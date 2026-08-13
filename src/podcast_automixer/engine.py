"""Application-level interface shared by the CLI and Desktop Shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .artifacts import OverwriteConfirmation
from .core import AudioInfo, AutomixError, Settings, inspect_inputs
from .run import RunRequest, RunResult, run_automix

DEFAULT_SETTINGS = Settings()


class AutomixEventName(StrEnum):
    ANALYZING = "analyzing"
    CALCULATING_GAIN_AUTOMATION = "calculating_gain_automation"
    RENDERING = "rendering"
    MEASURING_LOUDNESS = "measuring_loudness"


@dataclass(frozen=True)
class AutomixEvent:
    name: AutomixEventName
    track: int
    completed: int
    total: int


@dataclass(frozen=True)
class ValidationProblem:
    code: str
    message: str


@dataclass(frozen=True)
class RecordingSetInspection:
    inputs: list[AudioInfo]
    problems: list[ValidationProblem]


class AutomixCancelled(RuntimeError):
    """Raised when a caller asks the engine to stop normal work."""


class CancellationToken:
    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise AutomixCancelled("Automix was cancelled.")


ProgressListener = Callable[[AutomixEvent], None]


class AutomixEngine:
    """Run Recording Set inspection, Preview Runs, and Full Renders."""

    def __init__(self, runner: Callable[..., RunResult] = run_automix) -> None:
        self._runner = runner

    def inspect(self, paths: list[Path]) -> RecordingSetInspection:
        try:
            return RecordingSetInspection(inspect_inputs(paths), [])
        except (AutomixError, OSError, RuntimeError) as exc:
            problem = ValidationProblem("invalid_recording_set", str(exc))
            return RecordingSetInspection([], [problem])

    def preview(
        self,
        paths: list[Path],
        output_directory: Path,
        *,
        settings: Settings = DEFAULT_SETTINGS,
        start_seconds: float = 0.0,
        duration_seconds: float = 30.0,
        progress: ProgressListener | None = None,
        cancellation: CancellationToken | None = None,
    ) -> RunResult:
        return self._run(
            RunRequest(
                paths,
                settings,
                preview_start=start_seconds,
                preview_duration=duration_seconds,
                output_directory=output_directory,
            ),
            progress,
            cancellation,
        )

    def full_render(
        self,
        paths: list[Path],
        output_directory: Path,
        *,
        settings: Settings = DEFAULT_SETTINGS,
        progress: ProgressListener | None = None,
        cancellation: CancellationToken | None = None,
        confirm_overwrite: OverwriteConfirmation | None = None,
    ) -> RunResult:
        request = RunRequest(paths, settings, output_directory=output_directory)
        return self._run(request, progress, cancellation, confirm_overwrite)

    def execute(
        self,
        request: RunRequest,
        *,
        progress: ProgressListener | None = None,
        cancellation: CancellationToken | None = None,
        confirm_overwrite: OverwriteConfirmation | None = None,
        inputs_ready: Callable[[list[AudioInfo]], None] | None = None,
    ) -> RunResult:
        """Execute a request while adapting legacy callbacks to stable events."""
        return self._run(request, progress, cancellation, confirm_overwrite, inputs_ready)

    def _run(
        self,
        request: RunRequest,
        progress: ProgressListener | None,
        cancellation: CancellationToken | None,
        confirm_overwrite: OverwriteConfirmation | None = None,
        inputs_ready: Callable[[list[AudioInfo]], None] | None = None,
    ) -> RunResult:
        event_names = {
            "Analyzing": AutomixEventName.ANALYZING,
            "Calculating gain automation": AutomixEventName.CALCULATING_GAIN_AUTOMATION,
            "Rendering": AutomixEventName.RENDERING,
            "Measuring loudness": AutomixEventName.MEASURING_LOUDNESS,
        }

        def emit(phase: str, track: int, completed: int, total: int) -> None:
            if cancellation:
                cancellation.raise_if_cancelled()
            if progress:
                progress(AutomixEvent(event_names[phase], track, completed, total))

        if cancellation:
            cancellation.raise_if_cancelled()
        return self._runner(
            request,
            progress=emit,
            check_cancelled=cancellation.raise_if_cancelled if cancellation else None,
            confirm_overwrite=confirm_overwrite,
            inputs_ready=inputs_ready,
        )
