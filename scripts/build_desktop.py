"""Build the Windows pywebview tracer-bullet executable."""

from pathlib import Path

from PyInstaller.__main__ import run

root = Path(__file__).parents[1]
desktop_ui = root / "src" / "podcast_automixer" / "desktop-ui"
desktop_diagnostics = root / "src" / "podcast_automixer" / "desktop_diagnostics.js"
run(
    [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "Podcast Automixer",
        f"--add-data={desktop_ui};podcast_automixer/desktop-ui",
        f"--add-data={desktop_diagnostics};podcast_automixer",
        "--collect-all",
        "silero_vad",
        "--collect-all",
        "torch",
        "--collect-all",
        "torchaudio",
        "--paths",
        str(root / "src"),
        str(root / "src" / "podcast_automixer" / "desktop.py"),
    ]
)
