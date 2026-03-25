"""CalDAV calendar sync — idempotent workout event note updates."""

import os
import re
from datetime import date
from typing import Any

from garmin_coach.models import WorkoutLog


CALDAV_URL = os.getenv("CALDAV_URL", "")
CALDAV_USER = os.getenv("CALDAV_USER", "")
CALDAV_PASS = os.getenv("CALDAV_PASS", "")
CALENDAR_NAME = os.getenv("CALENDAR_NAME", "Training")

WORKOUT_BLOCK_START = "<!-- GARMIN_COACH_START -->"
WORKOUT_BLOCK_END = "<!-- GARMIN_COACH_END -->"

WORKOUT_KEYWORDS = [
    "러닝",
    "달리기",
    "운동",
    "트레이닝",
    "run",
    "jog",
    "workout",
    "marathon",
    "long run",
    "threshold",
    "training",
    "easy",
    "recovery",
]


def _caldav_available() -> bool:
    if not (CALDAV_URL and CALDAV_USER and CALDAV_PASS):
        return False
    try:
        import caldav

        return True
    except ImportError:
        return False


def build_workout_block(log: WorkoutLog) -> str:
    lines = [
        WORKOUT_BLOCK_START,
        "## Garmin Coach Workout Log",
        f"- Date: {log.date}",
        f"- Planned: {log.planned or 'n/a'}",
        f"- Status: {log.final_status or 'n/a'}",
        f"- Completed: {log.completed or 'n/a'}",
    ]
    if log.activity:
        lines += [
            f"- Type: {log.activity.type or 'n/a'}",
            f"- Distance: {log.activity.distance_km} km"
            if log.activity.distance_km
            else "- Distance: n/a",
            f"- Pace: {log.activity.avg_pace or 'n/a'}",
            f"- HR: {log.activity.avg_hr or 'n/a'} bpm",
        ]
    if log.coach_note:
        lines.append(f"- Note: {log.coach_note}")
    lines += [
        f"- Source: {log.source}",
        f"- Logged: {log.updated_at}",
        WORKOUT_BLOCK_END,
        "",
    ]
    return "\n".join(lines)


def strip_workout_block(description: str) -> str:
    pattern = rf"{re.escape(WORKOUT_BLOCK_START)}.*?{re.escape(WORKOUT_BLOCK_END)}\n?"
    return re.sub(pattern, "", description, flags=re.DOTALL)


def merge_description(existing: str, log: WorkoutLog) -> str:
    cleaned = strip_workout_block(existing or "")
    block = build_workout_block(log)
    if cleaned.strip():
        return f"{cleaned.rstrip()}\n\n{block}"
    return block


def event_matches_workout(title: str) -> bool:
    if not title:
        return False
    return any(kw.lower() in title.lower() for kw in WORKOUT_KEYWORDS)


def find_and_update_workout_event(target_date: str, log: WorkoutLog) -> str | None:
    if not _caldav_available():
        return None

    try:
        import caldav
        from caldav import Calendar, Event
    except ImportError:
        return None

    try:
        client = caldav.DAVClient(
            CALDAV_URL, username=CALDAV_USER, password=CALDAV_PASS
        )
        principal = client.principal()
        calendars = list(principal.calendars())

        target = date.fromisoformat(target_date)
        start = f"{target_date}T00:00:00"
        end = f"{target_date}T23:59:59"

        for cal in calendars:
            if CALENDAR_NAME not in cal.name:
                continue

            events = cal.search_events(start=start, end=end, expand=True)
            for ev in events:
                if not event_matches_workout(ev.summary):
                    continue

                existing = ""
                if hasattr(ev, "data") and ev.data:
                    existing = ev.data
                elif hasattr(ev, "raw"):
                    existing = getattr(ev.raw, "text", "")

                updated = merge_description(existing, log)
                ev.data = updated
                ev.save()
                return f"{ev.summary} ({target_date})"

    except Exception:
        pass

    return None
