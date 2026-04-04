# Release Lane 3 — QA / Product Audit (Read-Only)

## Worktree
- Path: `/Users/ho/code/garmin-personal-coach-architecture`

## Goal

Provide a strict release audit while runtime work continues elsewhere.

This lane should **not** modify runtime code. It should inspect and report.

## Scope

Perform a skeptical product audit of:

- CLI readiness
- Telegram readiness
- MCP/OpenClaw readiness
- Garmin/Strava integration UX
- coaching consistency across surfaces
- release-risk gaps in docs or product behavior

## Output

Create a read-only audit document, for example:

- `docs/release/release-audit.md`

## Required Structure

For each area, include:

- what appears release-ready
- what is still rough but acceptable
- what would block a clean release
- evidence or file references supporting the assessment

## Files You May Edit
- `docs/release/**`

## Files You Must Not Edit
- runtime Python code
- tests
- README
- research docs

## Acceptance Criteria

1. Audit is evidence-based, not just opinions.
2. It distinguishes blocker vs rough edge.
3. It gives PM/VP-level go/no-go visibility.
4. It does not mutate runtime truth while lane 1 is coding.

## Verification

- cite actual files/commands/behaviors where possible
- keep judgments grounded in the current repo state
- no code changes

## Deliverable Format

When done, report:
1. overall release readiness verdict
2. top blockers
3. top non-blocking polish items
