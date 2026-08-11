---
id: 002
title: Make energetic fallback reference-consistent
status: done
priority: critical
triage: ready-for-agent
assignee: ticket_002
---

## Problem

The energetic fallback compares calibrated leader levels with uncalibrated noise floors and applies the noisiest track's threshold to every stem.

## Scope

Evaluate energy above noise floor per track in one consistent level reference, then combine that evidence with ownership plausibility.

## Acceptance criteria

- [x] Every threshold comparison uses values in the same calibrated or uncalibrated reference.
- [x] A noisy stem cannot suppress energetic events on cleaner stems.
- [x] VAD-missed speech-like sounds can activate their plausible owning stem.
- [x] Noise-only frames remain inactive.

## Verification

Add synthetic three-stem tests with unequal gains, unequal noise floors, an energetic non-VAD event, and noise-only controls.

## Log

- 2026-08-11: Created from the audio-analysis audit.
- 2026-08-11: Claimed by ticket_002; implementation started.
- 2026-08-11: Implemented per-stem calibrated noise-floor comparisons and synthetic
  three-stem regression coverage. Verified with `uv run pytest` (12 passed),
  `uv run ruff check .`, and `git diff --check`.
