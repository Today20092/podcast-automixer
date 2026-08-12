# Podcast Automixer

[![Python](https://img.shields.io/badge/Python-3.11%E2%80%933.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/podcast-automixer?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/podcast-automixer/)
[![CI](https://img.shields.io/github/actions/workflow/status/Today20092/podcast-automixer/ci.yml?branch=main&style=for-the-badge&label=CI)](https://github.com/Today20092/podcast-automixer/actions/workflows/ci.yml)
[![uv](https://img.shields.io/badge/uv-managed-DE5FE9?style=for-the-badge&logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
[![Silero VAD](https://img.shields.io/badge/Silero-VAD-00A67E?style=for-the-badge)](https://github.com/snakers4/silero-vad)
[![WAV output](https://img.shields.io/badge/Output-WAV-7C3AED?style=for-the-badge)](https://github.com/Today20092/podcast-automixer)
[![Offline](https://img.shields.io/badge/Processing-Offline-20232A?style=for-the-badge)](https://github.com/Today20092/podcast-automixer)
[![MIT License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

> **Work in progress:** Podcast Automixer is a free, open-source, cross-platform Python CLI
> for podcast editors. The CLI is published on PyPI; standalone desktop packaging and deeper
> editor or DAW integration are future goals.

Podcast Automixer creates one gently auto-mixed replacement WAV for each synchronized
podcast microphone stem. Active microphones stay at unity while clearly inactive
microphones are smoothly attenuated, reducing bleed and room noise without changing the
timing or length of the recordings.

It is designed as a preparation step between synchronizing a multitrack podcast and
starting the editorial cut. It does not normalize, compress, limit, EQ, transcribe, or
combine the microphones into a finished stereo mix.

## Quick start

Podcast Automixer is currently a command-line app. You need at least two synchronized mono
WAV files—one isolated microphone recording per speaker—with matching sample rate, length,
and bit depth.

1. [Install `uv`](https://docs.astral.sh/uv/getting-started/installation/), then open a new
   terminal window.
2. Install Podcast Automixer:

   ```bash
   uv tool install podcast-automixer
   ```

3. Start the guided workflow:

   ```bash
   podcast-automix
   ```

4. Paste each WAV path when prompted, then press Enter when done (Windows terminals also
   support drag-and-drop).
5. Listen to the new `_auto-mixed.wav` files written beside the originals, and open
   `podcast-automix-report.html` to review what the automixer changed.

The original recordings are never modified. For a 30-second test before processing the
whole recording, run:

```bash
podcast-automix --preview-start 60 --preview-duration 30
```

That example starts one minute into the recording. See [Install](#install) and [Run](#run)
for platform-specific commands, scripted usage, every output, and troubleshooting details.

## Why Podcast Automixer?

I mix podcasts regularly and have not found a free automixer that gives me the practical,
conservative results I want. Good automixing should save repetitive work without making
creative decisions for the editor or locking the workflow to expensive software.

Podcast Automixer is a free and open-source alternative: local, transparent,
cross-platform, and useful before editing begins. The original synchronized tracks remain
untouched, and the replacement files can be inspected before they enter the edit.

## Features

- Automixes two or more synchronized, single-speaker WAV microphone stems.
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

## Gain Smoothing Design

Podcast Automixer uses a continuously retargetable gain envelope: the current gain
smoothly chases the latest active or inactive target instead of jumping directly to it.
This is well suited to speech because the envelope can reverse direction cleanly when a
speaker resumes before a closing transition has finished.

The design follows the transparent target-chasing philosophy demonstrated by Airwindows
[PurestGain](https://github.com/airwindows/airwindows/tree/master/plugins/WinVST/PurestGain),
but it is an independent implementation and does not embed PurestGain code. The timing
model uses standard one-pole coefficients derived from explicit opening and closing
time constants, with sample-level interpolation between analysis frames. Exact-duration
S-curve envelopes are not planned: continuously retargetable Natural/chase smoothing is a
better fit for changing speech decisions.

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

`uv` installs and manages a compatible Python version automatically.

Intel Macs are not supported because the locked PyTorch and torchaudio releases do not
publish compatible Intel macOS wheels. Windows on ARM and Linux distributions using musl
(including Alpine) are also outside the supported matrix. On those systems, dependency
installation may report that no compatible wheel is available; use one of the supported
OS and architecture combinations above.

See [Platform support](docs/platform-support.md) for the dependency-level details.

## Install

First, install `uv` if you do not already have it:

**Windows (PowerShell)**

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS and Linux**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal if the installer asks you to refresh your `PATH`, then install Podcast
Automixer:

```bash
uv tool install podcast-automixer
```

The package is named `podcast-automixer`, and the command it installs is `podcast-automix`.
Confirm the installation with `podcast-automix --help`.

To upgrade later, run `uv tool upgrade podcast-automixer`. To uninstall, run
`uv tool uninstall podcast-automixer`. To try it without permanently installing it, run:

```bash
uvx --from podcast-automixer podcast-automix
```

See the [Podcast Automixer project on PyPI](https://pypi.org/project/podcast-automixer/)
for published versions and package files.

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

For scripting, pass two or more positional arguments and use the quoting rules of the current
shell.
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

Each run writes:

- One `_auto-mixed.wav` replacement beside each input microphone.
- `podcast-automix-report.html`, a self-contained visual report beside the first input.
- `podcast-automix-report.json`, a machine-readable report beside the first input.
- `podcast-automix-diagnostics.csv` beside the first input when `--diagnostics` is supplied.

Run `podcast-automix --help` for the complete command-line reference.

## Roadmap

- [x] Conservative voice-activity-based automixing.
- [x] Timing-identical replacement WAV files for two or more synchronized microphones.
- [x] Preview rendering and advanced command-line settings.
- [x] JSON, HTML, and optional CSV diagnostics.
- [x] Visualize attenuation, gain changes, speaker ownership, overlap, and review moments.
- [ ] Make advanced settings easier to understand, adjust, save, and reuse.
- [ ] Add reusable presets for different rooms, microphones, and podcast styles.
- [x] Support a flexible number of microphone tracks.
- [x] Publish a cross-platform command-line installation through PyPI and `uv`.
- [ ] Ship a standalone desktop experience that does not require a Python tool manager.
- [ ] Explore editor, DAW, or plugin integration without requiring it for basic use.
- [ ] Add more listening tests and real-world podcast fixtures.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv build
```

Release maintainers should follow [the release guide](docs/releasing.md).

## License

Podcast Automixer is free and open-source software licensed under the [MIT License](LICENSE).
