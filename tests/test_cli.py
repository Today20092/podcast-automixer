import shutil
import subprocess
from collections.abc import Callable
from io import StringIO
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import SimpleNamespace
from typing import cast

import pytest
from rich.console import Console
from rich.progress import Progress

from podcast_automixer import cli


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('"C:\\Audio Files\\voice ` one.wav"', "C:\\Audio Files\\voice ` one.wav"),
        ("'\\\\server\\share\\O’Brien.wav'", "\\\\server\\share\\O’Brien.wav"),
        ('"/Users/me/My Recording.wav"', "/Users/me/My Recording.wav"),
        (r"/Users/me/My\ Recording.wav", r"/Users/me/My\ Recording.wav"),
        ("/home/me/it's ` here.wav", "/home/me/it's ` here.wav"),
        ("-opening.wav", "-opening.wav"),
        ("C:\\Audio\\", "C:\\Audio\\"),
    ],
)
def test_normalize_interactive_path_preserves_path_characters(raw: str, expected: str) -> None:
    assert cli.normalize_interactive_path(raw) == expected


def test_interactive_paths_have_host_independent_windows_and_posix_lexing() -> None:
    assert (
        PureWindowsPath(cli.normalize_interactive_path('"C:\\Audio Files\\one.wav"')).drive == "C:"
    )
    assert (
        PureWindowsPath(cli.normalize_interactive_path('"\\\\server\\share\\one.wav"')).drive
        == "\\\\server\\share"
    )
    assert PurePosixPath(cli.normalize_interactive_path('"/Users/me/one.wav"')).is_absolute()
    assert PurePosixPath(cli.normalize_interactive_path("'/home/me/one.wav'")).is_absolute()


@pytest.mark.parametrize("raw", ["", "   ", "'unterminated", 'unterminated"'])
def test_normalize_interactive_path_rejects_malformed_input(raw: str) -> None:
    with pytest.raises(ValueError, match="try again"):
        cli.normalize_interactive_path(raw)


def test_prompt_paths_retries_and_collects_until_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(
        ["", '"first file.wav"', "second`file.wav", "third file.wav", "fourth file.wav", ""]
    )
    monkeypatch.setattr(cli.Prompt, "ask", lambda _prompt: next(answers))

    paths = cli._prompt_paths()

    assert [path.name for path in paths] == [
        "first file.wav",
        "second`file.wav",
        "third file.wav",
        "fourth file.wav",
    ]


def test_prompt_paths_accepts_one_file(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(['"voiceover.wav"', ""])
    monkeypatch.setattr(cli.Prompt, "ask", lambda _prompt: next(answers))

    assert [path.name for path in cli._prompt_paths()] == ["voiceover.wav"]


def test_direct_cli_path_is_not_reparsed(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = "literal ` 'quoted' path.wav"
    parsed = cli.parser().parse_args([raw])

    assert parsed.files == [cli._path(raw)]


def test_direct_cli_accepts_filename_beginning_with_dash_after_separator() -> None:
    parsed = cli.parser().parse_args(["--", "-one.wav", "two.wav", "three.wav"])

    assert [path.name for path in parsed.files] == ["-one.wav", "two.wav", "three.wav"]


def test_parser_exposes_all_engine_settings_and_disables_abbreviation() -> None:
    parsed = cli.parser().parse_args(
        [
            "--attenuation",
            "-8",
            "--frame-ms",
            "10",
            "--ambiguity",
            "7",
            "--preroll-ms",
            "100",
            "--hold-ms",
            "300",
            "--open-ms",
            "25",
            "--close-ms",
            "250",
            "--segment-seconds",
            "15",
        ]
    )

    assert (
        parsed.attenuation,
        parsed.frame_ms,
        parsed.ambiguity,
        parsed.preroll_ms,
        parsed.hold_ms,
        parsed.open_ms,
        parsed.close_ms,
        parsed.segment_seconds,
    ) == (-8.0, 10, 7.0, 100, 300, 25.0, 250.0, 15)
    with pytest.raises(SystemExit):
        cli.parser().parse_args(["--non-int"])


def test_non_interactive_never_prompts_without_recordings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "_prompt_paths", lambda **_kwargs: pytest.fail("prompted"))
    monkeypatch.setattr("sys.argv", ["podcast-automix", "--non-interactive"])

    with pytest.raises(SystemExit) as stopped:
        cli.main()

    assert stopped.value.code == 2


def test_write_config_does_not_prompt_or_start_engine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "saved.toml"
    monkeypatch.setattr(cli, "_prompt_paths", lambda **_kwargs: pytest.fail("prompted"))
    monkeypatch.setattr(cli, "run_automix", lambda *_args, **_kwargs: pytest.fail("engine started"))
    monkeypatch.setattr(
        "sys.argv", ["podcast-automix", "--write-config", str(path), "--frame-ms", "10"]
    )

    cli.main()

    assert "frame_ms = 10" in path.read_text(encoding="utf-8")


def test_write_config_rejects_run_only_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "podcast-automix",
            "--write-config",
            str(tmp_path / "saved.toml"),
            "--diagnostics",
            "one.wav",
        ],
    )

    with pytest.raises(SystemExit) as stopped:
        cli.main()

    assert stopped.value.code == 2
    assert not (tmp_path / "saved.toml").exists()


def test_installed_command_writes_and_loads_unicode_configuration(tmp_path: Path) -> None:
    first = tmp_path / "配置.toml"
    second = tmp_path / "copy.toml"
    command = shutil.which("podcast-automix")
    assert command

    written = subprocess.run(
        [command, "--write-config", first, "--frame-ms", "10"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    loaded = subprocess.run(
        [command, "--config", first, "--write-config", second],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert written.returncode == loaded.returncode == 0
    assert "frame_ms = 10" in second.read_text(encoding="utf-8")

    protected = subprocess.run(
        [command, "--write-config", second], capture_output=True, text=True, check=False
    )
    replaced = subprocess.run(
        [command, "--write-config", second, "--overwrite", "--frame-ms", "20"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert protected.returncode == 2
    assert "--overwrite" in protected.stdout
    assert replaced.returncode == 0
    assert "frame_ms = 20" in second.read_text(encoding="utf-8")


def test_installed_command_reports_malformed_configuration(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text("schema_version = 2\nunknown = true\n", encoding="utf-8")
    command = shutil.which("podcast-automix")
    assert command

    result = subprocess.run(
        [command, "--config", path, "--non-interactive"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "schema_version" in result.stdout
    assert "unknown top-level key(s): unknown" in result.stdout
    assert "--non-interactive requires" in result.stdout


def test_write_config_accumulates_configuration_and_mode_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("schema_version = 2\n", encoding="utf-8")
    output = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=output, color_system=None))
    monkeypatch.setattr(
        "sys.argv",
        [
            "podcast-automix",
            "--config",
            str(bad),
            "--write-config",
            str(tmp_path / "saved.toml"),
            "--preview-duration",
            "30",
        ],
    )

    with pytest.raises(SystemExit):
        cli.main()

    assert "schema_version" in output.getvalue()
    assert "--preview-duration" in output.getvalue()


def test_quiet_routes_output_directory_and_keeps_artifact_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured = []

    def run(request: object, **callbacks: object) -> object:
        captured.append((request, callbacks))
        return SimpleNamespace(
            outputs=[tmp_path / "one_auto-mixed.wav"],
            report=tmp_path / "podcast-automix-report.json",
            html_report=tmp_path / "podcast-automix-report.html",
            diagnostics=None,
        )

    output = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=output, color_system=None))
    monkeypatch.setattr(cli, "run_automix", run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "podcast-automix",
            "--quiet",
            "--non-interactive",
            "--output-dir",
            str(tmp_path),
            "one.wav",
            "two.wav",
        ],
    )

    cli.main()

    request, callbacks = captured[0]
    assert request.output_directory == tmp_path.resolve()
    assert callable(callbacks["progress"])
    assert callbacks["inputs_ready"] is None
    with pytest.raises(ValueError, match="--overwrite"):
        cast(Callable[[int], bool], callbacks["confirm_overwrite"])(1)
    assert "Complete." not in output.getvalue()
    assert "one_auto-mixed.wav" in output.getvalue()


def test_overwrite_confirmation_suspends_progress_display(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeProgress:
        def stop(self) -> None:
            events.append("stop")

        def start(self) -> None:
            events.append("start")

    def ask(_prompt: str, *, default: bool) -> bool:
        assert default is False
        events.append("prompt")
        return True

    monkeypatch.setattr(cli.Confirm, "ask", ask)

    assert cli._confirm_overwrite(cast(Progress, FakeProgress()), 3) is True
    assert events == ["stop", "prompt", "start"]


def test_cli_reports_clean_cancellation_without_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def cancel(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    output = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=output, color_system=None))
    monkeypatch.setattr(cli, "_prompt_paths", lambda: [Path("one.wav"), Path("two.wav")])
    monkeypatch.setattr(cli, "run_automix", cancel)
    monkeypatch.setattr("sys.argv", ["podcast-automix"])

    with pytest.raises(SystemExit) as stopped:
        cli.main()

    assert stopped.value.code == 130
    assert "Cancelled." in output.getvalue()
    assert "Complete." not in output.getvalue()
