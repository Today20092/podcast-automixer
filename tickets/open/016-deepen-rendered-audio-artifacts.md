---
id: 016
title: Deepen rendered-audio artifacts
status: open
priority: medium
triage: ready-for-agent
assignee: null
dependencies: [013]
---

## Problem

Output naming, collision policy, gain interpolation, audio IO, BEXT preservation, and replacement collectively define a valid rendered artifact but currently span the CLI, renderer, and private RIFF helpers.

## Scope

Place complete rendered-artifact semantics behind one deep local-IO module seam. Keep RIFF parsing and metadata surgery private, and test final artifacts rather than private helpers. Suggested branch: `refactor/016-rendered-audio-artifacts`.

## Acceptance criteria

- [ ] One module owns destination policy, streaming gain application, BEXT preservation and offset, and atomic replacement.
- [ ] Collision policy no longer leaks between the CLI/run module and artifact implementation.
- [ ] Failed writes do not leave partial destination artifacts.
- [ ] Tests inspect final WAV structure, audio values, metadata, preview offsets, and collision behavior through the module interface.
- [ ] Existing output names, formats, subtypes, and metadata behavior remain compatible.

## Verification

After ticket 013, run focused artifact tests, `uv run pytest -q`, `uv run ruff check .`, and `uv run ruff format --check .` on supported platforms.

## Log

- 2026-08-11: Created from the architecture review; intended as a separate PR after ticket 013.
