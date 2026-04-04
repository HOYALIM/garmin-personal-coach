# Merge Order Plan

## Current State

All three lanes are now review-complete and merge-ready:

- Lane 1 — runtime nutrition coaching (main checkout)
- Lane 2 — research docs (research worktree)
- Lane 3 — release audit / architecture docs (architecture worktree)

## Recommended Merge Order

## 1. Lane 2 — Research Docs

Merge first because it is docs-only and independent of runtime truth changes.

Scope:

- `docs/research/nike-run-club-feasibility.md`
- `docs/research/healthkit-feasibility.md`

Why first:

- no runtime collision,
- clarifies blocked / native-track work,
- safe to merge independently.

## 2. Lane 3 — Release Audit / Architecture Docs

Merge second because it is docs-only and now explicitly points to the main checkout as runtime source of truth.

Scope:

- `docs/release/release-audit.md`
- architecture/spec release-facing docs in the architecture worktree

Why second:

- helps frame the release honestly,
- does not change runtime behavior,
- should land before or alongside the runtime lane if you want the release docs ready.

## 3. Lane 1 — Runtime Nutrition Coaching

Merge last because it is the only lane changing live runtime behavior.

Scope:

- `garmin_coach/profile_manager.py`
- `garmin_coach/setup_wizard.py`
- `garmin_coach/wizard/__init__.py`
- `garmin_coach/handler/__init__.py`
- `README.md`
- nutrition-related tests

Why last:

- runtime truth wins,
- highest risk of incidental conflicts,
- easiest to validate once docs are already ready.

## Merge Notes

- If Lane 1 and main checkout already represent the current runtime source of truth, do not re-copy older runtime worktree content back into main.
- Resolve `README.md` carefully if other docs changes touched wording.
- Keep the release-facing description honest:
  - Garmin-first
  - Strava supplemental sync
  - CLI / Telegram / MCP usable now
  - nutrition coaching is lightweight / preference-driven
  - iMessage, dashboard, HealthKit, Nike remain future/blocked

## Post-Merge Priority

After all three are merged, the next highest-value engineering milestone is:

1. backend API layer,
2. then read-only dashboard,
3. then future platform expansions.
