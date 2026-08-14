import re
import shutil
import subprocess
from contextlib import suppress
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from podcast_automixer.desktop import DesktopBridge
from podcast_automixer.diagnostics import DesktopDiagnostics, diagnostics_directory, redact_paths


def test_desktop_inline_scripts_parse() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to validate the desktop renderer")
    renderer = (
        Path(__file__).parents[1] / "src" / "podcast_automixer" / "desktop.html"
    ).read_text(encoding="utf-8")
    scripts = re.findall(r"<script>([\s\S]*?)</script>", renderer)
    assert scripts
    for script in scripts:
        subprocess.run(
            [node, "--check", "-"], input=script, text=True, check=True, capture_output=True
        )


def test_diagnostics_use_local_app_data_and_redact_complete_paths(monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\Ada\AppData\Local")
    assert diagnostics_directory() == (
        Path(r"C:\Users\Ada\AppData\Local") / "Podcast Automixer" / "Logs"
    )
    assert redact_paths(r"failed at C:\Users\Ada\Recordings\episode.wav") == (
        "failed at <redacted>/episode.wav"
    )
    assert redact_paths("failed at /home/ada/exports/mix.wav") == "failed at <redacted>/mix.wav"


def test_rotating_session_log_captures_python_and_javascript_errors(tmp_path: Path) -> None:
    diagnostics = DesktopDiagnostics(tmp_path, version="test")
    bridge = DesktopBridge(diagnostics=diagnostics)
    bridge.report_javascript_error("uncaught_error", r"at C:\Users\Ada\Recordings\episode.wav")
    with suppress(ValueError):
        bridge.inspect_recording_set(["bad.mp3"])
    contents = (tmp_path / "desktop.log").read_text(encoding="utf-8")
    assert "session_start version=test" in contents
    assert "javascript_error kind=uncaught_error" in contents
    assert "operation_failed operation=inspect_recording_set" in contents
    assert "Traceback" in contents
    assert "episode.wav" in contents
    assert r"C:\Users\Ada\Recordings" not in contents


def test_diagnostics_rotation_is_bounded(tmp_path: Path) -> None:
    diagnostics = DesktopDiagnostics(tmp_path)
    handler = diagnostics.logger.handlers[0]
    assert isinstance(handler, RotatingFileHandler)
    handler.maxBytes = 50
    handler.backupCount = 1
    diagnostics.log("x" * 100)
    diagnostics.log("y" * 100)
    assert len(list(tmp_path.glob("desktop.log*"))) <= 2


def test_desktop_renderer_reports_javascript_failures_and_exposes_log_folder_action() -> None:
    source = Path(__file__).parents[1] / "src" / "podcast_automixer"
    renderer = (source / "desktop.html").read_text(encoding="utf-8")
    folder_action = (source / "desktop_diagnostics.js").read_text(encoding="utf-8")
    assert "unhandledrejection" in renderer
    assert "uncaught_error" in renderer
    assert "const rawApi=window.pywebview?.api" not in renderer
    assert "window.pywebview?.api?.[name]" in renderer
    assert "open_diagnostics_folder" in folder_action
    assert "Open diagnostics folder" in folder_action
