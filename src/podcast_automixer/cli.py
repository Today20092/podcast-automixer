from __future__ import annotations

import argparse
import math
import os
import sys
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Any, Never

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
            if paths:
                return paths
            console.print("[bold red]Error:[/bold red] At least one WAV file is required.")
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


class _ArgumentParser(argparse.ArgumentParser):
    automation = False

    def exit(self, status: int = 0, message: str | None = None) -> Never:
        if self.automation:
            raise ValueError(message or "--help and --version are unavailable with --json")
        super().exit(status, message)

    def error(self, message: str) -> Never:
        if self.automation:
            raise ValueError(message)
        super().error(message)


def parser(*, automation: bool = False) -> argparse.ArgumentParser:
    result = _ArgumentParser(
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
    result.automation = automation
    result.add_argument("--json", action="store_true", help="write the Automation Result as JSON")
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
    automation_mode = "--json" in sys.argv[1:]
    if automation_mode and any(option in sys.argv[1:] for option in ("-h", "--help", "--version")):
        from .automation import result, write

        write(
            result(
                status="error",
                error=("invalid_arguments", "--help and --version are unavailable with --json"),
            )
        )
        raise SystemExit(2)
    try:
        args = parser(automation=automation_mode).parse_args()
    except ValueError as exc:
        from .automation import result, write

        write(result(status="error", error=("invalid_arguments", str(exc))))
        raise SystemExit(2) from None
    global console
    if args.no_color:
        console.no_color = True
    from .configuration import resolve_settings, write_configuration
    from .core import AutomixError, Settings

    settings = Settings()
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
            if args.json:
                from .automation import result as automation_result
                from .automation import write

                write(
                    automation_result(
                        status="success",
                        kind="configuration",
                        settings=settings,
                        artifacts=[args.write_config],
                    )
                )
                return
            console.print("Configuration written.")
            return
        errors = []
        try:
            settings = resolve_settings(args)
        except ValueError as exc:
            errors.append(str(exc))
        if args.non_interactive and not args.files:
            errors.append("--non-interactive requires at least two WAV files.")
        elif args.json and not args.files:
            errors.append("--json requires at least two WAV files.")
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
            disable=args.quiet or args.json,
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
                progress=None if args.quiet or args.json else show_progress,
                inputs_ready=None if args.quiet or args.json else show_inputs,
                confirm_overwrite=(
                    _require_overwrite
                    if args.non_interactive or args.json
                    else lambda count: _confirm_overwrite(progress_display, count)
                ),
            )
        if args.json:
            from .automation import result as automation_result
            from .automation import write

            artifacts = [*result.outputs, result.report, result.html_report]
            if result.diagnostics:
                artifacts.append(result.diagnostics)
            write(
                automation_result(
                    status="success",
                    inputs=paths,
                    settings=settings,
                    artifacts=artifacts,
                )
            )
            return
        if not args.quiet:
            console.print("[green]Complete.[/green]")
        for output in result.outputs:
            console.print(f"  {output}", soft_wrap=True)
        console.print(f"  {result.report}", soft_wrap=True)
        console.print(f"  {result.html_report}", soft_wrap=True)
        if result.diagnostics:
            console.print(f"  {result.diagnostics}", soft_wrap=True)
    except KeyboardInterrupt:
        if automation_mode:
            from .automation import result, write

            write(
                result(
                    status="cancelled",
                    inputs=getattr(args, "files", []),
                    error=("cancelled", "Automix was cancelled."),
                )
            )
            raise SystemExit(130) from None
        console.print("[yellow]Cancelled.[/yellow]")
        raise SystemExit(130) from None
    except (AutomixError, OSError, ValueError) as exc:
        if automation_mode:
            from .automation import result, write

            message = str(exc)
            if "already exist" in message:
                code = "output_collision"
            elif isinstance(exc, AutomixError):
                if any(
                    text in message
                    for text in (
                        "WAV files are required",
                        "File not found",
                        "Not a WAV",
                        "requires mono",
                        "Inputs must have identical",
                        "Preview range is outside",
                    )
                ):
                    code = "invalid_inputs"
                else:
                    code = "processing_failed"
            elif getattr(args, "config", None) or getattr(args, "write_config", None):
                code = "invalid_configuration"
            else:
                code = "invalid_arguments"
            write(
                result(
                    status="error",
                    inputs=getattr(args, "files", []),
                    settings=settings,
                    error=(code, message),
                )
            )
            raise SystemExit(2) from None
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(2) from exc
    except Exception as exc:
        if automation_mode:
            from .automation import result, write

            write(
                result(
                    status="error",
                    inputs=getattr(args, "files", []),
                    settings=settings,
                    error=("internal_failure", str(exc)),
                )
            )
            raise SystemExit(1) from None
        raise


if __name__ == "__main__":
    main()
