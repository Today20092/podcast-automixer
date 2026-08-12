---
id: 010
title: Fix cross-platform interactive path input
status: done
priority: high
triage: ready-for-agent
assignee: codex-ticket-010
---

## Problem

The no-argument interactive flow reparses three dropped or pasted paths with a PowerShell-oriented grammar. It does not understand POSIX backslash escaping, so a macOS or Linux path such as `/Users/me/My\ Recording.wav` is split into multiple inputs. It also consumes literal backticks that may legally appear in filenames.

## Scope

Replace the ambiguous one-line parser with an application-owned cross-platform input contract, preferably prompting for exactly one WAV path at a time. Normalize only a single matching pair of outer quotes before converting each value to the host platform's `Path`. Preserve the existing direct CLI argument behavior.

## Acceptance criteria

- [x] The interactive flow accepts exactly three paths without applying one shell's tokenization rules to another platform.
- [x] Paths containing spaces, Unicode, apostrophes, double quotes, literal backticks, and trailing backslashes are either preserved or rejected with a clear retry message.
- [x] Windows drive-letter and UNC paths, macOS paths, and Linux paths have focused host-independent lexical tests using `PureWindowsPath` or `PurePosixPath` where appropriate.
- [x] Malformed or empty interactive input produces a concise user-facing error and permits retry instead of exposing a traceback.
- [x] Direct positional CLI arguments continue to accept shell-tokenized paths unchanged.

## Verification

Run the focused CLI tests plus `uv run pytest -q`, `uv run ruff check .`, and `uv run ruff format --check .` on the supported platforms.

## Log

- 2026-08-11: Created from the cross-platform path, terminal drag/drop, and uv audit.
- 2026-08-11: Claimed by codex-ticket-010 for implementation.
- 2026-08-11: Implemented three single-path prompts with retry-safe validation and host-independent lexical coverage. Verification: `uv run pytest -q` (42 passed), `uv run ruff check .` (passed), and focused `uv run ruff format --check src/podcast_automixer/cli.py tests/test_cli.py` (passed). Repository-wide format check remains blocked by pre-existing formatting in `src/podcast_automixer/core.py` and unrelated portions of `tests/test_core.py`.
