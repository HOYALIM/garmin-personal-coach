# Release Audit — garmin-personal-coach

**Worktree:** `/Users/ho/code/garmin-personal-coach`
**Runtime Source of Truth Reviewed:** `/Users/ho/code/garmin-personal-coach`

> This audit reflects the current runtime truth in the main checkout. Earlier lane-3 audit work was docs-only and reviewed the same runtime source of truth; this file is the integrated main-checkout release audit for final go/no-go decisions.

**Verdict: GO**

The core coaching engine is release-ready for early users with a Garmin account. The primary surfaces (CLI, Telegram, MCP) are functional. Internal code/test/doc blockers are cleared, and Telegram end-to-end proof has been completed with a real BotFather token.

---

## 1. CLI (`garmin_coach/cli.py`)

**Release-ready**
- `setup` — wizard collects full profile including nutrition preferences (US-L1 complete)
- `oauth-status` — shows Garmin/Strava connection state and strava-sync summary
- `strava-sync [--dry-run] [--days N]` — ownership-guarded, fingerprint-idempotent, dry-run safe
- `garmin-sync [--dry-run] [--days N]` — symmetric Garmin sync command
- `status` — returns coaching response via `process_message`
- `log` — logs workout completion via `process_message`
- `connect-strava` — OAuth flow for Strava
- `--version`, `--check-updates` — standard release hygiene

**Rough but acceptable**
- `status` and `log` use hardcoded Korean phrases (`"컨디션 어때?"`, `"운동 끝"`) — fine for current early users but should be documented

**Would block release**
- None identified. All commands have `RuntimeError` catch with `sys.stderr` output and non-zero exit.

---

## 2. Telegram (`garmin_coach/telegram_bot.py`)

**Release-ready**
- Commands: `/start`, `/help`, `/status`, `/plan`, `/setup`, `/profile`
- ConversationHandler for multi-step flows (lines 152–180)
- Delegates to `process_message` — shares the same coaching engine as CLI
- `TelegramRuntimeConfig` validates config on startup (line 63)
- Fresh end-to-end proof completed with a real BotFather token:
  - `/start` returned the welcome/help response
  - `/status` returned a live CTL/ATL/TSB coaching response
  - `/plan` returned plan guidance
  - `/log` entered the multi-step workout logging flow and advanced correctly
  - verified from the real Telegram client conversation using a BotFather-issued token

**Rough but acceptable**
- Requires user to provision their own Telegram bot token and set env vars — this is now documented clearly in the user journey

**Would block release**
- None.

---

## 3. MCP Server (`mcp_server/server.py`)

**Release-ready**
- Exposes 6 tools: `get_training_status`, `get_user_profile`, `get_recent_activities`, `handle_natural_language`, `health`, `get_training_plan`
- JSON-RPC over stdio — compatible with standard MCP clients
- `handle_natural_language` routes through the full coaching handler
- `health` tool provides integration health check

**Rough but acceptable**
- No authentication on the MCP layer — acceptable for local stdio use, not for network-exposed deployments

**Would block release**
- None for local use case.

---

## 4. Garmin / Strava Integration UX

**Release-ready**
- `garmin_coach/adapters/fetch.py`: Garmin is the only `primary_source()`. Strava is explicitly excluded from `merged_daily_summary()` training-load path (lines 23–27, 53–54)
- `garmin_coach/integrations/strava/sync.py`: Ownership guards prevent Garmin data from being overwritten by strava-sync. Fingerprint-based idempotence prevents redundant updates (lines 200–226)
- Stale-day reconciliation handles the case where Garmin takes over a previously Strava-owned day (lines 153–189)
- Dry-run support throughout strava-sync

**Rough but acceptable**
- Strava sync is manual (`garmin-coach strava-sync`) — users expecting automatic sync will be confused. Must be documented.
- `oauth-status` now shows sync state, which helps, but no automatic trigger exists

**Would block release**
- None. The manual-sync model is intentional and defensible for v1.

---

## 5. Coaching Consistency

**Release-ready**
- `garmin_coach/handler/__init__.py`: 7 intents handled: `WAKE_UP`, `WORKOUT_COMPLETE`, `ASK_STATUS`, `ASK_PLAN`, `ASK_HELP`, `ASK_NUTRITION`, `SYMPTOM_REPORT` (lines 151–164)
- Rule-based fallback is coherent and gives actionable guidance without AI
- AI path falls back gracefully to rules on any exception (line 147)
- Nutrition coaching (`_handle_ask_nutrition`) now personalizes by weight_goal, dietary_style, food_restrictions, coaching_style

**Rough but acceptable**
- Intents are matched via keyword patterns in `garmin_coach/handler/intent.py` — coverage for non-Korean/English input may be limited
- Nutrition coaching is profile-based only; no per-session macro calculation visible to user

**Would block release**
- None. The coaching responses are directional and honest about what they are.

---

## 6. Test Coverage Signal

```
146 passed, 0 failed in the current full suite
```

The repository-wide suite is now green. Focused self-serve confidence checks and the full suite both support the current release state.

---

## Top Blockers

No hard runtime blocker prevents the current beta release.

---

## Top Non-Blocking Polish Items

1. **Telegram provisioning is still self-hosted** — user must create a bot via BotFather and manage the token.
2. **Strava sync is manual** — users must run `garmin-coach strava-sync` periodically; no automatic trigger exists yet.
3. **One-load-per-day model** — still simplifies same-day multi-session coexistence.
4. **CLI Korean hardcoding** — `status` / `log` commands still use Korean prompts internally.

---

*Audit date: 2026-04-01. Based on main checkout at `/Users/ho/code/garmin-personal-coach`.*
