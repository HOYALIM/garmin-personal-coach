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
| Strava | **Supported (supplemental)** | OAuth flow available via `garmin-coach connect-strava` or setup wizard. Supplemental sync via `garmin-coach strava-sync`; Garmin remains authoritative. |
| Nike Run Club | **Not supported** | Stub file exists. No usable integration. |

### Interfaces

| Interface | Status | Notes |
|-----------|--------|-------|
| CLI (`garmin-coach`) | **Supported** | `setup`, `status`, `log`, `oauth-status`, `connect-strava`, `strava-sync`, `garmin-sync`, `--check-updates`, `--version` |
| Telegram bot | **Supported** | Natural language coaching via `garmin-coach-telegram`. Requires user-provisioned Telegram bot token. |
| MCP server | **Supported** | Compatible with OpenClaw / Claude Desktop / Cursor via `garmin-coach-mcp` or `python -m mcp_server`. Tools: `get_training_status`, `get_user_profile`, `get_recent_activities`, `handle_natural_language`, `get_training_plan`, `health`. |
| Web dashboard | **Not supported** | Not built. |
| iMessage | **Not supported** | Not built. |
| Apple HealthKit | **Not supported** | Requires native iOS app. Not in this repo. |

### AI Coaching

| Feature | Status | Notes |
|---------|--------|-------|
| AI-enhanced responses | **Supported (optional)** | Supports OpenAI, Anthropic, or Gemini. Without API keys, rule-based coaching still works. |
| Natural language input | **Supported** | Korean and English. |
| Lightweight nutrition coaching | **Supported** | Personalized by weight goal, dietary style, restrictions, and coaching style. Not meal tracking. |

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
| Strava full independent authority | **Not planned now** | Strava is intentionally supplemental; Garmin remains primary runtime truth. |
| Web dashboard | **Planned** | Not built. Specs exist in `docs/specs/`. |
| Nike Run Club | **Blocked / Deferred** | No public API. See `docs/research/nike-run-club-feasibility.md`. |
| Apple HealthKit | **Separate track** | Requires native iOS app. Python backend prep possible now. See `docs/research/healthkit-feasibility.md`. |
| iMessage | **Planned later** | No implementation yet. README marks this as next update, not current release scope. |
| Apple Watch native | **Separate track** | Requires watchOS app. Not in scope for this repo. |

---

## Configuration

- Profile: `~/.config/garmin_coach/config.yaml`
- Strava token: `~/.config/garmin_coach/strava_token.json` (created by OAuth flow)
- Garmin session: managed by `garth` library

---

## Version

`v0.1.0` — Beta. Package classifier: `Development Status :: 4 - Beta`.
