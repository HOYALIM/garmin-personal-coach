# Current Product State

_As of 2026-03-31. Describes what is true today, not planned scope._

---

## Summary

Garmin Personal Coach is a Garmin-first AI coaching tool for endurance athletes. It reads workout data from Garmin Connect, calculates training load (CTL/ATL/TSB), and delivers coaching feedback through CLI, Telegram, or MCP. Strava can supplement Garmin data but is not a standalone source. All other integrations are future work.

---

## Supported Now

### Data Sources

| Source | Status | Notes |
|--------|--------|-------|
| Garmin Connect | **Supported** | Core data source. Auth via `garth`. Activities, HR, training load. |
| Strava | **Partial** | Adapter implemented. Activity fetch and profile work. CTL/ATL calculations are placeholder math, not real PMC. OAuth setup is not a guided wizard — token must be supplied manually. |
| Nike Run Club | **Not supported** | Stub file exists. No usable integration. |

### Interfaces

| Interface | Status | Notes |
|-----------|--------|-------|
| CLI (`garmin-coach`) | **Supported** | `setup`, `status`, `log`, `--check-updates`, `--version` |
| Telegram bot | **Supported** | Natural language coaching. Requires self-hosted bot token. Korean and English. |
| MCP server | **Supported** | JSON-RPC server compatible with Claude Desktop, Cursor. Tools: `get_training_status`, `get_user_profile`, `get_recent_activities`, `handle_natural_language`, `get_training_plan`, `health`. |
| Web dashboard | **Not supported** | Not built. |
| iMessage | **Not supported** | Not built. |
| Apple HealthKit | **Not supported** | Requires native iOS app. Not in this repo. |

### AI Coaching

| Feature | Status | Notes |
|---------|--------|-------|
| AI-enhanced responses | **Supported (optional)** | Requires OpenAI or Anthropic API key. Without AI key, rule-based coaching still works. |
| Natural language input | **Supported** | Korean and English. |

### Training Features

| Feature | Status | Notes |
|---------|--------|-------|
| CTL / ATL / TSB | **Supported** | Calculated from Garmin data. Strava CTL/ATL is placeholder only. |
| Multi-sport | **Supported** | Running, cycling, swimming, triathlon. |
| CalDAV calendar sync | **Supported** | Requires manual env var setup. See `docs/CALDAV_SETUP.md`. |
| Periodization | **Supported** | Basic TSB-driven plan recommendation. |

---

## Not Supported (Future / Planned / Blocked)

| Feature | Category | Why |
|---------|----------|-----|
| Strava OAuth wizard | **Planned** | Token must be manually supplied today. Guided OAuth flow not yet built. |
| Strava real training load | **Planned** | CTL/ATL from Strava uses simplified placeholder math. |
| Web dashboard | **Planned** | Not built. Specs exist in `docs/specs/`. |
| Nike Run Club | **Blocked / Deferred** | No public API. See `docs/research/nike-run-club-feasibility.md`. |
| Apple HealthKit | **Separate track** | Requires native iOS app. Python backend prep possible now. See `docs/research/healthkit-feasibility.md`. |
| iMessage | **Not planned** | No implementation or spec. |
| Apple Watch native | **Separate track** | Requires watchOS app. Not in scope for this repo. |

---

## Configuration

- Profile: `~/.config/garmin_coach/config.yaml`
- Strava token: `~/.config/garmin_coach/strava_token.json` (manually created)
- Garmin session: managed by `garth` library

---

## Version

`v0.1.0` — Beta. Package classifier: `Development Status :: 4 - Beta`.
