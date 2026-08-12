# Issue tracker: local Markdown

Issues and specs live under `tickets/`. Each ticket is one Markdown file whose directory is its workflow state:

- `tickets/open/`: available work
- `tickets/in-progress/`: claimed work
- `tickets/done/`: completed or declined work

## Ticket format

Use a zero-padded numeric ID and slug: `NNN-short-title.md`. Every ticket starts with:

```yaml
---
id: 001
title: Short imperative title
status: open
priority: high
triage: ready-for-agent
assignee: null
---
```

After the metadata, include `Problem`, `Scope`, `Acceptance criteria`, `Verification`, and `Log`. Acceptance criteria use Markdown checkboxes.

## Operations

- **List**: enumerate `tickets/open/*.md` and inspect metadata before selecting work.
- **Create**: choose one greater than the highest ID across all three directories and add it under `tickets/open/`.
- **Read**: open the matching numeric filename in any state directory.
- **Triage**: edit `priority` and `triage` using the roles in `docs/agents/triage-labels.md`.
- **Claim**: move the file to `tickets/in-progress/`, set `status: in-progress`, set `assignee`, and append a dated `Log` entry.
- **Comment**: append a dated bullet under `Log`.
- **Close**: check completed acceptance criteria, append the verification result, move the file to `tickets/done/`, and set `status: done`. For declined work, set `triage: wontfix` and explain why in `Log`.

When a skill says to publish, fetch, claim, or resolve a ticket, perform the corresponding local operation above. A ticket is complete only when its acceptance criteria and verification are recorded in the file.
