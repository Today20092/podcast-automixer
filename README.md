# Podcast Automixer

[![Python](https://img.shields.io/badge/Python-3.11%E2%80%933.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-managed-DE5FE9?style=for-the-badge&logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
[![Silero VAD](https://img.shields.io/badge/Silero-VAD-00A67E?style=for-the-badge)](https://github.com/snakers4/silero-vad)
[![WAV output](https://img.shields.io/badge/Output-WAV-7C3AED?style=for-the-badge)](https://github.com/Today20092/podcast-automixer)
[![Offline](https://img.shields.io/badge/Processing-Offline-20232A?style=for-the-badge)](https://github.com/Today20092/podcast-automixer)

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
