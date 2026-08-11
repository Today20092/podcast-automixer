from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.prompt import Confirm, FloatPrompt, Prompt
from rich.table import Table

from .core import (
    AutomixError,
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

console = Console()


def _path(value: str) -> Path:
    return Path(value.strip().strip('"')).expanduser().resolve()


def parse_dropped_paths(raw: str) -> list[Path]:
    """Parse paths pasted by PowerShell/Windows Terminal drag-and-drop."""
    tokens: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    for character in raw.strip():
        if escaped:
            current.append(character)
            escaped = False
        elif character == "`":
            escaped = True
        elif quote:
            if character == quote:
                quote = None
            else:
                current.append(character)
        elif character in {'"', "'"}:
            quote = character
        elif character.isspace():
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(character)
    if escaped:
        current.append("`")
    if quote:
        raise ValueError("An input path has an unmatched quote.")
    if current:
        tokens.append("".join(current))
    return [_path(token) for token in tokens]


def _prompt_paths() -> list[Path]:
    console.print(
        Panel(
            "Drag all three synchronized WAV files here, then press Enter.\n"
            "Windows will paste their quoted paths.",
            title="Podcast Automixer",
        )
    )
    raw = Prompt.ask("WAV files")
    return parse_dropped_paths(raw)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Automix three synchronized podcast stems")
    result.add_argument("files", nargs="*", type=_path)
    result.add_argument("--preview-start", type=float, default=None, metavar="SECONDS")
    result.add_argument("--preview-duration", type=float, default=30.0, metavar="SECONDS")
    result.add_argument("--attenuation", type=float, default=-6.0, metavar="DB")
    result.add_argument("--ambiguity", type=float, default=9.0, metavar="DB")
    result.add_argument(
        "--open-ms",
        type=float,
        default=50.0,
        metavar="MS",
        help="Opening time constant in milliseconds (about 63%% complete)",
    )
    result.add_argument(
        "--close-ms",
        type=float,
        default=500.0,
        metavar="MS",
        help="Closing time constant in milliseconds (about 63%% complete)",
    )
    result.add_argument("--advanced", action="store_true")
    result.add_argument("--overwrite", action="store_true")
    result.add_argument(
        "--diagnostics", action="store_true", help="Write a frame-level activity/gain CSV"
    )
    return result


def main() -> None:
    args = parser().parse_args()
    try:
        paths = args.files or _prompt_paths()
        settings = Settings(
            attenuation_db=args.attenuation,
            ambiguity_db=args.ambiguity,
            open_ms=args.open_ms,
            close_ms=args.close_ms,
        )
        if args.advanced and not args.files:
            settings = Settings(
                attenuation_db=FloatPrompt.ask("Inactive attenuation (dB)", default=-6.0),
                ambiguity_db=FloatPrompt.ask("Ownership ambiguity (dB)", default=9.0),
                open_ms=FloatPrompt.ask("Opening time constant (ms)", default=50.0),
                close_ms=FloatPrompt.ask("Closing time constant (ms)", default=500.0),
            )
        infos = inspect_inputs(paths)
        table = Table(title="Validated synchronized inputs")
        table.add_column("Track")
        table.add_column("File")
        table.add_column("Format")
        table.add_column("Duration")
        for index, info in enumerate(infos, 1):
            table.add_row(
                str(index),
                info.path.name,
                f"{info.samplerate} Hz {info.subtype} mono",
                f"{info.frames / info.samplerate:.3f} s",
            )
        console.print(table)

        preview = args.preview_start is not None
        start = round((args.preview_start or 0.0) * infos[0].samplerate)
        available = infos[0].frames - start
        count = (
            min(available, round(args.preview_duration * infos[0].samplerate))
            if preview
            else available
        )
        if start < 0 or count <= 0:
            raise AutomixError("Preview range is outside the files.")

        collisions = [
            output_path(info.path, preview)
            for info in infos
            if output_path(info.path, preview).exists()
        ]
        overwrite = args.overwrite
        if collisions and not overwrite:
            overwrite = Confirm.ask(
                f"{len(collisions)} output(s) exist. Overwrite all?", default=False
            )
            if not overwrite:
                raise AutomixError("Cancelled; no output files were changed.")

        with Progress(
            TextColumn("{task.description:<28}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TextColumn("ETA"),
            TimeRemainingColumn(),
            console=console,
        ) as progress_display:
            analysis_task = progress_display.add_task("Analyzing track 1/3", total=3 * count)

            def analysis_progress(phase: str, track: int, completed: int, total: int) -> None:
                progress_display.update(
                    analysis_task,
                    description=f"{phase} track {track}/3",
                    completed=completed,
                    total=total,
                )

            gains, active, analysis_report = analyze(
                infos, settings, start, count, progress=analysis_progress
            )
            progress_display.update(
                analysis_task, description="Analysis complete", completed=3 * count
            )

            render_task = progress_display.add_task("Rendering track 1/3", total=3 * count)

            def render_progress(phase: str, track: int, completed: int, total: int) -> None:
                progress_display.update(
                    render_task,
                    description=f"{phase} track {track}/3",
                    completed=completed,
                    total=total,
                )

            outputs = render(
                infos,
                gains,
                settings,
                start,
                count,
                preview,
                overwrite,
                progress=render_progress,
            )
            progress_display.update(
                render_task, description="Rendering complete", completed=3 * count
            )

        report = outputs[0].with_name("podcast-automix-report.json")
        analysis_report["loudness"] = analyze_rendered_loudness(outputs)
        write_report(report, infos, settings, gains, analysis_report)
        html_report = outputs[0].with_name("podcast-automix-report.html")
        write_html_report(html_report, infos, settings, gains, active, analysis_report)
        if args.diagnostics:
            diagnostics = outputs[0].with_name("podcast-automix-diagnostics.csv")
            write_diagnostics(diagnostics, active, gains, settings.frame_ms)
        console.print("[green]Complete.[/green]")
        for output in outputs:
            console.print(f"  {output}")
        console.print(f"  {report}")
        console.print(f"  {html_report}")
        if args.diagnostics:
            console.print(f"  {diagnostics}")
    except (AutomixError, OSError, ValueError) as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
