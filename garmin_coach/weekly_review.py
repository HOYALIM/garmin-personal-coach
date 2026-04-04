"""Weekly review cronjob — week summary + AI coach analysis + next week plan."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from garmin_coach.ai_coach import AICoachEngine, CoachContext
from garmin_coach.activity_fetch import resume_garth
from garmin_coach.profile_manager import ProfileManager
from garmin_coach.training_load import Sport, TrainingLoadCalculator
from garmin_coach.training_load_manager import get_training_load_manager


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def _activity_payload(activity) -> dict:
    return activity.to_dict() if hasattr(activity, "to_dict") else activity


def get_week_start(target_date: date) -> date:
    days_since_monday = target_date.weekday()
    return target_date - timedelta(days=days_since_monday)


def get_week_stats(week_start: date, calculator: TrainingLoadCalculator) -> dict:
    return calculator.get_weekly_stats(week_start).to_dict()


def build_weekly_context(
    week_start: date,
    pm: ProfileManager,
    calculator: TrainingLoadCalculator,
) -> CoachContext:
    profile = pm.load()
    if not profile:
        raise RuntimeError("No profile found. Run setup_wizard first.")

    week_end = week_start + timedelta(days=6)
    activities = calculator.get_sessions_in_range(week_start, week_end)
    snapshot = calculator.get_snapshot(week_end)
    zones = pm.calculate_all_zones(profile)
    week_num = (
        week_start - date.fromisoformat(profile.profile.goal_date or "2026-01-01")
    ).days // 7 + 1

    return CoachContext(
        date=week_end.isoformat(),
        user_profile=profile,
        load_snapshot=snapshot,
        zones=zones,
        recent_activities=[_activity_payload(a) for a in activities],
        week_number=max(1, week_num),
        phase="weekly_review",
    )


def format_weekly_summary(stats: dict, activities: list) -> str:
    lines = [
        f"📊 Weekly Summary — {stats.get('week_start', '?')}",
        f"  Sessions: {stats.get('session_count', 0)}",
        f"  Total volume: {stats.get('total_hours', 0):.1f}h",
        f"  Total TRIMP: {stats.get('total_trimp', 0):.0f}",
        f"  CTL change: {stats.get('ctl_change', 0):+.0f}",
    ]

    breakdown = stats.get("sport_breakdown", {})
    if breakdown:
        lines.append("  By sport:")
        for sport, trimp in breakdown.items():
            lines.append(f"    {sport}: {trimp:.0f} TRIMP")

    return "\n".join(lines)


def run_weekly(target_date: date | None = None) -> None:
    resume_garth()

    pm = ProfileManager()
    profile = pm.load() if pm.exists() else None
    if not profile:
        print("No profile found. Run: python -m garmin_coach.setup_wizard")
        return

    if target_date is None:
        target_date = date.today()

    week_start = get_week_start(target_date)

    calc = get_training_load_manager().calculator

    stats = get_week_stats(week_start, calc)
    week_end = week_start + timedelta(days=6)
    activities = calc.get_sessions_in_range(week_start, week_end)

    print(f"\n{format_weekly_summary(stats, activities)}")

    ctx = build_weekly_context(week_start, pm, calc)
    engine = AICoachEngine()
    msg = engine.weekly_review_advice(ctx)

    print("\n" + engine.format_message(msg))

    print(f"\n✓ Weekly review saved.")


def main() -> None:
    p = argparse.ArgumentParser(description="Weekly review")
    p.add_argument("--date", default=None)
    args = p.parse_args()
    target = date.fromisoformat(args.date) if args.date else None
    run_weekly(target)


if __name__ == "__main__":
    main()
