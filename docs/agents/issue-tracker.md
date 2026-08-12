# Issue tracker: GitHub

Issues and specs live in `Today20092/podcast-automixer` on GitHub. GitHub Issues are the single source of truth; use the `gh` CLI for issue operations and do not create a parallel local ticket.

## Conventions

- **Create**: `gh issue create --title "..." --body-file <file> --label "<category>,<state>"`
- **Read**: `gh issue view <number> --comments --json number,title,body,labels,assignees,comments,state`
- **List**: `gh issue list --state open --json number,title,body,labels,assignees,comments`
- **Comment**: `gh issue comment <number> --body-file <file>`
- **Label**: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`
- **Claim**: `gh issue edit <number> --add-assignee @me`, then set Project status to `In progress`
- **Close**: record verification, check the acceptance criteria, then run `gh issue close <number> --reason completed --comment "..."`

Infer the repository from `git remote -v`; `gh` does this automatically inside the clone. Use body files for multiline Markdown so shell escaping cannot alter issue content.

Maintainer-created engineering issues include `Problem`, `Scope`, `Acceptance criteria`, and `Verification`. Use comments for dated progress, decisions, blockers, and verification results. An issue is complete only when its acceptance criteria are satisfied and verification is recorded.

## Pull requests as a triage surface

**PRs as a request surface: no.** External pull requests are reviewed as code contributions, not treated as incoming feature requests by `/triage`.

GitHub shares one number space across issues and pull requests. Resolve an ambiguous `#42` with `gh pr view 42`; if it is not a pull request, use `gh issue view 42`.

## Skill operations

- When a skill says **publish to the issue tracker**, create a GitHub issue.
- When a skill says **fetch the relevant ticket**, read the issue body, comments, labels, assignees, and state.
- Work produced by `/to-tickets` is already agent-ready; apply `ready-for-agent` without sending it through `/triage`.
- Incoming reports use exactly one category (`bug` or `enhancement`) and one state from `docs/agents/triage-labels.md`.

## Project workflow

The `Podcast Automixer` GitHub Project organizes issues without replacing them:

- `Inbox`: awaiting triage
- `Ready`: sufficiently specified and available to claim
- `In progress`: assigned and actively being worked
- `Blocked`: cannot proceed until a recorded dependency or external condition clears
- `Done`: completed and verified

Priorities are `P0` through `P3`. The Backlog groups by priority, Current work groups by status, and Roadmap displays scheduled larger outcomes using Start date and Target date. Leave dates unset until there is a real scheduling decision.

## Sub-issues and blocking

Use GitHub sub-issues for decomposed work. A parent roadmap issue holds the outcome and shared context; independently deliverable implementation slices are child issues.

Use native issue dependencies for blocking edges:

1. Fetch the blocker's database ID: `gh api repos/Today20092/podcast-automixer/issues/<blocker> --jq .id`
2. Add the edge: `gh api --method POST repos/Today20092/podcast-automixer/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`

If native dependencies are unavailable, put `Blocked by: #<number>` at the top of the child issue. An issue is ready only when every blocker is closed.

## Wayfinding

For `/wayfinder`, create one issue labelled `wayfinder:map` and link its decision tickets as sub-issues. Child labels use `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, or `wayfinder:task`. The frontier is the first open, unassigned child whose blockers are all closed. Claiming the issue is the session's first write; resolution records the answer in a comment, closes the child, and adds the decision pointer to the map.
