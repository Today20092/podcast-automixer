---
id: 015
title: Deepen the report module
status: open
priority: high
triage: ready-for-agent
assignee: null
dependencies: [013]
---

## Problem

Report meaning and calculations are spread across the analysis dictionary, CLI mutation, JSON writer, HTML payload builder, diagnostics writer, and TypeScript consumer. Gain and ownership calculations are duplicated, so formats can drift.

## Scope

Create one internal report model that owns facts and derived insights. Make JSON, HTML, and diagnostics thin adapters and preserve the current serialized formats unless a deliberate migration is documented. Suggested branch: `refactor/015-report-module`.

## Acceptance criteria

- [ ] Units, nullability, names, and derived calculations have locality in one report module.
- [ ] JSON, HTML, and diagnostics consume the same report model without duplicated gain or ownership math.
- [ ] The report UI's consumed shape is explicit and checked against the produced payload.
- [ ] Contract tests cover the report interface; format adapters have focused serialization tests.
- [ ] Existing user-visible report content remains compatible.

## Verification

After ticket 013, run report tests, `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, and the report UI typecheck/build.

## Log

- 2026-08-11: Created from the architecture review; intended as a separate PR after ticket 013 and may precede ticket 014.
