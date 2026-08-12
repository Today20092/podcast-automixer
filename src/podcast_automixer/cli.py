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

from .core import AudioInfo, AutomixError, Settings
from .run import RunRequest, run_automix

console = Console()


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def normalize_interactive_path(raw: str) -> str:
    """Apply the interactive path contract without shell tokenization."""
    value = raw.strip()
    if not value:
        raise ValueError("Path cannot be empty; please try again.")
    for quote in ('"', "'"):
        if value.startswith(quote) != value.endswith(quote):
            raise ValueError("Path has an unmatched outer quote; please try again.")
        if value.startswith(quote):
            value = value[1:-1]
            if not value:
                raise ValueError("Path cannot be empty; please try again.")
            break
    return value


def _prompt_paths() -> list[Path]:
    console.print(
        Panel(
            "Drag or paste each synchronized WAV file when prompted.\n"
            "Enter exactly one path at a time.",
            title="Podcast Automixer",
        )
    )
    paths: list[Path] = []
    for index in range(1, 4):
        while True:
            raw = Prompt.ask(f"WAV file {index}/3")
            try:
                paths.append(_path(normalize_interactive_path(raw)))
                break
            except ValueError as exc:
                console.print(f"[bold red]Error:[/bold red] {exc}")
    return paths


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
        with Progress(
            TextColumn("{task.description:<28}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TextColumn("ETA"),
            TimeRemainingColumn(),
            console=console,
        ) as progress_display:
            tasks: dict[str, int] = {}

            def show_progress(phase: str, track: int, completed: int, total: int) -> None:
                task = tasks.get(phase)
                if task is None:
                    task = progress_display.add_task(f"{phase} track {track}/3", total=total)
                    tasks[phase] = task
                progress_display.update(
                    task,
                    description=f"{phase} track {track}/3",
                    completed=completed,
                    total=total,
                )

            def show_inputs(infos: list[AudioInfo]) -> None:
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

            result = run_automix(
                RunRequest(
                    paths=paths,
                    settings=settings,
                    preview_start=args.preview_start,
                    preview_duration=args.preview_duration,
                    overwrite=args.overwrite,
                    diagnostics=args.diagnostics,
                ),
                progress=show_progress,
                inputs_ready=show_inputs,
                confirm_overwrite=lambda count: Confirm.ask(
                    f"{count} output(s) exist. Overwrite all?", default=False
                ),
            )
        console.print("[green]Complete.[/green]")
        for output in result.outputs:
            console.print(f"  {output}")
        console.print(f"  {result.report}")
        console.print(f"  {result.html_report}")
        if result.diagnostics:
            console.print(f"  {result.diagnostics}")
    except (AutomixError, OSError, ValueError) as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
