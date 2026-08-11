---
id: 001
title: Fix gain-envelope hold direction
status: done
priority: critical
triage: ready-for-agent
assignee: ticket_001
---

## Problem

The configured hold expands activity before an event instead of after it. A one-frame event receives excessive look-ahead and no true post-event hold.

## Scope

Correct `make_gain_envelopes` so preroll precedes activity and hold follows activity, while retaining the configured opening and closing smoothing.

## Acceptance criteria

- [x] A one-frame event receives the configured preroll before its frame.
- [x] The event remains fully active for the configured hold after its frame.
- [x] Opening and closing smoothing begin on the intended sides of those regions.
- [x] Boundary behavior at the beginning and end of a file is covered.

## Verification

Add impulse-style tests that assert exact expanded frame ranges for default and non-default settings.

## Log

- 2026-08-11: Created from the audio-analysis audit.
- 2026-08-11: Claimed by ticket_001 for implementation.
- 2026-08-11: Implemented explicit preroll/hold expansion with clipped boundaries; verified with `uv run pytest` (13 passed) and `uv run ruff check .`.
