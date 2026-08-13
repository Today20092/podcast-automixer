"""Small, purpose-built bridge for the pywebview desktop-shell spike."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from threading import Lock, Thread
from typing import Any, cast

from .engine import AutomixCancelled, AutomixEngine, AutomixEvent, CancellationToken


class DesktopBridge:
    """Expose only Recording Set inspection and one cancellable Preview Run to JavaScript."""

    def __init__(self, engine: Any | None = None) -> None:
        self._engine = engine or AutomixEngine()
        self._lock = Lock()
        self._token: CancellationToken | None = None
        self._status: dict[str, Any] = {"state": "idle", "progress": None, "error": None}

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
        return paths

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
        output_directory: object,
        start_seconds: object = 0.0,
        duration_seconds: object = 30.0,
    ) -> dict[str, str | float]:
        recording_paths = self._paths(paths)
        if not isinstance(output_directory, str) or not output_directory:
            raise ValueError("output_directory must be a directory path")
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
        destination = Path(output_directory) / "Preview Runs"
        destination.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if self._status["state"] in {"running", "cancelling"}:
                raise RuntimeError("A Preview Run is already active")
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
            with self._lock:
                self._status = {
                    "state": "complete",
                    "progress": self._status["progress"],
                    "error": None,
                    "outputs": [str(path) for path in result.outputs],
                }
        except AutomixCancelled:
            with self._lock:
                self._status = {"state": "cancelled", "progress": None, "error": None}
        except Exception as exc:
            with self._lock:
                self._status = {"state": "failed", "progress": None, "error": str(exc)}

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

    def choose_preview_directory(self) -> str | None:
        """Open the Desktop Shell's native destination chooser for Preview Runs."""
        import webview

        selected = webview.windows[0].create_file_dialog(cast(int, webview.FOLDER_DIALOG))
        return str(selected) if selected else None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._status.copy()


def main() -> None:
    """Launch the packaged desktop shell only when pywebview is available."""
    import webview

    page = Path(__file__).with_name("desktop.html")
    webview.create_window("Podcast Automixer", page.as_uri(), js_api=DesktopBridge())
    webview.start()
