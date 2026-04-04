from __future__ import annotations

from datetime import date
from typing import Any

from garmin_coach.logging_config import log_warning
from garmin_coach.models import ActivitySummary
from garmin_coach.training_load import Sport
from garmin_coach.training_load_manager import get_training_load_manager


def _to_training_sport(sport_type: str | None) -> Sport:
    raw = (sport_type or "").lower()
    if raw in {"run", "running", "jog", "treadmill"}:
        return Sport.RUNNING
    if raw in {"ride", "bike", "biking", "cycling", "virtualride", "ebikeride"}:
        return Sport.CYCLING
    if raw in {"swim", "swimming", "pool_swim", "open_water_swim"}:
        return Sport.SWIMMING
    if raw in {"triathlon"}:
        return Sport.TRIATHLON
    return Sport.OTHER


def _activity_value(activity: ActivitySummary | dict[str, Any], key: str, default=None):
    if isinstance(activity, dict):
        return activity.get(key, default)
    return getattr(activity, key, default)


def upsert_activity_to_training_load(
    session_date: date,
    activity: ActivitySummary | dict[str, Any],
    source_tag: str,
    description: str | None = None,
) -> dict[str, Any]:
    manager = get_training_load_manager()
    sport = _to_training_sport(
        _activity_value(activity, "type") or _activity_value(activity, "sport_type")
    )
    duration_min = float(_activity_value(activity, "duration_min") or 0)
    distance_km = _activity_value(activity, "distance_km")
    avg_hr = _activity_value(activity, "avg_hr") or _activity_value(activity, "heart_rate_avg")

    if duration_min <= 0:
        return {"action": "skipped", "reason": "missing-duration"}

    trimp = manager.calculator.session_calculator.calculate_trimp(
        sport=sport,
        duration_min=duration_min,
        avg_hr=avg_hr,
        distance_km=distance_km if distance_km is not None else None,
    )

    existing = manager.calculator.get_session(session_date)
    action = "updated" if existing else "added"
    session_description = description or f"[{source_tag}] logged activity"

    manager.add_activity(
        session_date=session_date,
        trimp=trimp,
        sport=sport.value,
        duration_min=duration_min,
        description=session_description,
    )

    return {
        "action": action,
        "date": session_date.isoformat(),
        "sport": sport.value,
        "duration_min": duration_min,
        "trimp": trimp,
        "description": session_description,
    }
