---
id: 007
title: Calibrate ownership heuristics on representative sessions
status: open
priority: medium
triage: ready-for-human
assignee: null
---

## Problem

The 75th-percentile microphone calibration, 9 dB ambiguity window, 12 dB noise-floor margin, and default Silero thresholds are reasonable heuristics but are not validated against representative podcast recordings.

## Scope

Build an evaluation corpus and compare ownership, overlap preservation, missed utterances, false openings, and audible pumping across parameter combinations.

## Acceptance criteria

- [ ] The corpus covers clean, noisy, reverberant, quiet-speaker, loud-speaker, overlap, laughter, breath, cough, and crosstalk cases.
- [ ] Expected ownership regions are annotated independently of implementation output.
- [ ] Current defaults and candidate settings are scored with documented metrics.
- [ ] Recommended defaults and known tradeoffs are recorded.
- [ ] Calibration behavior for stems with no detected speech is explicitly decided and tested.

## Verification

Publish a repeatable evaluation command and a concise results artifact that supports the selected defaults.

## Log

- 2026-08-11: Created from the audio-analysis audit.
