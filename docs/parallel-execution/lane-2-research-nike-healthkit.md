# Lane 2 — Research / Nike + HealthKit

## Worktree
- Path: `/Users/ho/code/garmin-personal-coach-research`
- Branch: `docs/research-integrations`

## Mission

Produce and refine the external integration research lane without touching runtime code.

This lane exists to reduce uncertainty, not to ship provider adapters.

## Product Context

The runtime product already has Garmin as the core source of truth, Strava phase 1 sync exists, and future platform growth depends on making good decisions about blocked or native-only integrations.

The two active topics are:

- Nike Run Club
- Apple HealthKit / Apple Watch

## Goal

Make the research docs strong enough that the runtime lane does not waste time building on unsupported assumptions.

## Files You May Edit

- `docs/research/nike-run-club-feasibility.md`
- `docs/research/healthkit-feasibility.md`
- if truly needed, a small note in `docs/parallel-execution/**`

## Files You Must Not Edit

- any `garmin_coach/**/*.py`
- `mcp_server/**`
- `tests/**`
- dashboard/API spec docs
- runtime README text unless specifically requested later

## Required Focus

### Nike
- confirm whether any safe/public developer path exists,
- keep the current blocked/defer recommendation grounded,
- strengthen the “why not now” case,
- distinguish official support from reverse-engineered temptation.

### HealthKit / Apple Watch
- clarify exactly what needs a native Apple app,
- separate backend-prep work from native-client work,
- make the repo boundary obvious: Python core vs native iOS/watchOS layer.

## Output Style Requirements

Each document should clearly separate:

- Confirmed facts
- Working assumptions
- Unknowns / blockers
- Recommendation

## Acceptance Criteria

1. No runtime code changes.
2. The Nike doc makes a clear safe/defer/drop judgment grounded in public support reality.
3. The HealthKit doc clearly explains why this is not a direct Python adapter task.
4. Another engineer could read the docs and know whether to implement, defer, or split into a native track.

## Verification

- Re-read both docs for overclaiming.
- Ensure wording does not imply a public Nike API exists unless you can ground it.
- Ensure HealthKit wording does not imply direct server/Python access.

## Collision Rules

- Docs-only lane.
- Do not modify runtime files even if you notice architecture problems.
- If runtime docs look stale, note it in your final summary instead of fixing it here.

## Deliverable Format

When done, provide:

1. what changed in the research docs,
2. strongest recommendation for Nike,
3. strongest recommendation for HealthKit,
4. any unresolved unknowns.
