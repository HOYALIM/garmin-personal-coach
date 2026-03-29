# Garmin Personal Coach

Your personal AI-powered endurance sports coach. Connects to Garmin Connect, adapts to your fitness — running, cycling, swimming, and triathlon.

## Quick Start

### Installation

```bash
pip install garmin-personal-coach
```

Or from source:

```bash
git clone https://github.com/HOYALIM/garmin-personal-coach.git
cd garmin-personal-coach
pip install -e .
```

### Connect Garmin

```bash
garth login your@email.com
```

### Run Setup

```bash
garmin-coach setup
```

## Mobile-First: Telegram Bot

For the best experience on mobile, use the Telegram bot:

```bash
pip install garmin-personal-coach[telegram]
export TELEGRAM_BOT_TOKEN="your_bot_token"
python -m telegram.bot
```

### Telegram Commands

- `/start` - Start the bot
- `/status` - Check today's training status
- `/plan` - See today's training plan
- `/help` - Help

Or just chat naturally: "오늘 컨디션 어때?" "운동 끝났어" "피곤해"

## AI Coach

Get personalized coaching with AI:

```bash
pip install garmin-personal-coach[ai]
export OPENAI_API_KEY="sk-..."
```

AI will automatically enhance responses with personalized advice.

## MCP Server

Connect to Claude, Cursor, or other AI tools:

```bash
pip install garmin-personal-coach[mcp]
```

Add to Claude Desktop config (`claude_desktop_config.json`):

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

### Available MCP Tools

- `get_training_status` - Get CTL/ATL/TSB metrics
- `get_user_profile` - Get user profile
- `get_recent_activities` - Get recent workouts
- `handle_natural_language` - Natural language coaching

## CLI Usage

```bash
# Check training status
garmin-coach status

# Log workout
garmin-coach log

# Check for updates
garmin-coach --check-updates
```

Or with natural language:

```bash
python -m garmin_coach.handler --message "오늘 컨디션 어때?"
```

## Features

### Training Load Management

| Metric | Description |
|--------|-------------|
| **CTL** | Chronic Training Load — 42-day fitness |
| **ATL** | Acute Training Load — 7-day fatigue |
| **TSB** | Training Stress Balance — form (CTL − ATL) |

### Multi-Sport Support

- 🏃 **Running** — pace zones, marathon planning
- 🚴 **Cycling** — power zones (FTP-based)
- 🏊 **Swimming** — pace zones
- 🏅 **Triathlon** — multi-sport periodization

### Coming Soon

- 📱 Strava integration
- 📱 Nike Run Club integration
- 🌐 Web Dashboard

## Architecture

```
garmin_coach/
├── adapters/       # Data sources (Garmin → Strava/Nike coming)
├── handler/       # Natural language interface + AI
├── wizard/        # Interactive setup
├── nutrition/     # Nutrition advice
├── ai_simple.py   # AI coach (OpenAI/Anthropic)
├── training_load.py
├── periodization.py
└── cli.py

mcp/
└── server.py      # MCP server

telegram/
└── bot.py         # Telegram bot
```

## Configuration

Profile stored at `~/.config/garmin_coach/config.yaml`.

## Updates

```bash
garmin-coach --check-updates
```

## License

MIT
