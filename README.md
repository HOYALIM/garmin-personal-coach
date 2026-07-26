# Garmin Personal Coach

**Languages:** English | [한국어](README.ko.md) | [Español](README.es.md) | [日本語](README.ja.md)

Garmin Personal Coach is a Garmin-first AI coaching engine for endurance athletes.

It works today through:

- CLI
- Telegram
- MCP / OpenClaw

It is **not** yet a dashboard, mobile app, or food-photo calorie app.

---

## What It Does Today

- Connects to Garmin Connect as the primary source of truth
- Supports Strava as a supplemental sync source
- Calculates training load (CTL / ATL / TSB)
- Gives coaching guidance through CLI, Telegram, and MCP/OpenClaw
- Supports optional AI providers: OpenAI, Anthropic, Gemini
- Supports lightweight personalized nutrition coaching

---

## Garmin Data We Can Pull

Everything below is fetched through `garminconnect` (≥0.3.6) — the successor to `garth`,
which Garmin's 2026-03 Cloudflare/TLS changes broke for automated logins. `garminconnect`
works around this with browser TLS impersonation. Login once with `garmin-coach connect-garmin`;
the refresh token keeps working for ~30 days without asking again — **avoid re-login loops**,
Garmin now rate-limits login attempts per account, not per IP.

| Category | Data | Coaching use | Status |
|----------|------|---------------|--------|
| **Readiness/Recovery** | Training Readiness (Garmin's own score), HRV + 7-day status, Body Battery, daily Stress, Resting HR + baseline | Feeds `ReadinessScore`; primary gate for the daily guardrails | ✅ pulled |
| **Sleep** | Sleep score, stages (deep/REM/light/awake), total duration | Recovery quality → intensity adjustment | ✅ pulled |
| **Training load (Garmin-native)** | Training Status, VO2max / fitness age, Race Predictions, Lactate Threshold, Endurance Score, Hill Score, Running Tolerance, Cycling FTP | Cross-check against our own CTL/ATL/TSB | 🔲 not yet wired into snapshot |
| **Activities** | Full activity list + per-activity detail: laps, splits, HR/power time-in-zone, gear used, weather, exercise sets (strength) | Session analysis, PRD training-load math | ✅ pulled (list + detail) |
| **Body composition** | Weight, body fat %, muscle/bone mass, daily weigh-ins | Nutrition coaching context | ✅ pulled |
| **Daily activity** | Steps, floors climbed, intensity minutes (weekly too), daily/weekly stress rollups | General fitness picture between workouts | 🔲 not yet wired into snapshot |
| **Blood/health extras** | SpO2, respiration rate, blood pressure, hydration | Altitude/illness detection, hydration nudges | ✅ SpO2/respiration pulled; BP/hydration 🔲 roadmap |
| **Gear** | Gear list, per-gear activity stats, defaults | Shoe/bike mileage tracking (injury-prevention angle) | 🔲 roadmap |
| **Goals/records/badges** | Personal records, goals, badges, challenges | Motivational hooks, PR-based coaching | 🔲 roadmap |
| **Cycle/lifestyle** | Menstrual cycle data, pregnancy summary | Cycle-aware training adjustments | 🔲 roadmap (opt-in only) |

Not pulled by design: nutrition logging fields native to Garmin Connect (we run our own
`nutrition/` engine instead — see below) and golf-specific data (out of scope for endurance coaching).

References used to compile this table: [python-garminconnect](https://github.com/cyberjunky/python-garminconnect) (the client library itself)
and [garmin-grafana](https://github.com/arpanghosh8453/garmin-grafana) (a self-hosted dashboard pulling nearly the same surface into Grafana).

## Strava Data We Can Pull

Strava is **supplemental only** — Garmin stays the source of truth for training load. Full activity
history back to account creation is fetched via `/activities` with page-based pagination (100/page);
this already covers years of history for any athlete, not just recent weeks. As of Strava's June 2026
developer-program changes (Standard tier now requires a Strava subscription, rate limits raised to
200/15min & 2000/day, intermediary-platform routing banned), the adapter backs off on `429` using the
`Retry-After` header instead of silently truncating a backfill — see
[garmin_coach/adapters/strava.py](garmin_coach/adapters/strava.py).

To pull your **entire** Strava history in one run:

```bash
garmin-coach strava-sync --days 3650   # ~10 years; adjust to your account age
```

Design references: [running_page](https://github.com/yihong0618/running_page) (multi-source personal
activity aggregator, same "one athlete, all their data" model we follow) and
[statistics-for-strava](https://github.com/robiningelbrecht/statistics-for-strava) (self-hosted
single-athlete Strava dashboard).

---

## Quick Start

### 1. Install

Recommended:

```bash
pip install garmin-personal-coach[all]
```

From source:

```bash
git clone https://github.com/HOYALIM/garmin-personal-coach.git
cd garmin-personal-coach
pip install -e .[all]
```

### 2. Connect Garmin

```bash
garmin-coach connect-garmin --email your@email.com
```

(`garth login` no longer works — Garmin's 2026 Cloudflare changes broke it. This project now
uses `garminconnect` instead; see [Garmin Data We Can Pull](#garmin-data-we-can-pull) below.)

### 3. Run Setup

```bash
garmin-coach setup
```

### 4. (Optional) Connect Strava

Create a Strava API app, then run:

```bash
garmin-coach connect-strava
```

Strava is **supplemental only** in this release. Garmin remains the primary source of truth.

To inspect sync state:

```bash
garmin-coach oauth-status
garmin-coach strava-sync --dry-run
```

---

## Supported Interfaces

### CLI

```bash
garmin-coach status
garmin-coach log
garmin-coach oauth-status
garmin-coach garmin-sync --dry-run
garmin-coach strava-sync --dry-run
garmin-coach --version
garmin-coach --check-updates
```

### Telegram

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
garmin-coach-telegram
```

For a bot token:

1. Open Telegram
2. Talk to **@BotFather**
3. Create a new bot
4. Copy the token into `TELEGRAM_BOT_TOKEN`

Common commands:

- `/start`
- `/status`
- `/plan`
- `/help`

Natural-language examples:

- `How is my condition today?`
- `I finished my workout`
- `What should I do tomorrow?`

### MCP / OpenClaw

Recommended MCP config:

```json
{
  "mcpServers": {
    "garmin-coach": {
      "command": "garmin-coach-mcp",
      "args": []
    }
  }
}
```

Fallback:

```json
{
  "mcpServers": {
    "garmin-coach": {
      "command": "python",
      "args": ["-m", "mcp_server"]
    }
  }
}
```

Available MCP tools:

- `get_training_status`
- `get_user_profile`
- `get_recent_activities`
- `handle_natural_language`
- `health`
- `get_training_plan`

---

## AI Coaching

Optional AI enhancement:

```bash
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
# or
export GEMINI_API_KEY="..."
```

Without API keys, the product still works with rule-based coaching.

---

## Nutrition Coaching

The current release supports **lightweight personalized nutrition coaching** based on:

- training load / fatigue context
- weight goal (`maintain`, `lose`, `gain`)
- dietary style (`omnivore`, `vegetarian`, `vegan`, `other`)
- food restrictions / avoidances
- preferred coaching style (`brief`, `detailed`, `macros`)

This is **guidance only** in the current release.

Not included yet:

- meal logging
- barcode scanning
- image upload
- calorie estimation from photos

### Future Chapter

In a future update, the nutrition layer may expand to image-based meal analysis where a user uploads a meal photo and gets calorie estimation plus meal recommendations.

That is **not** part of the current release.

---

## Product Boundaries for This Release

### Included now

- Garmin-first coaching engine
- Strava supplemental sync
- CLI / Telegram / MCP usage
- lightweight nutrition coaching

### Not included now

- Web dashboard
- iMessage integration
- Nike Run Club integration
- Apple HealthKit / Apple Watch integration
- full meal tracking or photo-calorie workflows

---

## Architecture Snapshot

```text
garmin_coach/
├── adapters/          # Garmin/Strava data access, Nike scaffold only
├── handler/           # Natural language coaching core
├── integrations/      # Garmin / Strava sync-to-load flows
├── wizard/            # Interactive setup
├── nutrition/         # Nutrition guidance logic
├── telegram_bot.py    # Telegram runtime
└── cli.py             # CLI entrypoint

mcp_server/
├── server.py          # MCP handlers
└── entrypoint.py      # MCP stdio entrypoint
```

---

## Configuration

- Main profile/config: `~/.config/garmin_coach/config.yaml`
- Strava token: `~/.config/garmin_coach/strava_token.json`

---

## Release Positioning

This release should be understood as an **honest beta for local/power users**:

- Garmin-first
- usable now through CLI, Telegram, and MCP/OpenClaw
- still early for broader consumer UX

---

## License

MIT
