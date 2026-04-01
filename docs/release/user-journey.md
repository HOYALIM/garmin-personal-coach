# User Journey — Early Release

_The path a real user should follow today. Does not cover future features._

---

## Prerequisites

- Python 3.10 or higher
- A Garmin Connect account with activity history
- Optional: OpenAI or Anthropic API key (for AI-enhanced coaching)
- Optional: Telegram bot token (for mobile use)

---

## Step 1 — Install

**From PyPI:**
```bash
pip install garmin-personal-coach
```

**From source:**
```bash
git clone https://github.com/HOYALIM/garmin-personal-coach.git
cd garmin-personal-coach
pip install -e .
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

> **Note:** Strava OAuth is not a guided wizard yet. You must supply an access token manually.

1. Create a Strava API app at [strava.com/settings/api](https://www.strava.com/settings/api)
2. Obtain an access token via OAuth
3. Save it manually:

```bash
cat > ~/.config/garmin_coach/strava_token.json <<EOF
{
  "access_token": "your_access_token",
  "refresh_token": "your_refresh_token",
  "expires_at": 9999999999
}
EOF
```

> **Limitation:** CTL/ATL calculations from Strava use simplified math, not the full PMC model. Garmin-sourced training load is more accurate.

---

## Step 5 — Use the Product

### CLI

```bash
garmin-coach status     # Today's training status and coaching
garmin-coach log        # Log a completed workout
garmin-coach --version  # Check version
garmin-coach --check-updates
```

### Telegram Bot (mobile)

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
python -m telegram.bot
```

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
      "command": "python",
      "args": ["-m", "mcp"]
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
- **Strava requires manual token setup.** There is no guided OAuth flow yet.
- **No web dashboard.** CLI, Telegram, and MCP are the only interfaces available now.
- **No mobile app.** Telegram is the mobile-friendly path.
