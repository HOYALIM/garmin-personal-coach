from __future__ import annotations

from datetime import timedelta
from statistics import pstdev

from garmin_coach.models import TrainingLoad
from garmin_coach.training_load import TrainingLoadCalculator


def calculate_ramp_rate(calculator: TrainingLoadCalculator, today: str) -> float:
    if not hasattr(calculator, "calculate_ctl"):
        return 0.0
    ctl_today = calculator.calculate_ctl(today)
    trend = calculator.export_time_series(days=8)
    if len(trend) < 8:
        return 0.0
    ctl_7_days_ago = trend[0].get("ctl", 0.0)
    return round(ctl_today - ctl_7_days_ago, 1)


def calculate_monotony(daily_loads: list[float]) -> float:
    if not daily_loads:
        return 0.0
    avg = sum(daily_loads) / len(daily_loads)
    deviation = pstdev(daily_loads) if len(daily_loads) > 1 else 0.0
    if deviation == 0:
        return 0.0
    return round(avg / deviation, 2)


def calculate_strain(daily_loads: list[float]) -> float:
    monotony = calculate_monotony(daily_loads)
    return round(sum(daily_loads) * monotony, 1)


def calculate_weekly_volume_km(
    calculator: TrainingLoadCalculator, start_date: str, end_date: str
) -> float:
    sessions = calculator.get_sessions_in_range(start_date, end_date)
    total = 0.0
    for session in sessions:
        duration_min = getattr(session, "duration_min", None)
        if duration_min:
            total += max(float(duration_min) / 6.0, 0.0)
    return round(total, 1)


def build_training_load(calculator: TrainingLoadCalculator, today: str) -> TrainingLoad:
    snapshot = calculator.get_snapshot(today)
    weekly = calculator.get_weekly_stats(today)
    previous_week_start = weekly.week_start - timedelta(days=7)
    previous_week_end = weekly.week_start - timedelta(days=1)
    daily = [
        item.trimp
        for item in calculator.get_sessions_in_range(
            weekly.week_start.isoformat(), snapshot.date.isoformat()
        )
    ]
    weekly_volume_km = calculate_weekly_volume_km(
        calculator, weekly.week_start.isoformat(), snapshot.date.isoformat()
    )
    previous_week_volume_km = calculate_weekly_volume_km(
        calculator, previous_week_start.isoformat(), previous_week_end.isoformat()
    )
    return TrainingLoad(
        ctl=round(snapshot.ctl, 1),
        atl=round(snapshot.atl, 1),
        tsb=round(snapshot.tsb, 1),
        ramp_rate=calculate_ramp_rate(calculator, today),
        monotony=calculate_monotony(daily),
        strain=calculate_strain(daily),
        weekly_volume_km=weekly_volume_km,
        weekly_tss=round(weekly.total_trimp, 1),
        previous_week_volume_km=previous_week_volume_km,
    )
