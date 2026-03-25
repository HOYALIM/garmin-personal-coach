# Garmin Personal Coach

A daily coaching loop that turns Garmin recovery data + a structured training plan into a reliable coaching workflow.

## What it does

Three-stage daily loop:

| Time | Trigger | Output |
|------|---------|--------|
| 4:45 AM | cron | Early training brief (precheck) |
| After wake | `일어났어` | Final workout prescription |
| After workout | `운동 끝` | Log + calendar sync |

## Architecture

```
garmin_coach/
  models.py          — MorningResult, WorkoutLog dataclasses
  plan.py            — training plan lookup
  coach_engine.py    — scoring + coaching logic
  activity_fetch.py  — Garmin data fetch (garth)
  triggers.py        — intent detection
  final_check.py     — post-wake final prescription
  workout_review.py  — post-workout ingest + logging
  calendar_sync.py   — CalDAV calendar sync
  garmin_writeback.py — write-back feasibility
  training_log.py    — manual log writer
  morning_checkin.py — precheck (cron entry point)
  dispatch.py        — CLI dispatcher
  test_coach.py      — unit tests
```

## Setup

### 1. Requirements

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Garmin Authentication

```bash
pip install garth
garth login your@email.com
# Follow OAuth flow — token saved to ~/.garth
```

### 3. Calendar Sync (optional)

CalDAV setup — see [docs/CALDAV_SETUP.md](docs/CALDAV_SETUP.md)

### 4. Configure Plan Start Date

```bash
export GARMIN_PLAN_START_DATE="2026-03-23"  # your training plan start
export GARMIN_RACE_DATE="2026-07-01"          # optional
```

## Usage

```bash
# Precheck (cron)
python morning_checkin.py --phase precheck

# Final check
python dispatch.py --message "일어났어"

# Post-workout
python dispatch.py --message "운동 끝"

# Manual log (no Garmin activity)
python training_log.py \
  --date 2026-03-25 \
  --completed "7 km easy" \
  --distance-km 7.1 \
  --source manual
```

## Trigger Phrases

| Trigger | Phrases |
|---------|---------|
| Wake (final check) | `일어났어`, `기상` |
| Workout complete | `운동 끝`, `러닝 끝`, `오늘 운동했어` |

## Output Files

| Path | Description |
|------|-------------|
| `data/snapshots/YYYY-MM-DD.json` | Morning coaching result |
| `data/training_logs/YYYY-MM-DD.md` | Workout log (human) |
| `data/training_log_json/YYYY-MM-DD.json` | Workout log (machine) |

## Testing

```bash
pip install pytest
python -m pytest tests/ -v
```

## Garmin Write-Back

Activity note write-back is **not implemented**. garth is read-only. garminconnect supports limited write-back but requires separate email/password auth.

Use local logs + calendar as durable truth.

## License

MIT
