"""Post-workout review — ingest activity and write training log."""

import argparse
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from garmin_coach.activity_fetch import fetch_recent_activities, resume_garth
from garmin_coach.calendar_sync import find_and_update_workout_event
from garmin_coach.logging_config import log_warning
from garmin_coach.models import ActivitySummary, WorkoutLog


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
TRAINING_MD_DIR = DATA_DIR / "training_logs"
TRAINING_JSON_DIR = DATA_DIR / "training_log_json"


def ensure_dirs() -> None:
    TRAINING_MD_DIR.mkdir(parents=True, exist_ok=True)
    TRAINING_JSON_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        log_warning(f"Failed to load workout review JSON from {path}", exc=exc)
        return None


def find_today_activity(
    activities: list[dict[str, Any]], target_date: str, hours_back: int = 20
) -> dict[str, Any] | None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    for act in activities:
        start = act.get("start_time", "")
        if not start:
            continue
        try:
            dt = datetime.fromisoformat(start)
            if dt >= cutoff:
                return act
        except Exception as exc:
            log_warning(f"Failed to parse activity start time: {start}", exc=exc)
            if start >= cutoff.isoformat():
                return act
    return None


def classify_activity_type(act: dict[str, Any]) -> str:
    t = (act.get("type") or "").lower()
    if any(x in t for x in ("run", "treadmill", "jog")):
        return "running"
    if "swim" in t or "pool" in t:
        return "swimming"
    if "bike" in t or "cycl" in t:
        return "cycling"
    return t or "unknown"


def build_md(log: WorkoutLog) -> str:
    lines = [f"# {log.date} Training Log", ""]
    lines += [
        f"- Planned: {log.planned or 'n/a'}",
        f"- Morning status: {log.final_status or 'n/a'}",
        f"- Completed: {log.completed or 'n/a'}",
    ]
    if log.activity:
        lines += [
            f"- Type: {log.activity.type}",
            f"- Distance: {log.activity.distance_km} km"
            if log.activity.distance_km
            else "- Distance: n/a",
            f"- Duration: {log.activity.duration_min} min"
            if log.activity.duration_min
            else "- Duration: n/a",
            f"- Pace: {log.activity.avg_pace or 'n/a'}",
            f"- HR: {log.activity.avg_hr or 'n/a'} bpm",
        ]
    if log.subjective:
        lines += [
            f"- Energy: {log.subjective.energy}/5",
            f"- Legs: {log.subjective.legs}/5",
            f"- Mood: {log.subjective.mood}/5",
        ]
    lines += [
        f"- Note: {log.coach_note or 'n/a'}",
        f"- Tomorrow: {log.tomorrow_note or 'n/a'}",
        f"- Source: {log.source}",
        f"- Updated: {log.updated_at}",
    ]
    return "\n".join(lines) + "\n"


def build_coach_note(act: dict[str, Any], planned: str, distance_km: float | None) -> str:
    planned_lower = planned.lower()
    if distance_km is None:
        return "Activity recorded. Log distance/time manually if needed."
    numbers = re.findall(r"(\d+)", planned)
    planned_km = float(numbers[0]) if numbers else 0.0
    diff_pct = ((distance_km - planned_km) / planned_km * 100) if planned_km > 0 else 0
    if "threshold" in planned_lower or "tempo" in planned_lower:
        return f"Good run. {distance_km}km done. Pace feel OK?"
    if "long run" in planned_lower:
        return f"{distance_km}km long run. Fuel/hydration OK? Easy tomorrow."
    return f"{distance_km}km done. {diff_pct:+.0f}% vs plan. Feel recovered?"


def write_log(
    target_date: str, activity: dict[str, Any] | None, snapshot: dict[str, Any] | None
) -> WorkoutLog:
    log = WorkoutLog(date=target_date)
    log.planned = (
        (snapshot.get("recommended_session") or snapshot.get("planned_session"))
        if snapshot
        else None
    )
    log.final_status = snapshot.get("status") if snapshot else None

    if activity:
        log.source = "garmin"
        log.activity = ActivitySummary(
            type=classify_activity_type(activity),
            start_time=activity.get("start_time"),
            distance_km=activity.get("distance_km"),
            duration_min=activity.get("duration_min"),
            avg_pace=activity.get("avg_pace"),
            avg_hr=activity.get("avg_hr"),
        )
        log.coach_note = build_coach_note(activity, log.planned or "", activity.get("distance_km"))
    else:
        log.source = "unknown"
        log.coach_note = "No Garmin activity found. Enter distance/time manually."

    log.updated_at = datetime.now().isoformat()
    TRAINING_MD_DIR.mkdir(parents=True, exist_ok=True)
    TRAINING_JSON_DIR.mkdir(parents=True, exist_ok=True)
    md_path = TRAINING_MD_DIR / f"{target_date}.md"
    json_path = TRAINING_JSON_DIR / f"{target_date}.json"
    md_path.write_text(build_md(log))
    log.synced["markdown"] = True
    json_path.write_text(json.dumps(log.to_dict(), ensure_ascii=False, indent=2))
    return log


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Post-workout review")
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--distance-km", type=float, default=None)
    p.add_argument("--duration-min", type=float, default=None)
    p.add_argument("--avg-pace", default="")
    p.add_argument("--avg-hr", type=int, default=None)
    p.add_argument("--energy", type=int, default=3)
    p.add_argument("--legs", type=int, default=2)
    p.add_argument("--mood", type=int, default=3)
    p.add_argument("--pain", action="store_true")
    p.add_argument("--illness", action="store_true")
    p.add_argument("--notes", default="")
    p.add_argument("--tomorrow-note", default="")
    p.add_argument("--no-calendar", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs()
    garmin_ok = resume_garth()
    snapshot = load_json(SNAPSHOT_DIR / f"{args.date}.json")

    activity = None
    if garmin_ok:
        activities = fetch_recent_activities(limit=5)
        activity = find_today_activity(activities, args.date)

    log = write_log(args.date, activity, snapshot)
    print(
        f"Activity: {activity.get('type') if activity else 'none'} — {activity.get('distance_km') if activity else '?'}km"
        if activity
        else "No recent activity found."
    )
    print(f"Coach note: {log.coach_note}")

    if not args.no_calendar:
        cal_result = find_and_update_workout_event(args.date, log)
        if cal_result:
            log.synced["calendar"] = True
            json_path = TRAINING_JSON_DIR / f"{args.date}.json"
            json_path.write_text(json.dumps(log.to_dict(), ensure_ascii=False, indent=2))
            print(f"Calendar updated: {cal_result}")

    print(f"Log: {TRAINING_MD_DIR / f'{args.date}.md'}")


if __name__ == "__main__":
    main()
