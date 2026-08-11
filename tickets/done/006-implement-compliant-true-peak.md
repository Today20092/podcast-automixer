---
id: 006
title: Implement or accurately label true-peak measurement
status: done
priority: high
triage: ready-for-agent
assignee: ticket_006
---

## Problem

The current 4× generic resampling estimate resets at 10-second chunks and has not been verified against the BS.1770 true-peak filter requirements.

## Scope

Implement continuous, verified true-peak measurement or relabel the result as an estimate until compliance is demonstrated.

## Acceptance criteria

- [x] Filter state is continuous across input chunks.
- [x] Peaks spanning chunk boundaries are measured correctly.
- [x] The implementation meets documented BS.1770 accuracy requirements, or UI and JSON labels explicitly say `estimated`.
- [x] Silent inputs serialize as `null` rather than a non-finite JSON number.

## Verification

Use official or independently verified true-peak test vectors at supported sample rates, including intersample peaks and chunk-boundary cases.

## Log

- 2026-08-11: Created from the audio-analysis audit.
- 2026-08-11: Claimed by ticket_006; implementing a continuous, explicitly estimated peak measurement.
- 2026-08-11: Completed with whole-signal 4x oversampling, explicit estimated labels, boundary and silence regression tests; verified with 18 pytest tests, Ruff, UI typecheck, and UI build.
