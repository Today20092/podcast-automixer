# Retirement inventory

Podcast Automixer is retired as of October 10, 2026. All future development is in
[CleanSlate / Podcast Bleed Reducer](https://github.com/Today20092/podcast-bleed-reducer),
the replacement application written in Rust.

## What we made

- A Python audio-processing engine with input validation, Silero speech detection,
  microphone ownership heuristics, smooth gain envelopes, preview renders, and
  individual processed WAVs. It preserves synchronization and Broadcast Wave metadata.
- The `podcast-automixer` package and `podcast-automix` command-line app, with guided
  and scripted workflows.
- The `podcast-automix-desktop` Python desktop launcher, desktop bridge, and desktop
  interface work.
- Loudness measurement, JSON and self-contained HTML reports, CSV diagnostics,
  and a React/TypeScript report interface bundled into the Python package.
- Tests, CI, package builds, PyInstaller packaging work, and PyPI trusted publishing.
- Architecture and audio research, platform and release guidance, and a video walkthrough.
- Unfinished workstation, waveform-preview, distribution, calibration, and editor/DAW
  integration work. Local drafts and experimental interfaces are also retired.

## Published artifacts

- [GitHub repository](https://github.com/Today20092/podcast-automixer).
- [PyPI package](https://pypi.org/project/podcast-automixer/), with versions `0.1.0`,
  `0.1.1`, `0.1.2`, and `0.2.0`. Latest published version: `0.2.0`.
- [GitHub releases](https://github.com/Today20092/podcast-automixer/releases):
  `v0.1.2` and `v0.2.0`.
- Report-interface metadata declares a private package, not a public npm package.
- No GitHub Pages site was found through the repository Pages API.

## Retirement actions

The README and package metadata point to CleanSlate and declare this project inactive.
Automatic PyPI publishing is removed. Release instructions are historical. The issue
chooser directs visitors to the replacement. Old roadmap issues are abandoned, and
the repository is intended to remain archived as a historical reference.

The following open roadmap issues were identified for closure as not planned:
#19, #20, #21, #22, #23, #24, #25, #26, #35, #43, #44, #51, and #65.

PyPI retirement requires access to the owner's project settings. Archive the package
there and remove its trusted publisher. Repository metadata edits do not change
already uploaded distribution metadata. Keep historical versions available rather
than deleting the package name or replacing it with an empty package.

Local checkouts and experiments can be removed separately. Neither local deletion
nor GitHub archival updates PyPI. Old audio outputs remain the user's files.
