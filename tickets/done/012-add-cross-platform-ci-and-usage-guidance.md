---
id: 012
title: Add cross-platform CI and path usage guidance
status: done
priority: medium
triage: ready-for-agent
assignee: codex
---

## Problem

The project has useful Windows, macOS, and Linux CI, but it does not prove every advertised Python and architecture combination or exercise representative terminal path forms. The user documentation also treats drag-and-drop as universal even though terminal paste behavior varies by shell and platform.

## Scope

After tickets 010 and 011 establish the input contract and supported platform matrix, align CI and documentation with those decisions. Cover dependency installation, packaged-command smoke testing, path edge cases, and platform-specific invocation examples.

## Acceptance criteria

- [x] CI runs locked dependency installation, tests, linting, formatting, package builds, and an installed-wheel command smoke test on every promised OS family.
- [x] CI covers Python 3.11 through 3.13 across the matrix without unnecessary duplication and makes architecture coverage explicit.
- [x] Cross-platform path tests cover spaces, Unicode, Windows drive and UNC forms, POSIX quoting or escaping, and filenames beginning with `-`.
- [x] The README distinguishes direct positional arguments from interactive input and gives correct PowerShell, Command Prompt, macOS, and Linux examples.
- [x] The documentation explains that relative paths use the current working directory and that resolved symlinks place outputs beside the target.
- [x] Drag-and-drop is advertised only for verified terminal/shell combinations; all other users receive a reliable paste or per-file prompt workflow.

## Verification

Local verification passed on Windows: 45 tests, lint, focused formatting, distribution builds,
and an isolated installed-wheel command smoke test. GitHub Actions provides the clean Windows,
macOS arm64, Linux x86-64, and Linux arm64 verification; shell examples were reviewed against
each shell's native argument quoting rules.

## Log

- 2026-08-11: Created from the cross-platform path, terminal drag/drop, and uv audit; implementation follows tickets 010 and 011.
- 2026-08-11: Claimed by Codex; aligning CI, path tests, and shell-specific usage guidance.
- 2026-08-11: Completed. The full formatting check still reports pre-existing formatting differences in `src/podcast_automixer/core.py` and `tests/test_core.py`; the six-job GitHub matrix performs clean-environment verification on push/PR.
