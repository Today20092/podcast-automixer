---
id: 016
title: Deepen rendered-audio artifacts
status: done
priority: medium
triage: ready-for-agent
assignee: codex-ticket-016
dependencies: [013]
---

## Problem

Output naming, collision policy, gain interpolation, audio IO, BEXT preservation, and replacement collectively define a valid rendered artifact but currently span the CLI, renderer, and private RIFF helpers.

## Scope

Place complete rendered-artifact semantics behind one deep local-IO module seam. Keep RIFF parsing and metadata surgery private, and test final artifacts rather than private helpers. Suggested branch: `refactor/016-rendered-audio-artifacts`.

## Acceptance criteria

- [x] One module owns destination policy, streaming gain application, BEXT preservation and offset, and atomic replacement.
- [x] Collision policy no longer leaks between the CLI/run module and artifact implementation.
- [x] Failed writes do not leave partial destination artifacts.
- [x] Tests inspect final WAV structure, audio values, metadata, preview offsets, and collision behavior through the module interface.
- [x] Existing output names, formats, subtypes, and metadata behavior remain compatible.

## Verification

After ticket 013, run focused artifact tests, `uv run pytest -q`, `uv run ruff check .`, and `uv run ruff format --check .` on supported platforms.

## Log

- 2026-08-11: Created from the architecture review; intended as a separate PR after ticket 013.
- 2026-08-11: Claimed by codex-ticket-016 on `refactor/016-rendered-audio-artifacts`.
- 2026-08-11: Added `RenderedAudioArtifacts` as the destination/collision/rendering seam, with same-directory temporary WAVs and atomic replacement after BEXT preservation.
- 2026-08-11: Verified focused artifact/run tests (7 passed), full suite (51 passed), `uv run ruff check .`, `uv run ruff format --check .`, and `git diff --check`.
