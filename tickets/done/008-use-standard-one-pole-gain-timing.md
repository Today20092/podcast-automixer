---
id: 008
title: Use standard one-pole gain timing
status: done
priority: high
triage: ready-for-agent
assignee: codex-ticket-008
dependencies: []
---

## Problem

Gain smoothing currently uses `alpha = frame_ms / smoothing_ms`. This is a useful
approximation, but its response changes with analysis-frame size and the configured times
do not have a precise, standard time-constant meaning.

## Scope

Derive independent opening and closing coefficients with
`alpha = 1 - exp(-frame_seconds / time_constant_seconds)`. Preserve the existing
target-chasing behavior, linear-amplitude gain targets, preroll, hold, and sample-level
interpolation during rendering.

## Acceptance criteria

- [x] Opening and closing coefficients use the standard exponential one-pole formula.
- [x] Equivalent time constants produce equivalent envelopes across supported frame sizes.
- [x] An envelope can reverse direction smoothly from its current value when retargeted.
- [x] Unity and configured attenuation targets remain unchanged.
- [x] Existing preroll, hold, boundary, and interpolation behavior remains covered.

## Verification

Add numerical envelope tests for multiple frame sizes and compare selected points against
the closed-form one-pole response within an explicit tolerance. Run the full test and lint
suites.

## Log

- 2026-08-11: Created after approving the PurestGain-style Natural/chase design direction.
- 2026-08-11: Claimed by codex-ticket-008 for implementation.
- 2026-08-11: Implemented exponential one-pole opening/closing coefficients and numerical
  envelope coverage at 10 ms and 20 ms frame sizes, including smooth retargeting.
- 2026-08-11: Verified `uv run pytest tests/test_core.py -q` (23 passed),
  `uv run pytest -q` (29 passed), and `uv run ruff check .` (passed). The required
  `uv run ruff format --check .` remains blocked by pre-existing formatting drift in
  `src/podcast_automixer/core.py` and `tests/test_core.py`; both HEAD versions also fail.
