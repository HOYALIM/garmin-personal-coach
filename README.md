# Garmin Personal Coach

Your personal AI-powered endurance sports coach. Runs on your laptop, connects to Garmin Connect, adapts to your fitness — running, cycling, swimming, and triathlon.

## What It Does

```
06:00  Morning Precheck     — Wake up, brief coaching pulse
06:30  Final Check         — Final prescription based on fresh HRV/readiness data
22:00  Evening Check-in    — Daily health Q&A + AI coaching advice
Sunday Weekly Review        — Week summary + AI analysis + next week preview
```

**Hybrid intelligence**: Rule-based engine (CTL/ATL/TSB, periodization) ensures safety and consistency. AI enhances with personalized context, plan adjustments, and coaching language.

## Supported Sports

- 🏃 **Running** — pace zones, marathon/half/10K planning
- 🚴 **Cycling** — power zones (FTP-based), endurance training
- 🏊 **Swimming** — pace zones, threshold training
- 🏅 **Triathlon** — multi-sport periodization, brick workouts

## Quick Start

```bash
git clone https://github.com/HOYALIM/garmin-personal-coach.git
cd garmin-personal-coach
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run setup wizard
python -m garmin_coach.setup_wizard

# Connect Garmin
pip install garth
garth login your@email.com

# Install scheduler
python -m garmin_coach.scheduler --install-cron
# Add output to crontab: crontab -e
```

## Architecture

```
garmin_coach/
  profile_manager.py    — user profile, zones, config.yaml
  training_load.py      — CTL/ATL/TSB, TRIMP, form analysis
  periodization.py      — Base/Build/Peak/Race periodization
  ai_coach.py          — OMO AI + rule-based fallback engine
  plan.py              — training plan lookup
  coach_engine.py       — scoring, recommendation logic
  activity_fetch.py     — Garmin Connect data (garth)
  calendar_sync.py      — CalDAV calendar sync
  morning_checkin.py    — 06:00 precheck cronjob
  final_check.py        — 06:30 final prescription
  evening_checkin.py    — 22:00 health check + AI advice
  weekly_review.py      — Sunday AI weekly review
  scheduler.py          — user-time-based job runner
  setup_wizard.py       — interactive CLI profile setup
  dispatch.py           — CLI dispatcher
```

## Key Concepts

### Training Load (CTL / ATL / TSB)

| Metric | Description |
|--------|-------------|
| **CTL** | Chronic Training Load — 42-day fitness trend |
| **ATL** | Acute Training Load — 7-day fatigue |
| **TSB** | Training Stress Balance — CTL − ATL (form) |
| **TRIMP** | Training Impulse — session load score |

TSB tells you when to push and when to back off:
- `TSB > +25`: Detrained risk — add volume
- `TSB +10 to +25`: Fresh (race day)
- `TSB -10 to +10`: Training sweet spot
- `TSB < -25`: Injury risk — recover

### Periodization

Four phases: **Base → Build → Peak → Race**
- Recovery/deload weeks every 3–4 weeks
- Volume increases gradually, intensity peaks near race
- Rules-based: safe, consistent, explainable

### AI Coach

AI generates personalized advice based on your profile, load data, and self-reports. Three flexibility levels:
- **Conservative**: Minor adjustments only (≤10% volume)
- **Moderate**: Session swaps, intensity changes (≤20%)
- **Flexible**: Week restructuring (≤40%)

Falls back to rule-based engine if OMO AI is unavailable.

## Setup Wizard Questions

1. **About you** — name, age, sex, height, weight
2. **Sports** — running, cycling, swimming, triathlon (multi-select)
3. **Goal** — target event, date, fitness level, available days
4. **Fitness assessment** — recent race times, FTP, HR baseline (or "auto" to fetch from Garmin)
5. **Garmin auth** — garth login verification
6. **Schedule** — per-job time config, enable/disable per job
7. **AI coach** — tone, flexibility, notification method

## Manual Commands

```bash
# Daily loop
python -m garmin_coach.dispatch --message "일어났어"      # final check
python -m garmin_coach.dispatch --message "운동 끝"        # post-workout

# Individual cronjobs
python -m garmin_coach.morning_checkin --date 2026-03-25
python -m garmin_coach.evening_checkin --date 2026-03-25  # interactive
python -m garmin_coach.evening_checkin --date 2026-03-25 --auto  # no questions
python -m garmin_coach.weekly_review  # current week

# Profile
python -m garmin_coach.profile_manager  # show current profile
python -m garmin_coach.setup_wizard  # reconfigure

# Scheduler
python -m garmin_coach.scheduler --dispatch      # run due jobs now
python -m garmin_coach.scheduler --install-cron # show cron line
```

## Configuration

Profile stored at `~/.config/garmin_coach/config.yaml`.

Key environment variables:

| Variable | Description |
|----------|-------------|
| `GARMIN_PLAN_START_DATE` | Training plan start (default: from config) |
| `GARMIN_RACE_DATE` | Target race date |
| `OMO_PATH` | Path to OpenCode binary (default: `omo`) |
| `CALDAV_URL`, `CALDAV_USER`, `CALDAV_PASS` | Calendar sync (optional) |

## Data Files

```
~/.config/garmin_coach/config.yaml   # user profile
data/training_load.json              # CTL/ATL/TSB time series
data/snapshots/YYYY-MM-DD.json       # morning coaching results
data/training_logs/YYYY-MM-DD.md      # human-readable workout log
data/training_log_json/YYYY-MM-DD.json # machine-readable workout log
data/evening_data/YYYY-MM-DD.json    # evening self-reports
```

## Testing

```bash
pip install pytest
python -m pytest tests/ -v
```

## Garmin Write-Back

Activity annotation write-back is **not implemented**. garth is read-only. The recommended workflow: local logs + calendar as durable truth.

## License

MIT
