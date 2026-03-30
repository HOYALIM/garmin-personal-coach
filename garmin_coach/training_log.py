"""Manual training log writer — md + json output."""

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from garmin_coach.logging_config import log_warning
from garmin_coach.models import ActivitySummary, SubjectiveRating, WorkoutLog


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
EVENING_DIR = DATA_DIR / "evening_reviews"
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
        log_warning(f"Failed to load JSON from {path}", exc=exc)
        return None


def build_md(log: WorkoutLog) -> str:
    lines = [f"# {log.date} Training Log", ""]
    lines += [
        f"- Planned: {log.planned or 'n/a'}",
        f"- Morning status: {log.final_status or 'n/a'}",
        f"- Completed: {log.completed or 'n/a'}",
    ]
    if log.activity:
        lines += [
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
            f"- Pain/illness: {'yes' if (log.subjective.pain or log.subjective.illness) else 'no'}",
        ]
    lines += [
        f"- Note: {log.coach_note or 'n/a'}",
        f"- Tomorrow: {log.tomorrow_note or 'n/a'}",
        f"- Source: {log.source}",
        f"- Updated: {log.updated_at}",
    ]
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Write training log")
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--completed", default="")
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
    p.add_argument("--source", default="manual", choices=["garmin", "manual", "strava", "unknown"])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs()
    snapshot = load_json(SNAPSHOT_DIR / f"{args.date}.json") or {}
    evening = load_json(EVENING_DIR / f"{args.date}.json") or {}

    log = WorkoutLog(date=args.date)
    log.planned = snapshot.get("recommended_session") or snapshot.get("planned_session")
    log.final_status = snapshot.get("status")
    log.completed = args.completed or evening.get("completed", "")

    if args.distance_km is not None or args.avg_pace or args.avg_hr is not None:
        log.activity = ActivitySummary(
            distance_km=args.distance_km,
            duration_min=args.duration_min,
            avg_pace=args.avg_pace or None,
            avg_hr=args.avg_hr,
        )

    log.subjective = SubjectiveRating(
        energy=args.energy if args.energy else evening.get("energy", 3),
        legs=args.legs if args.legs else evening.get("legs", 2),
        mood=args.mood if args.mood else evening.get("mood", 3),
        pain=args.pain or evening.get("pain", False),
        illness=args.illness or evening.get("illness", False),
    )
    log.coach_note = args.notes or evening.get("notes", "")
    log.tomorrow_note = args.tomorrow_note or evening.get("tomorrow_note", "")
    log.source = args.source
    log.updated_at = datetime.now().isoformat()
    log.synced = {"markdown": False, "calendar": False, "garmin_writeback": False}

    md_path = TRAINING_MD_DIR / f"{args.date}.md"
    json_path = TRAINING_JSON_DIR / f"{args.date}.json"
    md_path.write_text(build_md(log))
    log.synced["markdown"] = True
    json_path.write_text(json.dumps(log.to_dict(), ensure_ascii=False, indent=2))
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
