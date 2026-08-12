---
id: 014
title: Deepen ownership analysis
status: done
priority: high
triage: ready-for-agent
assignee: codex-ticket-014
dependencies: [013]
---

## Problem

Ownership analysis is fragmented across VAD conversion, frame energy, activity classification, and gain-envelope helpers. Its tuple-and-dictionary interface leaks implementation details, and tests depend directly on several internal algorithms.

## Scope

Concentrate ownership decisions and analysis state behind one deep module interface. Keep VAD/model loading and streaming weighting as internal seams, and replace helper-level tests where stable behavior can be tested through the module. Suggested branch: `refactor/014-ownership-analysis`.

## Acceptance criteria

- [x] Analysis returns one explicit result rather than an unstructured tuple and mutable dictionary.
- [x] Frame/sample coordinates, calibration, ownership, and gain timing have locality in the module.
- [x] VAD and audio substitutions remain possible through internal seams without widening the external interface.
- [x] Behavioral tests cover segmentation, speech boundaries, ownership fallback, and gain timing through the module interface.
- [x] Existing automix decisions and report values remain compatible.

## Verification

After ticket 013, run focused ownership-analysis tests, `uv run pytest -q`, `uv run ruff check .`, and `uv run ruff format --check .`.

## Log

- 2026-08-11: Created from the architecture review; intended as a separate PR after ticket 013.
- 2026-08-11: Claimed by codex-ticket-014 on `refactor/014-ownership-analysis`.
- 2026-08-11: Added `AnalysisResult`, preserving report values while concentrating ownership decisions and frame/sample coordinates behind `analyze`.
- 2026-08-11: Verified with `uv run pytest -q` (49 passed), `uv run ruff check .`, `uv run ruff format --check .`, and `git diff --check`.
