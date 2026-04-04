# User Journey — Early Release

_The path a real user should follow today. Does not cover future features._

---

## Prerequisites

- Python 3.10 or higher
- A Garmin Connect account with activity history
- Optional: OpenAI, Anthropic, or Gemini API key (for AI-enhanced coaching)
- Optional: Telegram bot token from BotFather (for mobile use)

---

## Step 1 — Install

**From PyPI:**
```bash
pip install garmin-personal-coach[all]
```

**From source:**
```bash
git clone https://github.com/HOYALIM/garmin-personal-coach.git
cd garmin-personal-coach
pip install -e .[all]
```

**With optional features:**
```bash
pip install garmin-personal-coach[telegram]   # Telegram bot
pip install garmin-personal-coach[ai]         # AI coaching
pip install garmin-personal-coach[mcp]        # MCP server
pip install garmin-personal-coach[all]        # Everything
```

---

## Step 2 — Connect Garmin

```bash
garth login your@garminconnect.email.com
```

This saves your Garmin session locally. Required before setup.

---

## Step 3 — Run Setup

```bash
garmin-coach setup
```

The interactive wizard collects:
- Your name, age, weight
- Sport preferences (running, cycling, swimming, triathlon)
- Fitness level
- AI API key (optional — skip to use rule-based coaching)

Profile is saved to `~/.config/garmin_coach/config.yaml`.

---

## Step 4 — (Optional) Connect Strava

Strava provides supplemental activity data alongside Garmin.

1. Create a Strava API app at [strava.com/settings/api](https://www.strava.com/settings/api)
2. Run:

```bash
garmin-coach connect-strava
```

3. Enter your Strava Client ID / Client Secret when prompted
4. Complete the browser OAuth flow
5. Optional sync check:

```bash
garmin-coach oauth-status
garmin-coach strava-sync --dry-run
```

> **Important:** Strava is supplemental only. Garmin remains the primary source of truth. Strava sync is manual (`garmin-coach strava-sync`) in the current release.

---

## Step 5 — Use the Product

### CLI

```bash
garmin-coach status     # Today's training status and coaching
garmin-coach log        # Log a completed workout
garmin-coach oauth-status
garmin-coach garmin-sync --dry-run
garmin-coach strava-sync --dry-run
garmin-coach --version  # Check version
garmin-coach --check-updates
```

### Telegram Bot (mobile)

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
garmin-coach-telegram
```

To create a Telegram bot token:
1. Open Telegram
2. Talk to **@BotFather**
3. Create a new bot
4. Copy the bot token into `TELEGRAM_BOT_TOKEN`

Commands:
- `/start` — Start
- `/status` — Training status
- `/plan` — Today's plan
- `/help` — Help
- Or chat naturally: `"오늘 컨디션 어때?"`, `"운동 끝났어"`

### MCP Server (Claude Desktop / Cursor)

Add to `claude_desktop_config.json`:
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

Fallback if the console script is not on PATH:

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

Available tools: `get_training_status`, `get_user_profile`, `get_recent_activities`, `handle_natural_language`, `get_training_plan`, `health`

### CalDAV Calendar Sync (optional)

See `docs/CALDAV_SETUP.md` for full setup. Requires manual env vars:
```bash
export CALDAV_URL="..."
export CALDAV_USER="..."
export CALDAV_PASS="..."
export CALENDAR_NAME="Training"
```

---

## What Users Should Know Before Starting

- **Garmin Connect is required.** The product does not work without it.
- **AI is optional.** Rule-based coaching works without an API key, but responses are less personalized.
- **Strava is supplemental.** Garmin remains the primary source of truth. Strava sync is manual in this release.
- **Nutrition coaching is lightweight.** It personalizes guidance from your setup preferences and training context, but it is not meal tracking or photo-based calorie estimation yet.
- **No web dashboard.** CLI, Telegram, and MCP are the only interfaces available now.
- **No mobile app.** Telegram is the mobile-friendly path.
