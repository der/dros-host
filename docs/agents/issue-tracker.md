# Issue tracker: GitHub Issues

Repository: `der/dros-host`. Use `gh` CLI for all operations.

## Conventions

- **Create a ticket**: `gh issue create --title "..." --label "..." --body "..."`
- **Create a map**: create an issue with label `wayfinder:map`.
- **Read a ticket**: `gh issue view <number>`
- **List open tickets**: `gh issue list --label <label> --state open`
- **Comment/resolve**: `gh issue comment <number> --body "..."` then `gh issue close <number>`
- **Apply labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --reason completed`

## Ticket format

Use the standard issue body. Frontmatter (status, assignee, opened, closed) is tracked by GitHub natively. Include `Map: #<map-issue-number>` in the body for child tickets.

## Labels

| Label | Purpose |
|-------|---------|
| `wayfinder:map` | Wayfinder map issue |
| `wayfinder:research` | Research ticket (AFK) |
| `wayfinder:prototype` | Prototype ticket (HITL) |
| `wayfinder:grilling` | Grilling ticket (HITL) |
| `wayfinder:task` | Task ticket |
| `ready-for-agent` | Spec ready for implementation |

## Wayfinding operations

Used by `/wayfinder`. The **map** is an issue with label `wayfinder:map`. Tickets are issues with `wayfinder:*` labels.

- **Map**: create an issue with label `wayfinder:map`.
- **Child ticket**: create an issue with label `wayfinder:<type>`. Reference the map issue number in the body.
- **Blocking**: reference blocking issues by number in the body (e.g. `Blocked by: #2, #3`). A ticket is unblocked when every referenced issue is closed.
- **Frontier query**: `gh issue list --label wayfinder:prototype,wayfinder:grilling,wayfinder:task,wayfinder:research --state open --assignee @me` (for claimed) or without `--assignee` for unclaimed.
- **Claim**: `gh issue edit <number> --assignee @me`
- **Resolve**: add a resolution comment, then `gh issue close <number> --reason completed`.