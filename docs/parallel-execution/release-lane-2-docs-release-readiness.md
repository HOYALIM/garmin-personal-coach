# Release Lane 2 — Docs / Release Readiness

## Worktree
- Path: `/Users/ho/code/garmin-personal-coach-research`

## Goal

Strengthen release readiness without touching runtime code.

This lane should make the product easier to understand and safer to ship, but it must stay docs-only.

## Scope

Produce or refine docs that answer:

- what the product truly does today,
- what is still future work,
- what channels are supported now,
- what setup path a real user should follow,
- what limitations still exist before a broader release.

## Recommended Outputs

Create or refine docs under a release-focused directory, for example:

- `docs/release/current-product-state.md`
- `docs/release/user-journey.md`
- `docs/release/release-readiness-checklist.md`

## Required Content

### Current Product State
- Garmin-first coaching engine
- Strava supplemental sync
- CLI / Telegram / MCP usable now
- iMessage, dashboard, HealthKit, Nike not current release features

### User Journey
- install
- Garmin connect/login
- setup
- optional Strava connect
- use via CLI / Telegram / MCP

### Release Readiness Checklist
- what must be true before tagging a release
- what remains known limitation
- what should be described honestly to early users

## Files You May Edit
- `docs/release/**`

## Files You Must Not Edit
- runtime Python code
- tests
- `README.md` unless specifically coordinated later
- dashboard/api specs

## Acceptance Criteria

1. Docs describe current truth, not aspirational scope.
2. Supported vs planned features are clearly separated.
3. Early-user setup path is understandable.
4. Docs help release decisions instead of marketing beyond the truth.

## Verification

- re-read for overclaiming
- ensure unsupported items are clearly labeled future/blocked
- ensure no runtime-file edits are made

## Deliverable Format

When done, report:
1. docs created/changed
2. current supported surfaces documented
3. key release blockers or limitations called out
