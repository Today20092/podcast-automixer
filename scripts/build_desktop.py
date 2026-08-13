"""Build the Windows pywebview tracer-bullet executable."""

from pathlib import Path

from PyInstaller.__main__ import run

root = Path(__file__).parents[1]
run(
    [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "Podcast Automixer",
        f"--add-data={root / 'src' / 'podcast_automixer' / 'desktop.html'};podcast_automixer",
        f"--add-data={root / 'src' / 'podcast_automixer' / 'comparison_playback.js'};podcast_automixer",
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
