# Lane 3 — Architecture / Backend API + Dashboard Prep

## Worktree
- Path: `/Users/ho/code/garmin-personal-coach-architecture`
- Branch: `docs/architecture-dashboard`

## Mission

Refine the architecture/spec lane for the next product layer without touching runtime implementation.

This lane is about making the next coding phase easier, not building the dashboard right now.

## Product Context

Current real product surfaces:

- CLI
- Garmin-first runtime coaching flow
- Telegram bot
- MCP server
- Strava phase 1 sync ingest

Missing product layer:

- backend API contract for web/mobile
- dashboard implementation

The repo already contains draft docs for these. Your job is to improve them carefully.

## Goal

Leave the project with an architecture/spec package that a future implementation lane can build from without guessing.

## Files You May Edit

- `docs/architecture/web-ios-architecture.md`
- `docs/specs/dashboard-mvp.md`
- `docs/specs/dashboard-api-contract.md`

## Files You Must Not Edit

- any runtime Python code
- `mcp_server/server.py`
- `garmin_coach/**`
- `tests/**`
- research docs owned by lane 2

## Scope

### Backend API prep
- refine the thin API layer concept,
- make sure contracts align with current real runtime data,
- avoid claiming endpoints already exist.

### Dashboard prep
- keep MVP read-only,
- ensure the dashboard wraps existing product value,
- avoid inventing a second product model.

## Explicit Constraints

- Spec only.
- No frontend implementation.
- No API server implementation.
- No auth-system invention beyond a conservative future-facing outline.

## Acceptance Criteria

1. Docs remain aligned with the current codebase reality.
2. Dashboard scope stays read-only and MVP-sized.
3. API contract reads like a target design, not implemented runtime.
4. Another engineer could start backend API work from these docs without major ambiguity.

## Verification

- Re-check docs against current runtime surfaces:
  - `garmin_coach/cli.py`
  - `garmin_coach/handler/**`
  - `garmin_coach/telegram_bot.py`
  - `mcp_server/server.py`
- Ensure no sentence implies the dashboard or API already exists.
- Ensure docs still respect Garmin-first runtime truth.

## Collision Rules

- Do not touch runtime files.
- Do not “fix” implementation by editing Python code from this lane.
- If runtime truth blocks a spec assumption, record that clearly in the doc instead of changing code.

## Deliverable Format

When done, provide:

1. what changed in each architecture/spec doc,
2. the clearest recommended next implementation order,
3. any remaining ambiguity that still needs runtime confirmation.
