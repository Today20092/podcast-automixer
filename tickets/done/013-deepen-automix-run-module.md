---
id: 013
title: Deepen the automix run module
status: done
priority: high
triage: ready-for-agent
assignee: codex-ticket-013
dependencies: []
---

## Problem

`cli.main` owns input validation, preview and overwrite policy, analysis, rendering, loudness measurement, and report creation. The CLI and renderer both know output-collision rules, and no test exercises the complete run outcome.

## Scope

Move the complete non-interactive run policy behind one deep module seam. Keep terminal prompting and presentation in the CLI adapter, absorb shallow output-path logic, and preserve current command behavior. Suggested branch: `refactor/013-automix-run-module`.

## Acceptance criteria

- [x] The CLI adapter delegates one complete automix run through a single module interface.
- [x] Preview validation, overwrite policy, sequencing, artifacts, and error modes have locality in the run module.
- [x] Progress reporting remains replaceable without leaking terminal concerns into the implementation.
- [x] Tests cover successful full and preview runs, refusal to overwrite, and failure without partial artifacts.
- [x] Existing CLI behavior and output names remain compatible.

## Verification

Run the focused run/CLI tests, `uv run pytest -q`, `uv run ruff check .`, and `uv run ruff format --check .`.

## Log

- 2026-08-11: Completed the run module seam and verified 49 tests, Ruff lint, Ruff format, and `git diff --check`.
- 2026-08-11: Claimed by codex-ticket-013 on `refactor/013-automix-run-module`.

- 2026-08-11: Created from the architecture review; implement first as the external seam for tickets 014–016.
