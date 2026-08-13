"""Small, purpose-built bridge for the pywebview desktop-shell spike."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from threading import Lock, Thread
from typing import Any

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
        inspection = self._engine.inspect(self._paths(paths))
        return {
            "inputs": [
                {"path": str(info.path), "samplerate": info.samplerate, "frames": info.frames}
                for info in inspection.inputs
            ],
            "problems": [asdict(problem) for problem in inspection.problems],
        }

    def start_preview(self, paths: object, output_directory: object) -> dict[str, str]:
        recording_paths = self._paths(paths)
        if not isinstance(output_directory, str) or not output_directory:
            raise ValueError("output_directory must be a directory path")
        with self._lock:
            if self._status["state"] in {"running", "cancelling"}:
                raise RuntimeError("A Preview Run is already active")
            self._token = CancellationToken()
            self._status = {"state": "running", "progress": None, "error": None}
            Thread(
                target=self._preview,
                args=(recording_paths, Path(output_directory), self._token),
                daemon=True,
            ).start()
        return {"state": "running"}

    def _preview(self, paths: list[Path], destination: Path, token: CancellationToken) -> None:
        try:
            result = self._engine.preview(
                paths,
                destination,
                duration_seconds=30.0,
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

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._status.copy()


def main() -> None:
    """Launch the packaged desktop shell only when pywebview is available."""
    import webview

    page = Path(__file__).with_name("desktop.html")
    webview.create_window("Podcast Automixer", page.as_uri(), js_api=DesktopBridge())
    webview.start()
