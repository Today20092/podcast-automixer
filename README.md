# Podcast Automixer

[![Python 3.11–3.13](https://img.shields.io/badge/python-3.11%E2%80%933.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/managed%20with-uv-DE5FE9?logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/badge/code%20style-Ruff-D7FF64?logo=ruff&logoColor=261230)](https://docs.astral.sh/ruff/)
[![GitHub repository](https://img.shields.io/badge/GitHub-podcast--automixer-181717?logo=github)](https://github.com/Today20092/podcast-automixer)

Creates one gently auto-mixed replacement WAV for each of three synchronized podcast
microphone stems. Active microphones stay at unity; clearly inactive microphones are
smoothly attenuated. It does not normalize, compress, limit, EQ, or transcribe.

## Requirements

- Python 3.11–3.13
- [uv](https://docs.astral.sh/uv/)

## Run

```powershell
uv sync
uv run podcast-automix
```

Drag three WAV files into the terminal when prompted (Windows pastes their paths), or:

```powershell
uv run podcast-automix path\to\A01.wav path\to\A02.wav path\to\A03.wav
```

Outputs are written beside each input with `_auto-mixed.wav`. Existing outputs are never
silently replaced. Use `--preview-start 60 --preview-duration 30` for a short preview and
`--advanced` to expose tuning controls.

Add `--diagnostics` to write a frame-level CSV containing microphone activity decisions
and applied gain. Self-contained HTML and machine-readable JSON reports are always produced.

## Development

```powershell
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
