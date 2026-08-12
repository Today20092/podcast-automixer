from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .core import (
    AudioInfo,
    AutomixError,
    ProgressCallback,
    Settings,
    analyze,
    inspect_inputs,
    output_path,
    render,
    write_diagnostics,
    write_report,
)
from .loudness import analyze_rendered_loudness
from .report import write_html_report

OverwriteConfirmation = Callable[[int], bool]
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

    outputs = [output_path(info.path, preview) for info in infos]
    collisions = [path for path in outputs if path.exists()]
    overwrite = request.overwrite
    if collisions and not overwrite:
        overwrite = bool(confirm_overwrite and confirm_overwrite(len(collisions)))
        if not overwrite:
            raise AutomixError("Cancelled; no output files were changed.")

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
        rendered = render(
            infos,
            analysis.gains,
            request.settings,
            start,
            count,
            preview,
            overwrite,
            progress=progress,
        )
        analysis_report = {
            **analysis.report_values,
            "loudness": analyze_rendered_loudness(rendered),
        }
        write_report(report, infos, request.settings, analysis.gains, analysis_report)
        write_html_report(
            html_report,
            infos,
            request.settings,
            analysis.gains,
            analysis.active,
            analysis_report,
        )
        if diagnostics:
            write_diagnostics(diagnostics, analysis.active, analysis.gains, analysis.frame_ms)
    except Exception:
        for artifact in absent_before_run:
            artifact.unlink(missing_ok=True)
        raise

    return RunResult(rendered, report, html_report, diagnostics)
