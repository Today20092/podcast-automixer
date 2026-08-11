---
id: 005
title: Make loudness range EBU-compliant
status: done
priority: high
triage: ready-for-agent
assignee: ticket_005
---

## Problem

Loudness Range currently samples 3-second short-term windows once per second. Current EBU Tech 3342 requires at least 10 Hz sampling with at least 2.9 seconds of overlap.

## Scope

Calculate the LRA distribution from 3-second K-weighted windows at 100 ms intervals while retaining a suitably reduced timeline for the report UI if needed.

## Acceptance criteria

- [x] LRA uses 3-second windows at 10 Hz or faster.
- [x] The −70 LUFS absolute gate and −20 LU relative gate remain correct.
- [x] LRA uses the gated 10th and 95th percentiles.
- [x] Report payload size stays reasonable for long episodes.

## Verification

Match `pyloudnorm.Meter.loudness_range` within 0.1 LU across stationary, stepped, rapidly varying, short, and silent fixtures.

## Log

- 2026-08-11: Created from the audio-analysis audit.
- 2026-08-11: Claimed by ticket_005; implementation started.
- 2026-08-11: Implemented 10 Hz LRA sampling with EBU gating and percentiles while
  retaining the report timeline at 1 Hz. Verified against pyloudnorm fixtures and with
  `uv run pytest -q` (22 passed) plus `uv run ruff check .`.
