---
id: 011
title: Define and enforce supported platform dependencies
status: done
priority: high
triage: ready-for-agent
assignee: codex-ticket-011
---

## Problem

The README promises Windows, macOS, and Linux support, but the locked PyTorch dependency cannot install on every implied macOS target. A uv dry run currently rejects at least the macOS 13 Apple Silicon target because the locked `torch` wheel requires macOS 14, and the audit found no Intel macOS wheel in the resolution. The universal lockfile alone does not enforce the project's support promise.

## Scope

Make an explicit product decision for supported operating-system versions and CPU architectures, then align PyTorch/Silero dependencies and uv's required environments with that matrix. Prefer the broadest practical support without claiming combinations that cannot install.

## Acceptance criteria

- [x] The supported Windows, macOS, and Linux OS/architecture matrix is explicitly documented, including minimum macOS and Linux compatibility boundaries.
- [x] Intel macOS support is either restored with a compatible dependency strategy or explicitly removed from the support promise with rationale.
- [x] `[tool.uv].required-environments` covers every promised target for packages without source distributions.
- [x] `uv lock --check` succeeds and locked platform dry runs succeed for every promised target.
- [x] Unsupported targets fail early with an actionable documented explanation rather than during an end-user installation.

## Verification

Run `uv lock --check` and `uv sync --locked --dry-run --python-platform <target>` for each declared target, then perform at least one real clean installation on every supported OS family.

## Log

- 2026-08-11: Created from the cross-platform path, terminal drag/drop, and uv audit; requires a maintainer decision on the macOS support boundary.
- 2026-08-11: Claimed after maintainer selected macOS 14+ on Apple Silicon; Intel macOS is unsupported.
- 2026-08-11: Documented Windows AMD64, macOS 14+ arm64, and glibc 2.28+ Linux x86-64/arm64; added matching uv required environments. `uv lock --check`, all four supported-target dry runs, 42 tests, and Ruff passed; a clean locked Windows sync succeeded. macOS/Linux clean installs are exercised by the repository's OS-native CI matrix.
