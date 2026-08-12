---
id: 017
title: Optimize and expose post-render loudness analysis
status: done
priority: high
triage: ready-for-agent
assignee: codex
working_branch: codex/ticket-017-loudness-progress
---

## Problem

After the rendering progress reaches 100%, the CLI performs a separate loudness-analysis pass without displaying any status. For an approximately 83-minute, three-track session, this appeared to be a hang and was interrupted with `Ctrl+C` inside `_StreamingMeter._consume_short_term`, so the report and final completion output were never produced.

The pass analyzes every rendered stem plus the virtual mono program. Its rolling loudness windows repeatedly slice NumPy arrays, while true-peak measurement retains every audio chunk and later concatenates and oversamples the entire recording. Long sessions can therefore require substantial time and several gigabytes of memory after rendering appears complete.

## Scope

Make post-render loudness analysis use bounded audio-sample memory and remain efficient for long recordings while preserving the existing ITU-R BS.1770 / EBU R 128 measurements. Compact 10 Hz measurement distributions and the requested 1 Hz report timeline necessarily scale with duration; full-rate audio buffers must not. Add visible CLI progress for the entire post-render phase, including stem/program measurement and any final true-peak work, so reaching 100% corresponds to actual completion.

Use streaming or bounded-window calculations instead of retaining full recordings or repeatedly copying large rolling buffers. Keep output schema and measurement semantics compatible unless a standards-correctness change is explicitly documented and tested.

## Acceptance criteria

- [x] The CLI visibly labels and reports progress throughout post-render loudness analysis.
- [x] Rendering at 100% is not presented as overall completion while loudness analysis is still running.
- [x] Loudness analysis uses bounded audio-sample memory with respect to recording duration, including estimated true-peak measurement; only compact measurement distributions and report output may scale with duration.
- [x] Rolling momentary and short-term window processing avoids repeated large-buffer slicing or equivalent avoidable copying.
- [x] Each rendered stem and the virtual mono program are still measured.
- [x] Integrated loudness, maximum momentary loudness, maximum short-term loudness, loudness range, estimated true peak, and the short-term timeline remain covered by regression tests.
- [x] Chunk-boundary behavior remains equivalent to processing the same audio as one continuous stream.
- [x] A long-duration synthetic benchmark or regression test demonstrates materially improved runtime and bounded memory without requiring a full podcast fixture.
- [x] Cancellation during loudness analysis exits cleanly without a misleading success message or partially finalized report.

## Verification

Verified with `uv run pytest -q` (64 passed), `uv run ruff check src tests`, and `uv run ty check src tests`. The 480-second benchmark and duration-scaling measurements are recorded below. CLI regressions confirm monotonic post-render progress through meter finalization and cancellation with exit code 130, no success message, and cleanup of newly created artifacts.

## Log

- 2026-08-12: Created from a reported 4,992.921-second, three-track run that was interrupted during the unreported post-render loudness phase.
- 2026-08-12: Claimed by Codex on `codex/ticket-017-loudness-progress`.
- 2026-08-12: A repeatable 480-second, 48 kHz synthetic meter benchmark improved from 4.023 seconds on `main` to 1.539 seconds on this branch (62% faster). Python peak allocations were 28.25 MiB and 30.39 MiB respectively; duration scaling on this branch remained effectively flat from 30.04 MiB at 60 seconds to 30.37 MiB at 480 seconds. The regression test exercises the streaming true-peak path and requires peak growth from 60 to 600 seconds at 8 kHz to remain below 1 MiB.
- 2026-08-12: Completed implementation and two-axis review; standards and ticket-spec reviews reported no findings.
