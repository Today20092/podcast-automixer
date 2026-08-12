# Podcast Automixer

[![Python](https://img.shields.io/badge/Python-3.11%E2%80%933.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-managed-DE5FE9?style=for-the-badge&logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
[![Silero VAD](https://img.shields.io/badge/Silero-VAD-00A67E?style=for-the-badge)](https://github.com/snakers4/silero-vad)
[![WAV output](https://img.shields.io/badge/Output-WAV-7C3AED?style=for-the-badge)](https://github.com/Today20092/podcast-automixer)
[![Offline](https://img.shields.io/badge/Processing-Offline-20232A?style=for-the-badge)](https://github.com/Today20092/podcast-automixer)
[![MIT License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

> **Work in progress:** Podcast Automixer is becoming a free, open-source, cross-platform
> automixing tool for podcast editors. The current version is a standalone Python CLI;
> easier standalone packaging and deeper editor or DAW integration are future goals.

Podcast Automixer creates one gently auto-mixed replacement WAV for each synchronized
podcast microphone stem. Active microphones stay at unity while clearly inactive
microphones are smoothly attenuated, reducing bleed and room noise without changing the
timing or length of the recordings.

It is designed as a preparation step between synchronizing a multitrack podcast and
starting the editorial cut. It does not normalize, compress, limit, EQ, transcribe, or
combine the microphones into a finished stereo mix.

## Why Podcast Automixer?

I mix podcasts regularly and have not found a free automixer that gives me the practical,
conservative results I want. Good automixing should save repetitive work without making
creative decisions for the editor or locking the workflow to expensive software.

Podcast Automixer is a free and open-source alternative: local, transparent,
cross-platform, and useful before editing begins. The original synchronized tracks remain
untouched, and the replacement files can be inspected before they enter the edit.

## Features

- Automixes three synchronized, single-speaker WAV microphone stems.
- Keeps active microphones at unity gain.
- Smoothly attenuates microphones that are clearly inactive.
- Preserves input duration, synchronization, sample rate, and channel layout.
- Preserves Broadcast Wave time-reference metadata when available.
- Processes audio locally and offline.
- Never silently overwrites existing output files.
- Supports short preview renders before processing the full recording.
- Provides optional advanced automixing controls.
- Produces JSON and self-contained HTML reports.
- Can export frame-level activity and gain diagnostics as CSV.

## Recommended Editing Workflow

Opening and closing controls are time constants, not exact fade durations. Each value
reaches about 63% of a gain change; roughly 95% takes three times the value and 99% takes
five times the value.

Use Podcast Automixer after the podcast has been recorded and synchronized, but before
cutting or otherwise editing the program:

1. Import the camera and audio recordings into your editor.
2. Synchronize everything and place each speaker's microphone on its own aligned track.
3. Before making cuts, export or locate the synchronized full-length microphone WAV files.
4. Run Podcast Automixer on those microphone stems.
5. Review the reports and listen to the generated `_auto-mixed.wav` files.
6. Replace each original microphone stem with its matching auto-mixed replacement.
7. Confirm that the replacement tracks remain perfectly synchronized, then link audio and
   video where appropriate.
8. Continue editing, adjusting levels, applying processing, and building the final mix.

The tool currently produces one replacement file per microphone—not one combined master
file. Each replacement is intended to line up exactly with its corresponding original.

## Requirements

- Python 3.11-3.13 on a supported platform:

  | Operating system | CPU architecture | Minimum version |
  | --- | --- | --- |
  | Windows | x86-64 (AMD64) | Windows 10 |
  | macOS | Apple Silicon (arm64) | macOS 14 Sonoma |
  | Linux | x86-64 or arm64 | glibc 2.28 |

- [uv](https://docs.astral.sh/uv/)

## Run

With no positional arguments, the interactive workflow asks for one WAV path at a time:

```bash
podcast-automix
```

Paste each path exactly as it appears in the file manager. One matching pair of surrounding
quotes is accepted. File Explorer drag-and-drop is supported in non-elevated PowerShell and
Command Prompt terminals; terminal drag-and-drop is not advertised on macOS or Linux because
shells may insert escape characters. On those systems, paste or type the unescaped path at
each prompt instead.

For scripting, pass three positional arguments and use the quoting rules of the current shell.
These examples all include paths containing spaces:

**Windows (PowerShell)**

```powershell
podcast-automix "C:\Audio Files\A01.wav" "C:\Audio Files\A02.wav" "C:\Audio Files\A03.wav"
```

**Windows (Command Prompt)**

```batch
podcast-automix "C:\Audio Files\A01.wav" "C:\Audio Files\A02.wav" "C:\Audio Files\A03.wav"
```

**macOS (zsh)**

```bash
podcast-automix '/Users/me/Audio Files/A01.wav' '/Users/me/Audio Files/A02.wav' '/Users/me/Audio Files/A03.wav'
```

**Linux (bash)**

```bash
podcast-automix '/home/me/Audio Files/A01.wav' '/home/me/Audio Files/A02.wav' '/home/me/Audio Files/A03.wav'
```

Use `--` before positional arguments when a relative filename begins with `-`. Relative paths
are resolved from the terminal's current working directory. Symbolic links are resolved before
processing, so outputs are written beside the link target, not beside the symlink. Outputs use
the `_auto-mixed.wav` suffix, and existing files are never silently replaced. Use
`--preview-start 60 --preview-duration 30` for a short preview and `--advanced` to expose tuning
controls.

Add `--diagnostics` to write a frame-level CSV containing microphone activity decisions
and applied gain. Self-contained HTML and machine-readable JSON reports are always produced.

## Roadmap

- [x] Conservative voice-activity-based automixing.
- [x] Timing-identical replacement WAV files for three synchronized microphones.
- [x] Preview rendering and advanced command-line settings.
- [x] JSON, HTML, and optional CSV diagnostics.
- [ ] Expand the visual report to show when and how every microphone was attenuated.
- [ ] Add interactive views for activity, gain changes, overlap, and crosstalk.
- [ ] Make advanced settings easier to understand, adjust, save, and reuse.
- [ ] Add reusable presets for different rooms, microphones, and podcast styles.
- [ ] Support a flexible number of microphone tracks.
- [ ] Improve cross-platform installation and ship a standalone desktop experience.
- [ ] Explore editor, DAW, or plugin integration without requiring it for basic use.
- [ ] Add more listening tests and real-world podcast fixtures.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## License

Podcast Automixer is free and open-source software licensed under the [MIT License](LICENSE).
