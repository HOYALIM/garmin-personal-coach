# Release Checklist

## Scope for This Release

This release should be framed as:

- Garmin-first personal coaching engine
- usable through CLI, Telegram, and MCP/OpenClaw
- Strava supplemental sync available
- lightweight personalized nutrition coaching available
- no dashboard/app/iMessage/HealthKit/Nike direct integration yet

## Product Truth Checklist

- Garmin remains the authoritative runtime source.
- Strava is supplemental sync, not equal authority.
- Manual log writes land in the same durable training-load state.
- Workout-complete can trigger Garmin sync and refresh context.
- Evening/weekly review use the shared load state.
- CLI / Telegram / MCP all route through the same coaching core or shared load model.

## Runtime Verification Checklist

- `garmin-coach status`
- `garmin-coach log`
- `garmin-coach oauth-status`
- `garmin-coach garmin-sync --dry-run`
- `garmin-coach strava-sync --dry-run`
- `garmin-coach-mcp --version`
- installed MCP handshake succeeds
- Telegram starts in the intended mode (polling or webhook)

## Test / Diagnostics Checklist

- Modified runtime files diagnostics clean
- Focused core-truth suite passes
- Nutrition-focused suite passes
- MCP/OpenClaw suite passes
- Garmin/Strava sync suites pass

## Docs / Messaging Checklist

- README reflects current supported surfaces accurately
- README nutrition section does not overclaim meal tracking or photo analysis
- README marks iMessage as future update only
- README marks dashboard as future work
- Nike remains clearly blocked/deferred
- HealthKit remains clearly native-track future work

## Release Risk Checklist

- No known startup blocker remains for Telegram
- MCP/OpenClaw config examples point to current entrypoint
- No stale blocker remains in release audit
- Known limitation about one-load-per-day model is documented honestly

## Go / No-Go Rule

Release is a **GO** if:

- runtime verification passes,
- focused test/diagnostic checks pass,
- release docs describe current truth honestly,
- no blocker reappears in Telegram/MCP/runtime startup.

### Current final blocker status

- **No remaining release blocker in the current verified state.**
- Telegram end-to-end proof has been completed with a real BotFather token (`garmin-coach-telegram`, `/start`, `/status`).

Release is a **NO-GO** if:

- Garmin primary truth is broken,
- core surfaces disagree with one another,
- MCP or Telegram startup path is broken,
- docs overclaim features that are not actually present.
