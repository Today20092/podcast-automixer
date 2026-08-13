"""Small, purpose-built bridge for the pywebview desktop-shell spike."""

from __future__ import annotations

import os
import shutil
import tempfile
import webbrowser
from contextlib import suppress
from dataclasses import asdict
from json import dumps
from pathlib import Path
from threading import Lock, Thread
from time import monotonic, time
from typing import Any, cast

from . import __version__
from .diagnostic_timeline import build_diagnostic_timeline
from .diagnostics import DesktopDiagnostics
from .engine import AutomixCancelled, AutomixEngine, AutomixEvent, CancellationToken
from .loudness import analyze_comparison_playback
from .waveform import analyze_monitoring_waveform


def _dropped_file_paths(event: object) -> list[str]:
    """Extract unique paths supplied by pywebview's native drop event."""
    if not isinstance(event, dict):
        return []
    transfer = event.get("dataTransfer") or event.get("domTransfer")
    if not isinstance(transfer, dict) or not isinstance(transfer.get("files"), list):
        return []
    paths: list[str] = []
    for file in transfer["files"]:
        path = file.get("pywebviewFullPath") if isinstance(file, dict) else None
        if isinstance(path, str) and path and path not in paths:
            paths.append(path)
    return paths


def _dialog_path(selected: object) -> str | None:
    """Normalize pywebview's platform-dependent single-folder result."""
    if isinstance(selected, str):
        return selected or None
    if isinstance(selected, (list, tuple)) and selected and isinstance(selected[0], str):
        return selected[0] or None
    return None


def _bind_drop_events(window: Any) -> None:
    """Use pywebview DOM events so Explorer drops retain native file paths."""
    from webview.dom import DOMEventHandler

    def on_drop(event: object) -> None:
        window.evaluate_js(f"window.receiveDroppedPaths({dumps(_dropped_file_paths(event))})")

    options = dict(prevent_default=True, stop_propagation=True, stop_immediate_propagation=True)
    window.dom.document.events.dragover += DOMEventHandler(
        lambda _event: None, debounce=500, **options
    )
    window.dom.document.events.drop += DOMEventHandler(on_drop, **options)


class DesktopBridge:
    """Expose Recording Set inspection plus separate preview and full-render journeys."""

    _PREVIEW_ROOT_NAME = "podcast-automixer-preview-sessions"
    _PREVIEW_SESSION_PREFIX = "session-"
    _PREVIEW_MARKER = ".podcast-automixer-preview-session"
    _PREVIEW_MARKER_CONTENT = "podcast-automixer-preview-session-v1\n"
    _PREVIEW_RETENTION_SECONDS = 7 * 24 * 60 * 60

    @classmethod
    def _preview_root_directory(cls, temp_directory: Any) -> Any:
        """Append the app-owned root without imposing host-specific path semantics."""
        return temp_directory / cls._PREVIEW_ROOT_NAME

    def __init__(
        self,
        engine: Any | None = None,
        diagnostics: DesktopDiagnostics | None = None,
        temp_directory: Path | None = None,
    ) -> None:
        self._engine = engine or AutomixEngine()
        self._diagnostics = diagnostics or DesktopDiagnostics(version=__version__)
        self._lock = Lock()
        self._token: CancellationToken | None = None
        self._status: dict[str, Any] = {"state": "idle", "progress": None, "error": None}
        self._last_success: dict[str, Any] | None = None
        self._last_full_render: dict[str, Any] | None = None
        self._full_render_acknowledged = False
        self._waveform: dict[str, Any] = {"state": "idle"}
        self._waveform_generation = 0
        self._diagnostic_timeline_cache: dict[tuple[str, float, float], dict[str, Any]] = {}
        self._preview_run_number = 0
        self._preview_root = self._preview_root_directory(
            temp_directory or Path(tempfile.gettempdir())
        )
        self._preview_root.mkdir(parents=True, exist_ok=True)
        self._recover_stale_preview_sessions(self._preview_root)
        self._preview_session = Path(
            tempfile.mkdtemp(prefix=self._PREVIEW_SESSION_PREFIX, dir=self._preview_root)
        )
        (self._preview_session / self._PREVIEW_MARKER).write_text(
            self._PREVIEW_MARKER_CONTENT, encoding="utf-8"
        )

    def __getattribute__(self, name: str) -> Any:
        """Time every public pywebview operation and retain unexpected tracebacks."""
        value = super().__getattribute__(name)
        if name.startswith("_") or not callable(value):
            return value
        diagnostics = super().__getattribute__("_diagnostics")

        def operation(*args: Any, **kwargs: Any) -> Any:
            started = monotonic()
            diagnostics.log("operation_start operation=%s", name)
            try:
                return value(*args, **kwargs)
            except Exception as exc:
                diagnostics.exception(name, exc)
                raise
            finally:
                elapsed = monotonic() - started
                diagnostics.log("operation_finish operation=%s elapsed_seconds=%.3f", name, elapsed)
                if elapsed >= 5:
                    diagnostics.log(
                        "operation_slow operation=%s elapsed_seconds=%.3f", name, elapsed
                    )

        return operation

    def report_javascript_error(self, kind: object, message: object, stack: object = "") -> None:
        """Accept only renderer diagnostics; never let malformed reports affect the UI."""
        self._diagnostics.log(
            "javascript_error kind=%s message=%s stack=%s", kind, message, stack, level=40
        )

    def open_diagnostics_folder(self) -> dict[str, str]:
        """Open the local log directory without making shell failures user-visible."""
        directory = self._diagnostics.directory
        try:
            directory.mkdir(parents=True, exist_ok=True)
            if hasattr(os, "startfile"):
                os.startfile(directory)  # type: ignore[attr-defined]
            else:
                webbrowser.open(directory.as_uri())
        except Exception as exc:
            self._diagnostics.exception("open_diagnostics_folder", exc)
        return {"path": str(directory)}

    @staticmethod
    def _default_full_render_directory(paths: list[Path]) -> Path:
        """Put deliverables beside the recording set, never in Preview Runs."""
        parents = {path.parent.resolve() for path in paths}
        parent = next(iter(parents)) if len(parents) == 1 else paths[0].parent.resolve()
        return parent / "Podcast Automixer Output"

    @staticmethod
    def _unique_directory(directory: Path) -> Path:
        if not directory.exists():
            return directory
        for number in range(2, 10_000):
            candidate = directory.with_name(f"{directory.name} ({number})")
            if not candidate.exists():
                return candidate
        raise RuntimeError("Could not choose a unique output folder")

    @staticmethod
    def _paths(value: object) -> list[Path]:
        if (
            not isinstance(value, list)
            or not value
            or not all(isinstance(item, str) for item in value)
        ):
            raise ValueError("paths must be a non-empty list of file paths")
        paths = [Path(item) for item in value]
        if not all(path.suffix.lower() in {".wav", ".wave", ".w64", ".rf64"} for path in paths):
            raise ValueError("Recording Sets must contain WAV-family files")
        if any(not path.is_absolute() or ".." in path.parts for path in paths):
            raise ValueError("Recording Set paths must be absolute and must not traverse folders")
        return [path.resolve() for path in paths]

    def inspect_recording_set(self, paths: object) -> dict[str, Any]:
        recording_paths = self._paths(paths)
        individual = [self._engine.inspect([path]) for path in recording_paths]
        inspection = self._engine.inspect(recording_paths)
        return {
            "inputs": [
                {
                    "path": str(path),
                    "samplerate": item.inputs[0].samplerate if item.inputs else None,
                    "frames": item.inputs[0].frames if item.inputs else None,
                    "channels": item.inputs[0].channels if item.inputs else None,
                    "subtype": item.inputs[0].subtype if item.inputs else None,
                    "format": item.inputs[0].format if item.inputs else None,
                    "problems": [asdict(problem) for problem in item.problems],
                }
                for path, item in zip(recording_paths, individual, strict=True)
            ],
            "problems": [asdict(problem) for problem in inspection.problems],
        }

    def start_waveform_overview(self, paths: object) -> dict[str, str]:
        """Analyze the bounded overview on a worker, never on the bridge caller's thread."""
        recording_paths = self._paths(paths)
        inspection = self._engine.inspect(recording_paths)
        if inspection.problems or not inspection.inputs:
            raise ValueError("Recording Set must be valid before creating its waveform")
        with self._lock:
            self._waveform_generation += 1
            generation = self._waveform_generation
            self._waveform = {"state": "loading"}
        Thread(
            target=self._analyze_waveform, args=(recording_paths, generation), daemon=True
        ).start()
        return {"state": "loading"}

    def _analyze_waveform(self, paths: list[Path], generation: int) -> None:
        try:
            result = analyze_monitoring_waveform(paths)
            waveform = {"state": "complete", "result": result}
        except Exception:
            waveform = {"state": "unavailable"}
        with self._lock:
            if generation == self._waveform_generation:
                self._waveform = waveform

    def waveform_overview_status(self) -> dict[str, Any]:
        with self._lock:
            return self._waveform.copy()

    def choose_recordings(self) -> list[str]:
        """Open the Desktop Shell's native multi-file chooser."""
        import webview

        selected = webview.windows[0].create_file_dialog(
            cast(int, webview.OPEN_DIALOG),
            allow_multiple=True,
            file_types=("Wave audio (*.wav;*.wave;*.rf64)",),
        )
        return list(selected or [])

    def start_preview(
        self,
        paths: object,
        start_seconds: object = 0.0,
        duration_seconds: object = 30.0,
    ) -> dict[str, str | float]:
        recording_paths = self._paths(paths)
        if not isinstance(start_seconds, (int, float)) or not isinstance(
            duration_seconds, (int, float)
        ):
            raise ValueError("Preview range must use numeric seconds")
        if not 5.0 <= duration_seconds <= 600.0:
            raise ValueError("Preview duration must be between 5 seconds and 10 minutes")

        inspection = self._engine.inspect(recording_paths)
        if inspection.problems or not inspection.inputs:
            raise ValueError("Recording Set must be valid before creating a Preview Run")
        recording_end = min(item.frames / item.samplerate for item in inspection.inputs)
        if recording_end < 5.0:
            raise ValueError("Recording Set must be at least 5 seconds long for a Preview Run")
        start = min(max(float(start_seconds), 0.0), recording_end - 5.0)
        duration = min(float(duration_seconds), recording_end - start)
        with self._lock:
            if self._status["state"] in {"running", "cancelling"}:
                raise RuntimeError("A Preview Run is already active")
            self._preview_run_number += 1
            destination = self._preview_session / f"run-{self._preview_run_number:04d}"
            destination.mkdir()
            self._token = CancellationToken()
            self._status = {"state": "running", "progress": None, "error": None}
            Thread(
                target=self._preview,
                args=(recording_paths, destination, start, duration, self._token),
                daemon=True,
            ).start()
        return {"state": "running", "start_seconds": start, "duration_seconds": duration}

    def _preview(
        self,
        paths: list[Path],
        destination: Path,
        start_seconds: float,
        duration_seconds: float,
        token: CancellationToken,
    ) -> None:
        try:
            result = self._engine.preview(
                paths,
                destination,
                start_seconds=start_seconds,
                duration_seconds=duration_seconds,
                progress=self._progress,
                cancellation=token,
            )
            completed = {
                "outputs": [str(path) for path in result.outputs],
                "paths": [str(path) for path in paths],
                "start_seconds": start_seconds,
                "duration_seconds": duration_seconds,
                "report": str(result.report),
                "html_report": str(result.html_report),
                "directory": str(destination),
            }
            with self._lock:
                self._last_success = completed
                self._status = {
                    "state": "complete",
                    "progress": self._status["progress"],
                    "error": None,
                }
        except AutomixCancelled:
            with self._lock:
                self._status = {"state": "cancelled", "progress": None, "error": None}
        except Exception as exc:
            self._diagnostics.exception("preview", exc)
            with self._lock:
                self._status = {
                    "state": "failed",
                    "progress": None,
                    "error": "Processing failed. Open diagnostics folder for details.",
                }

    def _progress(self, event: AutomixEvent) -> None:
        with self._lock:
            self._status["progress"] = {
                "phase": event.name,
                "completed": event.completed,
                "total": event.total,
            }

    def cancel_preview(self) -> dict[str, str]:
        with self._lock:
            if self._status["state"] == "running" and self._token:
                self._status["state"] = "cancelling"
                self._token.cancel()
            return {"state": self._status["state"]}

    @classmethod
    def _is_owned_preview_session(cls, directory: Path, root: Path) -> bool:
        """Require the expected location, name, and marker before recursive deletion."""
        try:
            marker = directory / cls._PREVIEW_MARKER
            return (
                directory.parent.resolve() == root.resolve()
                and directory.name.startswith(cls._PREVIEW_SESSION_PREFIX)
                and marker.is_file()
                and marker.read_text(encoding="utf-8") == cls._PREVIEW_MARKER_CONTENT
            )
        except OSError:
            return False

    @classmethod
    def _recover_stale_preview_sessions(cls, root: Path, now: float | None = None) -> list[Path]:
        """Remove only marked sessions older than the bounded seven-day retention window."""
        if not root.is_dir():
            return []
        cutoff = (time() if now is None else now) - cls._PREVIEW_RETENTION_SECONDS
        removed: list[Path] = []
        for directory in root.iterdir():
            if not cls._is_owned_preview_session(directory, root):
                continue
            try:
                if (directory / cls._PREVIEW_MARKER).stat().st_mtime > cutoff:
                    continue
                shutil.rmtree(directory)
                removed.append(directory)
            except OSError:
                continue
        return removed

    def close_session(self) -> None:
        """Best-effort normal-exit cleanup limited to this bridge's marked session."""
        if self._is_owned_preview_session(self._preview_session, self._preview_root):
            with suppress(OSError):
                shutil.rmtree(self._preview_session)

    def export_preview(self, output_directory: object = None) -> dict[str, str]:
        """Copy the latest successful Preview Run without changing the active result."""
        with self._lock:
            result = self._last_success.copy() if self._last_success else None
        if not result:
            raise ValueError("A successful Preview Run is required before exporting")
        if output_directory is None:
            import webview

            selected = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
            output_directory = _dialog_path(selected)
        if output_directory is None:
            return {"state": "cancelled"}
        if not isinstance(output_directory, str) or not output_directory:
            raise ValueError("output_directory must be a directory path")
        source = Path(result["directory"])
        if not source.is_dir() or not source.resolve().is_relative_to(
            self._preview_session.resolve()
        ):
            raise ValueError("Preview Run artifacts are unavailable")
        destination = self._unique_directory(Path(output_directory) / "Podcast Automixer Preview")
        shutil.copytree(source, destination)
        return {"state": "complete", "destination": str(destination)}

    def choose_full_render_directory(self) -> str | None:
        """Open the native destination chooser for Full Render deliverables."""
        import webview

        selected = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
        return _dialog_path(selected)

    def full_render_destination(
        self, paths: object, chosen_directory: object = None
    ) -> dict[str, str]:
        recording_paths = self._paths(paths)
        if chosen_directory is not None and not isinstance(chosen_directory, str):
            raise ValueError("chosen_directory must be a directory path")
        base = (
            Path(chosen_directory)
            if chosen_directory
            else self._default_full_render_directory(recording_paths)
        )
        return {"default": str(base), "unique": str(self._unique_directory(base))}

    def start_full_render(
        self, paths: object, chosen_directory: object = None, replace_existing: object = False
    ) -> dict[str, str]:
        recording_paths = self._paths(paths)
        if chosen_directory is not None and not isinstance(chosen_directory, str):
            raise ValueError("chosen_directory must be a directory path")
        if not isinstance(replace_existing, bool):
            raise ValueError("replace_existing must be true or false")
        inspection = self._engine.inspect(recording_paths)
        if inspection.problems or not inspection.inputs:
            raise ValueError("Recording Set must be valid immediately before Full Render")
        base = (
            Path(chosen_directory)
            if chosen_directory
            else self._default_full_render_directory(recording_paths)
        )
        destination = base if replace_existing else self._unique_directory(base)
        if replace_existing and base.exists() and not base.is_dir():
            raise ValueError("Full Render destination must be a folder")
        destination_existed = destination.exists()
        destination.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if self._status["state"] in {"running", "cancelling"}:
                raise RuntimeError("An automix run is already active")
            self._token = CancellationToken()
            self._status = {
                "state": "running",
                "progress": None,
                "error": None,
                "kind": "full_render",
            }
            Thread(
                target=self._full_render,
                args=(
                    recording_paths,
                    destination,
                    self._token,
                    replace_existing,
                    not destination_existed,
                ),
                daemon=True,
            ).start()
        return {"state": "running", "destination": str(destination)}

    def _full_render(
        self,
        paths: list[Path],
        destination: Path,
        token: CancellationToken,
        replace_existing: bool,
        remove_empty_destination: bool,
    ) -> None:
        try:
            result = self._engine.full_render(
                paths,
                destination,
                progress=self._progress,
                cancellation=token,
                confirm_overwrite=(lambda _count: replace_existing),
            )
            completed = {
                "outputs": [str(path) for path in result.outputs],
                "destination": str(destination),
                "report": str(result.report),
                "html_report": str(result.html_report),
            }
            with self._lock:
                self._last_full_render = completed
                self._full_render_acknowledged = False
                self._status = {
                    "state": "complete",
                    "progress": self._status["progress"],
                    "error": None,
                    "kind": "full_render",
                }
        except AutomixCancelled:
            if remove_empty_destination:
                _remove_empty_directory(destination)
            with self._lock:
                self._status = {
                    "state": "cancelled",
                    "progress": None,
                    "error": None,
                    "kind": "full_render",
                }
        except Exception as exc:
            self._diagnostics.exception("full_render", exc)
            if remove_empty_destination:
                _remove_empty_directory(destination)
            with self._lock:
                self._status = {
                    "state": "failed",
                    "progress": None,
                    "error": "Processing failed. Open diagnostics folder for details.",
                    "kind": "full_render",
                }

    def cancel_full_render(self) -> dict[str, str]:
        return self.cancel_preview()

    def open_full_render_folder(self) -> dict[str, str]:
        with self._lock:
            result = self._last_full_render.copy() if self._last_full_render else None
        if not result:
            raise ValueError("A completed Full Render is required before opening its folder")
        destination = result["destination"]
        try:
            if hasattr(os, "startfile"):
                os.startfile(destination)  # type: ignore[attr-defined]
            else:
                webbrowser.open(Path(destination).as_uri())
        except Exception:
            # A shell/device failure must not turn a completed render into a failed one.
            pass
        return {"path": destination}

    def full_render_mix_report(self) -> dict[str, str]:
        """Return the completed Full Render's portable, self-contained Mix Report."""
        with self._lock:
            report = self._last_full_render and self._last_full_render.get("html_report")
            if isinstance(report, str):
                self._full_render_acknowledged = True
        if not isinstance(report, str):
            raise ValueError("A completed Full Render is required before viewing its Mix Report")
        return {"path": report, "url": Path(report).as_uri()}

    def open_full_render_mix_report(self) -> dict[str, str]:
        """Open the portable Full Render Mix Report without affecting render success."""
        report = self.full_render_mix_report()
        with suppress(Exception):
            webbrowser.open(report["url"])
        return report

    def close_state(self) -> dict[str, bool]:
        """Expose the only two conditions that require a close confirmation."""
        with self._lock:
            active = self._status["state"] in {"running", "cancelling"}
            unacknowledged = (
                self._last_full_render is not None and not self._full_render_acknowledged
            )
        return {"active_processing": active, "unacknowledged_full_render": unacknowledged}

    def status(self) -> dict[str, Any]:
        with self._lock:
            status = self._status.copy()
            if self._last_success:
                status["result"] = self._last_success.copy()
                status["preview_result"] = self._last_success.copy()
            if self._last_full_render:
                status["full_render_result"] = self._last_full_render.copy()
                status["full_render_acknowledged"] = self._full_render_acknowledged
            return status

    def comparison_playback(self) -> dict[str, Any]:
        """Return immutable Preview Run sources and playback-only loudness matching."""
        with self._lock:
            if not self._last_success:
                raise ValueError("Comparison Playback requires a completed Preview Run")
            paths = self._last_success.get("paths")
            outputs = self._last_success.get("outputs")
            start = self._last_success.get("start_seconds")
            duration = self._last_success.get("duration_seconds")
        if (
            not isinstance(paths, list)
            or not isinstance(outputs, list)
            or not all(isinstance(path, str) for path in [*paths, *outputs])
            or not isinstance(start, (int, float))
            or not isinstance(duration, (int, float))
        ):
            raise ValueError("Preview Run audio is unavailable")
        metrics = analyze_comparison_playback(
            [Path(path) for path in paths],
            [Path(path) for path in outputs],
            float(start),
            float(duration),
        )
        report = self._last_success.get("report")
        key = (paths[0], float(start), float(duration))
        timeline = self._diagnostic_timeline_cache.get(key)
        if timeline is None and isinstance(report, str):
            timeline = build_diagnostic_timeline(
                Path(paths[0]),
                Path(outputs[0]),
                Path(report),
                float(start),
                float(duration),
            )
            self._diagnostic_timeline_cache[key] = timeline
        result = {
            "original_paths": paths,
            "automixed_paths": outputs,
            "start_seconds": start,
            "duration_seconds": duration,
            **metrics,
        }
        if timeline is not None:
            result["diagnostic_timeline"] = timeline
        return result

    def preview_mix_report(self) -> dict[str, str]:
        """Return the latest successful Preview Run's self-contained Mix Report."""
        with self._lock:
            report = self._last_success and self._last_success.get("html_report")
        if not isinstance(report, str):
            raise ValueError("A successful Preview Run is required before viewing its Mix Report")
        return {"path": report, "url": Path(report).as_uri()}

    def open_preview_mix_report(self) -> dict[str, str]:
        """Open the current Preview Mix Report in the system browser."""
        report = self.preview_mix_report()
        webbrowser.open(report["url"])
        return report


def _remove_empty_directory(directory: Path) -> None:
    """Best-effort cleanup for a new Full Render folder after an incomplete run."""
    with suppress(OSError):
        directory.rmdir()


def main() -> None:
    """Launch the packaged desktop shell only when pywebview is available."""
    import webview

    page = Path(__file__).with_name("desktop-ui") / "index.html"
    bridge = DesktopBridge()
    window = webview.create_window("Podcast Automixer", page.as_uri(), js_api=bridge)
    assert window is not None
    window.events.closed += bridge.close_session
    scripts = ("desktop_diagnostics.js",)
    window.events.loaded += lambda: window.evaluate_js(
        "\n".join(
            Path(__file__).with_name(script).read_text(encoding="utf-8") for script in scripts
        )
    )
    webview.start(_bind_drop_events, (window,))
