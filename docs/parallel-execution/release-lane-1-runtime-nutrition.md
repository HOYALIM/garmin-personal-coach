# Release Lane 1 — Runtime Nutrition Coaching

## Worktree / Checkout
- Path: `/Users/ho/code/garmin-personal-coach`
- Use the main checkout as source of truth.

## Why This Lane Exists

The core truth milestone is done. The highest-value pre-release feature still missing is lightweight, personalized nutrition coaching built into the existing coaching engine.

This is **not** a calorie-tracking app and **not** image analysis yet.

## Goal

Add minimal, personalized nutrition coaching to the current product by:

- collecting nutrition preferences / weight-goal intent during setup,
- persisting them in the profile,
- using them in coaching responses,
- keeping scope small enough to finish tonight.

## Product Boundaries

### In Scope
- nutrition-related user profile fields
- setup wizard prompts for nutrition goals/preferences
- handler / coaching surface improvements for nutrition responses
- simple personalization of nutrition coaching persona
- README note for future image-based calorie estimation if needed by runtime truth

### Out of Scope
- food image upload
- calorie estimation from photos
- meal logging app
- barcode scanning
- macro tracker UI
- new web/mobile implementation

## Recommended Runtime Scope

Implement the smallest version that materially improves the product:

1. Add profile-level nutrition preference fields such as:
   - weight goal / body-composition goal
   - dietary style or food preference
   - food restrictions / avoidances
   - coaching style for nutrition advice
2. Extend setup flows to collect them.
3. Make `ASK_NUTRITION` responses use:
   - current training/load context
   - next-session context if available
   - the new nutrition profile/preferences
4. Keep responses directional and coaching-oriented.

## Files You May Edit
- `garmin_coach/profile_manager.py`
- `garmin_coach/setup_wizard.py`
- `garmin_coach/wizard/__init__.py`
- `garmin_coach/handler/__init__.py`
- `garmin_coach/nutrition/**`
- related tests
- `README.md` only if runtime truth requires a minimal note

## Files You Must Not Edit
- `mcp_server/**`
- `garmin_coach/integrations/garmin/**`
- `garmin_coach/integrations/strava/**`
- dashboard/api docs
- HealthKit/Nike research docs

## Acceptance Criteria

1. Nutrition preferences are persisted in the main profile/config model.
2. Setup flows can collect the new fields without breaking existing setup.
3. Nutrition coaching becomes meaningfully personalized.
4. Current CLI / Telegram / MCP natural-language surfaces can benefit via the handler path.
5. No meal-tracking/product-scope explosion occurs.

## Required Verification

- diagnostics clean on modified runtime files
- targeted tests for profile/setup/handler nutrition changes
- manual QA showing:
  - setup/profile can store nutrition preferences
  - a nutrition question gets different guidance based on user profile or training context

## Deliverable Format

When done, report:
1. files changed
2. which nutrition profile fields were added
3. how the nutrition coaching response changed
4. diagnostics / tests / manual QA evidence
