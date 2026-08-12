from pathlib import PurePosixPath, PureWindowsPath

import pytest

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


def test_direct_cli_path_is_not_reparsed(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = "literal ` 'quoted' path.wav"
    parsed = cli.parser().parse_args([raw])

    assert parsed.files == [cli._path(raw)]


def test_direct_cli_accepts_filename_beginning_with_dash_after_separator() -> None:
    parsed = cli.parser().parse_args(["--", "-one.wav", "two.wav", "three.wav"])

    assert [path.name for path in parsed.files] == ["-one.wav", "two.wav", "three.wav"]
