# Podcast Automixer

Creates one gently auto-mixed replacement WAV for each of three synchronized podcast
microphone stems. Active microphones stay at unity; clearly inactive microphones are
smoothly attenuated. It does not normalize, compress, limit, EQ, or transcribe.

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
