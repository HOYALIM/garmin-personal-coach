# Parallel Lane Review Checklists

## Purpose

Use these checklists when the three Claude Code lanes return results.

The goal is not to review code and docs in isolation. The goal is to confirm that each lane strengthens the same product:

- Garmin-first runtime truth,
- Strava as additive synced ingestion,
- blocked/external integrations handled honestly,
- future web/mobile layers wrapping the existing core instead of forking it.

---

## Lane 1 — Runtime / Strava Phase 2 Review Checklist

## Product Fit
- Does the change keep Garmin as the authoritative runtime path?
- Does Strava remain a sync/normalize/ingest flow instead of reintroducing fake daily summary logic?
- Is Nike still untouched in runtime code?

## Architecture Fit
- Is ownership of Strava-synced data clearer than before?
- Is the boundary between Garmin runtime truth and Strava supplemental load more explicit?
- Did the lane avoid broad rewrites of unrelated runtime systems?

## Code Surface Check
- Review `garmin_coach/integrations/strava/**`
- Review `garmin_coach/adapters/strava.py`
- Review `garmin_coach/adapters/fetch.py` if touched
- Review `garmin_coach/cli.py` if touched

## Regression Check
- Garmin-first flows still behave the same
- Strava sync still works through CLI/runtime entrypoints
- No new fake CTL/ATL/TSB path appears in adapters
- No runtime-only data is silently overwritten by Strava sync

## Evidence Required
- tests passed for changed files
- diagnostics clean on modified runtime files
- manual QA output shown for the relevant commands

Minimum expected command evidence:

- `python3 -m garmin_coach.cli oauth-status`
- `python3 -m garmin_coach.cli strava-sync --dry-run`
- one relevant `process_message(...)` or `garmin-coach status` path if runtime truth changes user-facing coaching output

## Blockers / Red Flags
- Strava starts acting as peer authority with Garmin instead of additive sync
- `fetch_today_summary()` or handler logic becomes source-confused
- ownership is tracked only by fragile heuristics without improvement
- runtime docs claim behavior that was not manually verified

---

## Lane 2 — Research / Nike + HealthKit Review Checklist

## Product Fit
- Does the Nike conclusion stay aligned with current product safety standards?
- Does the HealthKit conclusion preserve the repo’s role as Python core/backend rather than pretending it can be a native Apple client?

## Research Quality
- Are claims clearly separated into facts, assumptions, unknowns, recommendations?
- Are official/public support boundaries stated honestly?
- Does the lane avoid “just scrape it” style handwaving?

## Decision Quality
- Nike: is the recommendation still clearly defer/block unless an official path appears?
- HealthKit: is the recommendation clearly “native app track + backend prep,” not “write a Python adapter”?

## Evidence Required
- doc text is internally consistent
- no runtime code changes
- reasoning is strong enough that runtime lane won’t waste time on unsupported integrations

## Blockers / Red Flags
- Doc implies a public Nike API exists without strong grounding
- Doc implies direct Python/server-side HealthKit access is viable
- Recommendation is fuzzy enough that engineers could still misread it as implementation-ready

---

## Lane 3 — Architecture / Backend API + Dashboard Spec Review Checklist

## Product Fit
- Do the docs still describe the current product as CLI + handler + Telegram + MCP + Garmin-first runtime + Strava sync?
- Does the web/dashboard layer wrap the core instead of redefining it?

## Architecture Quality
- Is the backend API clearly framed as the missing layer between current Python core and future web/mobile surfaces?
- Are proposed contracts aligned with existing runtime outputs and concepts?
- Is the dashboard still read-only MVP first?

## Spec Discipline
- No claim that endpoints already exist
- No actual implementation slipped in
- No invented auth/session complexity that the repo cannot yet support

## Evidence Required
- docs stay aligned with `garmin_coach/cli.py`, `garmin_coach/handler/**`, `garmin_coach/telegram_bot.py`, and `mcp_server/server.py`
- API contract looks like a target design, not shipped behavior
- recommended implementation order is explicit

Required provenance control:

- every endpoint and every contract field must be tagged as one of:
  - `existing`
  - `derived from existing`
  - `target only`
- each `existing` or `derived from existing` endpoint and field must cite the current source file/function
- any endpoint marked `target only` must not be described as currently reachable through CLI, handler, Telegram, or MCP

## Blockers / Red Flags
- Dashboard spec assumes runtime truths that don’t exist
- API draft duplicates business logic that already belongs in Python core
- Doc turns the project into a generic SaaS app instead of a coaching engine with delivery layers

---

## Cross-Lane Integration Checklist

Use this after all three lanes report back.

## Runtime Truth
- Lane 1 output is the source of truth for runtime behavior
- Lane 2 and Lane 3 docs do not contradict Lane 1 runtime reality

## Product Narrative
- README/product story still makes sense after all three lanes
- Garmin remains first-class core source
- Strava is described as synced ingestion, not equal authority
- Nike is explicitly blocked/deferred
- HealthKit is explicitly native-track work

## Merge Order Recommendation
1. Lane 2 (research docs) can merge independently.
2. Lane 1 (runtime) establishes runtime truth.
3. Lane 3 (architecture/spec docs) should merge only after checking against Lane 1’s final runtime diff.

If Lane 3 finishes before Lane 1, treat it as provisional and require a post-Lane-1 revalidation before merge.

Required review artifact for lane 3 merge:

- a short provenance table or annotated checklist showing each endpoint/field classification
- explicit reference to Lane 1’s final runtime diff or final merged runtime state used for revalidation

## Final PM / VP Questions
- What is now true in the shipped product?
- What is still blocked?
- What is the next implementation milestone?
- Did any lane quietly expand scope beyond the product strategy?
