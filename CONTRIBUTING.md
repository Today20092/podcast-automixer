# Contributing to Podcast Automixer

Thanks for helping improve Podcast Automixer. Contributions work best when they begin with a shared, sufficiently detailed GitHub Issue.

## Choose work

- Browse issues labelled [`ready-for-agent`](https://github.com/Today20092/podcast-automixer/issues?q=is%3Aissue%20state%3Aopen%20label%3Aready-for-agent) for work that is specified well enough to implement independently.
- Issues labelled `ready-for-human` require maintainer judgment, representative listening, design decisions, or access that cannot be delegated safely. Comment if you can provide that input.
- Roadmap issues describe larger outcomes. Claim a scoped child issue rather than implementing an entire roadmap item without coordination.
- Issues in `needs-triage` or `needs-info` are still being defined. Help with evidence or examples, but wait for a ready state before implementing.

Before starting, comment on the issue and wait for assignment or maintainer acknowledgement. This prevents duplicate work. Keep one independently reviewable outcome per pull request.

## Propose work

Use the repository issue forms:

- Bug reports include a reproducible command or workflow, environment, expected and actual behavior, input characteristics, and sanitized logs.
- Feature requests lead with the podcast-production problem, then describe desired behavior and observable acceptance criteria.
- Questions use the question form rather than an implementation pull request.

Do not upload private recordings, personal paths, or other sensitive material. For audio-dependent work, describe a reproducible synthetic fixture or confirm that shared recordings may be redistributed under an appropriate license.

## Develop

Podcast Automixer supports Python 3.11 through 3.13 and uses `uv`.

```bash
uv sync --locked --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

Add or update tests for behavior changes. Preserve synchronized input duration, sample rate, channel layout, and metadata unless the issue explicitly changes those guarantees. Never modify source recordings in place.

## Open a pull request

- Link the issue with `Closes #<number>` when the pull request fully resolves it.
- Explain what changed, why, user impact, and how it was verified.
- Include sanitized before/after evidence for audio, report, or interface changes when useful.
- Keep generated files and unrelated refactors out of the pull request.
- Ensure CI passes on Windows, macOS, and Linux.

Maintainers may ask for a smaller sub-issue or a design decision before accepting a large roadmap contribution. That keeps roadmap outcomes flexible while making implementation work reviewable.
