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
garth login your@email.com
```

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
