"""Evening check-in cronjob — daily health check + AI coaching advice."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from garmin_coach.activity_fetch import (
    fetch_morning_metrics,
    fetch_recent_activities,
    resume_garth,
)
from garmin_coach.ai_coach import AICoachEngine, CoachContext
from garmin_coach.coach_engine import evaluate
from garmin_coach.models import MorningMetrics, Phase
from garmin_coach.plan import get_planned_session, get_week_brief, get_week_number
from garmin_coach.profile_manager import ProfileManager
from garmin_coach.training_load import Sport, TrainingLoadCalculator


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
EVENING_DATA = DATA_DIR / "evening_data"


def ask_self_report() -> dict:
    print("\n📋 Evening Check-In")
    print("Answer a few quick questions:\n")

    def q(label: str, default: str = "") -> str:
        return (
            input(f"  {label}{f' [{default}]' if default else ''}: ").strip() or default
        )

    def scale(label: str, default: int) -> int:
        while True:
            raw = q(f"{label} (1-5)", str(default))
            try:
                v = int(raw)
                if 1 <= v <= 5:
                    return v
            except ValueError:
                pass
            print("  Enter 1–5")

    return {
        "energy": scale("Energy today", 3),
        "legs": scale("Legs freshness", 3),
        "mood": scale("Overall mood", 3),
        "sleep_hours": q("Hours slept last night", "7.5"),
        "nutrition_notes": q("Nutrition notes (optional)", ""),
        "stress_level": scale("Stress level", 2),
        "pain": q("Any pain or injury? (y/N)", "n").lower() == "y",
        "supplements": q("Took supplements today? (y/N)", "n").lower() == "y",
    }


def build_evening_context(
    target_date: str,
    self_reported: dict,
    pm: ProfileManager,
    calculator: TrainingLoadCalculator,
) -> CoachContext:
    profile = pm.load()
    if not profile:
        raise RuntimeError("No profile found. Run setup_wizard first.")

    week = get_week_number(target_date)
    planned = get_planned_session(target_date)
    brief = get_week_brief(week)

    today = date.fromisoformat(target_date)
    activities = fetch_recent_activities(today, today)
    last = activities[0] if activities else None

    snapshot = calculator.get_snapshot(today)
    zones = pm.calculate_all_zones(profile)

    upcoming_date = (today + timedelta(days=1)).isoformat()
    upcoming_week = get_week_number(upcoming_date)
    upcoming_session = get_planned_session(upcoming_date)

    return CoachContext(
        date=target_date,
        user_profile=profile,
        load_snapshot=snapshot,
        zones=zones,
        recent_activities=[
            a.to_dict() if hasattr(a, "to_dict") else a for a in activities
        ],
        self_reported=self_reported,
        week_number=week,
        phase=brief[:20] if brief else "base",
        last_session=last.to_dict() if last and hasattr(last, "to_dict") else None,
        upcoming_session={
            "date": upcoming_date,
            "week": upcoming_week,
            "session": upcoming_session,
        },
    )


def save_evening_data(target_date: str, self_reported: dict) -> Path:
    EVENING_DATA.mkdir(exist_ok=True)
    fp = EVENING_DATA / f"{target_date}.json"
    with open(fp, "w") as f:
        json.dump(
            {
                "date": target_date,
                "reported_at": datetime.now().isoformat(),
                "self_report": self_reported,
            },
            f,
            indent=2,
        )
    return fp


def run_evening(target_date: str | None = None, auto: bool = False) -> None:
    if target_date is None:
        target_date = date.today().isoformat()

    resume_garth()

    pm = ProfileManager()
    if not pm.exists():
        print("No profile found. Run: python -m garmin_coach.setup_wizard")
        return

    self_reported = {}
    if not auto:
        self_reported = ask_self_report()
    save_evening_data(target_date, self_reported)

    calc = TrainingLoadCalculator(sex="male")
    calc_file = DATA_DIR / "training_load.json"
    if calc_file.exists():
        calc = TrainingLoadCalculator.from_json(calc_file)

    ctx = build_evening_context(target_date, self_reported, pm, calc)
    engine = AICoachEngine()
    msg = engine.daily_evening_advice(ctx)

    print("\n" + engine.format_message(msg))

    calc_file.write_text(calc.export_json())
    print(f"\n✓ Evening check-in saved to {EVENING_DATA}/{target_date}.json")


def main() -> None:
    p = argparse.ArgumentParser(description="Evening check-in")
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument(
        "--auto", action="store_true", help="Skip questions, use rule-based advice"
    )
    run_evening(p.parse_args().date, auto=p.parse_args().auto)


if __name__ == "__main__":
    main()
