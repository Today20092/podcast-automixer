---
id: 014
title: Deepen ownership analysis
status: open
priority: high
triage: ready-for-agent
assignee: null
dependencies: [013]
---

## Problem

Ownership analysis is fragmented across VAD conversion, frame energy, activity classification, and gain-envelope helpers. Its tuple-and-dictionary interface leaks implementation details, and tests depend directly on several internal algorithms.

## Scope

Concentrate ownership decisions and analysis state behind one deep module interface. Keep VAD/model loading and streaming weighting as internal seams, and replace helper-level tests where stable behavior can be tested through the module. Suggested branch: `refactor/014-ownership-analysis`.

## Acceptance criteria

- [ ] Analysis returns one explicit result rather than an unstructured tuple and mutable dictionary.
- [ ] Frame/sample coordinates, calibration, ownership, and gain timing have locality in the module.
- [ ] VAD and audio substitutions remain possible through internal seams without widening the external interface.
- [ ] Behavioral tests cover segmentation, speech boundaries, ownership fallback, and gain timing through the module interface.
- [ ] Existing automix decisions and report values remain compatible.

## Verification

After ticket 013, run focused ownership-analysis tests, `uv run pytest -q`, `uv run ruff check .`, and `uv run ruff format --check .`.

## Log

- 2026-08-11: Created from the architecture review; intended as a separate PR after ticket 013.
