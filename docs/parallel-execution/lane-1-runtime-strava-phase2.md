# Lane 1 — Runtime / Strava Phase 2

## Worktree
- Path: `/Users/ho/code/garmin-personal-coach`
- Branch context: current main checkout working tree

## Important Note

At the moment, the latest runtime implementation work exists in the main checkout working tree and has **not** been propagated into the older runtime worktree branch. For this lane, use the main checkout above as the source of truth.

Do **not** use `/Users/ho/code/garmin-personal-coach-runtime` for this lane unless the runtime changes are later committed/cherry-picked there.

## Mission

Implement the next runtime phase after Strava phase 1.

The core requirement is:

- keep existing Garmin runtime behavior intact,
- keep Nike untouched,
- refine the new Strava sync path so ownership, runtime boundaries, and source precedence are clearer and more robust.

## Product Context

`garmin-personal-coach` is a Garmin-first endurance coaching product. Garmin is still the authoritative runtime path. Strava is now an additional ingestion source through a sync/normalize/ingest flow, not a peer source for fake daily training-load summaries.

Phase 1 already added:

- `garmin_coach/integrations/strava/sync.py`
- `garmin-coach strava-sync`
- local-date grouping
- fingerprint-based idempotence
- stale-day reconciliation
- adapter-side fake Strava daily summary disabled

Your work begins **after** that phase.

## Goal

Make the Strava path production-cleaner without changing Garmin’s authority.

## Primary Outcomes

1. Clarify Strava ownership metadata beyond fragile description-prefix checks where appropriate.
2. Tighten the boundary between:
   - Garmin runtime truth
   - Strava synced supplemental load
   - generic fetch surfaces
3. Make user-facing/runtime status around Strava sync clearer where it materially helps.

## Files You May Edit

- `garmin_coach/integrations/strava/**`
- `garmin_coach/integrations/models.py`
- `garmin_coach/adapters/strava.py`
- `garmin_coach/adapters/fetch.py`
- `garmin_coach/cli.py`
- Strava-related tests
- Minimal runtime-facing docs only if implementation truth requires it

## Files You Must Not Edit

- `docs/research/**`
- `docs/architecture/**`
- `docs/specs/**`
- HealthKit or Nike docs
- Dashboard/API spec docs
- broad Garmin runtime modules unless a very small compatibility fix is strictly required

## Current Known Boundaries

- Garmin remains primary in `garmin_coach/adapters/fetch.py`
- Strava sync writes into training load via `garmin_coach/integrations/strava/sync.py`
- `garmin_coach/adapters/strava.py:get_daily_summary()` is intentionally disabled now
- Current ownership of Strava-synced days still leans on `[strava-sync]` description markers

## Suggested Implementation Focus

Prefer the smallest meaningful step that improves runtime clarity. Good examples:

- source/ownership metadata strengthening,
- sync status exposure,
- clearer separation between activity listing vs training-load ingestion,
- removing remaining awkward Strava duplication.

Avoid turning this into a whole-platform rewrite.

## Acceptance Criteria

Work is good when all of these are true:

1. Garmin runtime behavior is unchanged for existing Garmin-first flows.
2. Strava sync behavior is more explicit/robust than before.
3. No new fake Strava training-load summary path is introduced.
4. Tests cover the changed behavior.
5. Diagnostics are clean on modified files.
6. Manual QA shows the relevant CLI/runtime path actually works.

## Required Verification

- Run targeted tests for modified files.
- Run `lsp_diagnostics` on every modified runtime file.
- Manually run relevant commands, likely including:
  - `python3 -m garmin_coach.cli oauth-status`
  - `python3 -m garmin_coach.cli strava-sync --dry-run`
- If runtime behavior changes meaningfully, show actual output.

## Collision Rules

- Do not edit research/spec docs owned by lane 2 or lane 3.
- Avoid `README.md` unless the runtime truth absolutely requires a minimal correction.
- If you must touch a shared file like `garmin_coach/adapters/fetch.py`, keep the diff surgical.

## Deliverable Format

When done, provide:

1. short summary of what changed,
2. exact files changed,
3. tests/diagnostics/manual QA evidence,
4. any remaining follow-up risk.
