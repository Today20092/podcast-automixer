---
id: 009
title: Clarify envelope time-constant controls
status: done
priority: medium
triage: ready-for-agent
assignee: codex
dependencies: [008]
---

## Problem

The opening and closing settings look like exact transition durations, but Natural/chase
envelopes approach their targets asymptotically. Users need controls and reports that state
this behavior accurately.

## Scope

After ticket 008, describe opening and closing values as time constants throughout CLI
help, advanced prompts, reports, and documentation. Explain the practical 63%, 95%, and
99% response landmarks without exposing unnecessary DSP jargon in the normal workflow.

## Acceptance criteria

- [x] CLI help and advanced prompts identify opening and closing values as time constants.
- [x] JSON and HTML reports label the values consistently.
- [x] The README distinguishes a time constant from an exact-duration fade.
- [x] User-facing wording remains concise and understandable without DSP knowledge.
- [x] Existing command-line options remain backward compatible.

## Verification

Add or update CLI and report tests for the labels, rebuild the report bundle, and run the
full test, lint, UI typecheck, and UI build suites.

## Log

- 2026-08-11: Created as the documentation and interface follow-up to ticket 008.
- 2026-08-11: Claimed by Codex for implementation.
- 2026-08-11: Completed. Verified 31 tests, Ruff lint, report UI typecheck and build;
  rebuilt the packaged report bundle.
