---
id: 004
title: Use sample-accurate VAD timestamps
status: done
priority: high
triage: ready-for-agent
assignee: ticket_004
---

## Problem

Silero timestamps requested in seconds use one-decimal-place resolution by default, quantizing VAD boundaries to roughly 100 ms while ownership frames are 20 ms.

## Scope

Request sample timestamps from Silero and map the 16 kHz coordinates deterministically onto analysis frames.

## Acceptance criteria

- [x] VAD boundaries are derived from sample coordinates rather than rounded seconds.
- [x] Start uses floor semantics and end uses ceiling semantics without dropping speech.
- [x] Partial final frames map correctly.
- [x] Existing Silero padding and silence behavior remains explicit.

## Verification

Add adapter tests for boundaries that do not land on 20 ms or 100 ms intervals.

## Log

- 2026-08-11: Created from the audio-analysis audit.
- 2026-08-11: Claimed by ticket_004; implementation started.
- 2026-08-11: Implemented integer sample-coordinate mapping with outward rounding,
  explicit Silero padding/silence settings, and partial-frame adapter coverage.
- 2026-08-11: Verified with `uv run pytest` (18 passed),
  `uv run ruff check .`, and scoped diff review; closed.
