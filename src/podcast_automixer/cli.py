from __future__ import annotations

import argparse
import math
import os
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.prompt import Confirm, FloatPrompt, Prompt
from rich.table import Table

if TYPE_CHECKING:
    from .core import AudioInfo

console = Console()


def run_automix(*args: Any, **kwargs: Any) -> Any:
    """Load the audio runner only when a run actually starts."""
    from .run import run_automix as run

    return run(*args, **kwargs)


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


def _prompt_paths(*, show_banner: bool = True) -> list[Path]:
    if show_banner:
        console.print(
            Panel(
                "Drag or paste each synchronized WAV file when prompted.\n"
                "Enter one path at a time, then press Enter when all tracks are added.",
                title="Podcast Automixer",
            )
        )
    paths: list[Path] = []
    while True:
        raw = Prompt.ask(f"WAV file {len(paths) + 1} (Enter when done)")
        if not raw.strip():
            if len(paths) >= 2:
                return paths
            console.print("[bold red]Error:[/bold red] At least two WAV files are required.")
            continue
        try:
            paths.append(_path(normalize_interactive_path(raw)))
        except ValueError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")


def _confirm_overwrite(progress_display: Progress, count: int) -> bool:
    progress_display.stop()
    try:
        return Confirm.ask(f"{count} output(s) exist. Overwrite all?", default=False)
    finally:
        progress_display.start()


def _require_overwrite(count: int) -> bool:
    raise ValueError(f"{count} artifact(s) already exist; rerun with --overwrite.")


def _positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def _nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def _nonnegative_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def _nonpositive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number > 0:
        raise argparse.ArgumentTypeError("must be zero or less")
    return number


def _output_directory(value: str) -> Path:
    path = _path(value)
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"not an existing directory: {path}")
    if not os.access(path, os.W_OK):
        raise argparse.ArgumentTypeError(f"directory is not writable: {path}")
    return path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Automix synchronized podcast stems",
        epilog=(
            "examples:\n"
            "  podcast-automix host.wav guest.wav\n"
            "  podcast-automix --preview-start 30 --output-dir mixes host.wav guest.wav\n"
            "  podcast-automix --non-interactive --overwrite host.wav guest.wav"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    result.add_argument(
        "--version", action="version", version=f"%(prog)s {version('podcast-automixer')}"
    )
    result.add_argument(
        "files", nargs="*", type=_path, help="two or more synchronized mono WAV files"
    )
    run = result.add_argument_group("run controls")
    run.add_argument("--preview-start", type=_nonnegative_float, default=None, metavar="SECONDS")
    run.add_argument("--preview-duration", type=_positive_float, default=None, metavar="SECONDS")
    run.add_argument("--output-dir", type=_output_directory, metavar="DIRECTORY")
    run.add_argument("--advanced", action="store_true")
    run.add_argument("--overwrite", action="store_true")
    run.add_argument("--non-interactive", action="store_true")
    run.add_argument("--quiet", action="store_true")
    run.add_argument("--no-color", action="store_true")
    run.add_argument(
        "--diagnostics", action="store_true", help="write a frame-level activity/gain CSV"
    )
    configuration = result.add_argument_group("configuration")
    configuration.add_argument("--config", type=_path, metavar="PATH")
    configuration.add_argument("--write-config", type=_path, metavar="PATH")
    settings = result.add_argument_group("Automix Engine settings (Safe Defaults)")
    settings.add_argument(
        "--attenuation",
        type=_nonpositive_float,
        default=None,
        metavar="DB",
        help="inactive attenuation (default: -6.0)",
    )
    settings.add_argument(
        "--frame-ms",
        type=_positive_int,
        default=None,
        metavar="MS",
        help="analysis frame size (default: 20)",
    )
    settings.add_argument(
        "--ambiguity",
        type=_nonnegative_float,
        default=None,
        metavar="DB",
        help="ownership ambiguity (default: 9.0)",
    )
    settings.add_argument(
        "--preroll-ms",
        type=_nonnegative_int,
        default=None,
        metavar="MS",
        help="speech preroll (default: 150)",
    )
    settings.add_argument(
        "--hold-ms",
        type=_nonnegative_int,
        default=None,
        metavar="MS",
        help="speech hold (default: 400)",
    )
    settings.add_argument(
        "--open-ms",
        type=_positive_float,
        default=None,
        metavar="MS",
        help="Opening time constant in milliseconds, about 63%% complete (default: 50.0)",
    )
    settings.add_argument(
        "--close-ms",
        type=_positive_float,
        default=None,
        metavar="MS",
        help="Closing time constant in milliseconds, about 63%% complete (default: 500.0)",
    )
    settings.add_argument(
        "--segment-seconds",
        type=_positive_int,
        default=None,
        metavar="SECONDS",
        help="analysis segment size (default: 30)",
    )
    return result


def main() -> None:
    args = parser().parse_args()
    global console
    if args.no_color:
        console.no_color = True
    from .configuration import resolve_settings, write_configuration
    from .core import AutomixError, Settings

    try:
        if args.write_config:
            incompatible = []
            if args.files:
                incompatible.append("recordings")
            if args.advanced:
                incompatible.append("--advanced")
            if args.preview_start is not None:
                incompatible.append("--preview-start")
            if args.preview_duration is not None:
                incompatible.append("--preview-duration")
            if args.output_dir:
                incompatible.append("--output-dir")
            if args.diagnostics:
                incompatible.append("--diagnostics")
            errors = []
            try:
                settings = resolve_settings(args)
            except ValueError as exc:
                errors.append(str(exc))
            if incompatible:
                errors.append("--write-config cannot be combined with " + ", ".join(incompatible))
            if errors:
                raise ValueError("\n".join(errors))
            write_configuration(args.write_config, settings, overwrite=args.overwrite)
            console.print("Configuration written.")
            return
        errors = []
        try:
            settings = resolve_settings(args)
        except ValueError as exc:
            errors.append(str(exc))
        if args.non_interactive and not args.files:
            errors.append("--non-interactive requires at least two WAV files.")
        if errors:
            raise ValueError("\n".join(errors))
        from .engine import AutomixEngine
        from .run import RunRequest

        paths = args.files or (_prompt_paths(show_banner=False) if args.quiet else _prompt_paths())
        if args.advanced and not args.files:
            settings = Settings(
                attenuation_db=(
                    args.attenuation
                    if args.attenuation is not None
                    else FloatPrompt.ask(
                        "Inactive attenuation (dB)", default=settings.attenuation_db
                    )
                ),
                frame_ms=settings.frame_ms,
                ambiguity_db=(
                    args.ambiguity
                    if args.ambiguity is not None
                    else FloatPrompt.ask("Ownership ambiguity (dB)", default=settings.ambiguity_db)
                ),
                preroll_ms=settings.preroll_ms,
                hold_ms=settings.hold_ms,
                open_ms=(
                    args.open_ms
                    if args.open_ms is not None
                    else FloatPrompt.ask("Opening time constant (ms)", default=settings.open_ms)
                ),
                close_ms=(
                    args.close_ms
                    if args.close_ms is not None
                    else FloatPrompt.ask("Closing time constant (ms)", default=settings.close_ms)
                ),
                segment_seconds=settings.segment_seconds,
            )
        with Progress(
            TextColumn("{task.description:<28}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TextColumn("ETA"),
            TimeRemainingColumn(),
            console=console,
            disable=args.quiet,
        ) as progress_display:
            tasks: dict[str, TaskID] = {}

            def show_progress(event) -> None:
                phase = {
                    "analyzing": "Analyzing",
                    "rendering": "Rendering",
                    "measuring_loudness": "Measuring loudness",
                }[event.name.value]
                track, completed, total = event.track, event.completed, event.total
                task = tasks.get(phase)
                if task is None:
                    task = progress_display.add_task(
                        f"{phase} track {track}/{len(paths)}", total=total
                    )
                    tasks[phase] = task
                progress_display.update(
                    task,
                    description=f"{phase} track {track}/{len(paths)}",
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
                if not args.quiet:
                    console.print(table)

            result = AutomixEngine(run_automix).execute(
                RunRequest(
                    paths=paths,
                    settings=settings,
                    preview_start=args.preview_start,
                    preview_duration=args.preview_duration or 30.0,
                    overwrite=args.overwrite,
                    diagnostics=args.diagnostics,
                    output_directory=args.output_dir,
                ),
                progress=None if args.quiet else show_progress,
                inputs_ready=None if args.quiet else show_inputs,
                confirm_overwrite=(
                    _require_overwrite
                    if args.non_interactive
                    else lambda count: _confirm_overwrite(progress_display, count)
                ),
            )
        if not args.quiet:
            console.print("[green]Complete.[/green]")
        for output in result.outputs:
            console.print(f"  {output}")
        console.print(f"  {result.report}")
        console.print(f"  {result.html_report}")
        if result.diagnostics:
            console.print(f"  {result.diagnostics}")
    except KeyboardInterrupt:
        console.print("[yellow]Cancelled.[/yellow]")
        raise SystemExit(130) from None
    except (AutomixError, OSError, ValueError) as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
