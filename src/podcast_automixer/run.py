from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .artifacts import OverwriteConfirmation, RenderedAudioArtifacts
from .core import (
    AudioInfo,
    AutomixError,
    ProgressCallback,
    Settings,
    analyze,
    inspect_inputs,
)
from .loudness import analyze_rendered_loudness
from .report import Report, write_diagnostics, write_html_report, write_json_report

InputsReadyCallback = Callable[[list[AudioInfo]], None]


@dataclass(frozen=True)
class RunRequest:
    paths: list[Path]
    settings: Settings
    preview_start: float | None = None
    preview_duration: float = 30.0
    overwrite: bool = False
    diagnostics: bool = False


@dataclass(frozen=True)
class RunResult:
    outputs: list[Path]
    report: Path
    html_report: Path
    diagnostics: Path | None


def run_automix(
    request: RunRequest,
    *,
    progress: ProgressCallback | None = None,
    confirm_overwrite: OverwriteConfirmation | None = None,
    inputs_ready: InputsReadyCallback | None = None,
) -> RunResult:
    """Validate and execute one complete non-interactive automix run."""
    infos = inspect_inputs(request.paths)
    if inputs_ready:
        inputs_ready(infos)

    preview = request.preview_start is not None
    start = round((request.preview_start or 0.0) * infos[0].samplerate)
    available = infos[0].frames - start
    count = (
        min(available, round(request.preview_duration * infos[0].samplerate))
        if preview
        else available
    )
    if start < 0 or count <= 0:
        raise AutomixError("Preview range is outside the files.")

    rendered_audio = RenderedAudioArtifacts.prepare(
        infos,
        preview=preview,
        overwrite=request.overwrite,
        confirm_overwrite=confirm_overwrite,
    )
    outputs = rendered_audio.paths

    report = outputs[0].with_name("podcast-automix-report.json")
    html_report = outputs[0].with_name("podcast-automix-report.html")
    diagnostics = (
        outputs[0].with_name("podcast-automix-diagnostics.csv") if request.diagnostics else None
    )
    artifacts = [*outputs, report, html_report]
    if diagnostics:
        artifacts.append(diagnostics)
    absent_before_run = {path for path in artifacts if not path.exists()}

    try:
        analysis = analyze(infos, request.settings, start, count, progress=progress)
        rendered = rendered_audio.render(
            analysis.gains,
            request.settings,
            start,
            count,
            progress=progress,
        )
        analysis_report = {
            **analysis.report_values,
            "loudness": analyze_rendered_loudness(rendered, progress=progress),
        }
        report_model = Report(
            infos,
            request.settings,
            analysis.gains,
            analysis.active,
            analysis_report,
        )
        write_json_report(report, report_model)
        write_html_report(html_report, report_model)
        if diagnostics:
            write_diagnostics(diagnostics, report_model)
    except (Exception, KeyboardInterrupt):
        for artifact in absent_before_run:
            artifact.unlink(missing_ok=True)
        raise

    return RunResult(rendered, report, html_report, diagnostics)
