from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from garmin_coach.adapters.garmin import GarminAdapter
from garmin_coach.integrations.models import CanonicalDailyActivityBatch
from garmin_coach.logging_config import log_warning
from garmin_coach.training_load import Sport
from garmin_coach.training_load_manager import get_training_load_manager


DATA_DIR = os.path.expanduser("~/.config/garmin_coach")
INTEGRATIONS_DIR = os.path.join(DATA_DIR, "integrations")
GARMIN_SYNC_STATE_FILE = os.path.join(INTEGRATIONS_DIR, "garmin_sync_state.json")


def _ensure_dir() -> None:
    os.makedirs(INTEGRATIONS_DIR, exist_ok=True)


def _load_state() -> dict[str, Any]:
    if not os.path.exists(GARMIN_SYNC_STATE_FILE):
        return {"days": {}}
    try:
        with open(GARMIN_SYNC_STATE_FILE) as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {"days": data.get("days", {})}
    except Exception as exc:
        log_warning(f"Failed to read Garmin sync state: {exc}")
    return {"days": {}}


def _save_state(state: dict[str, Any]) -> None:
    _ensure_dir()
    with open(GARMIN_SYNC_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.chmod(GARMIN_SYNC_STATE_FILE, 0o600)


def _aggregate_garmin_days(days: int, window_start_date=None) -> list[CanonicalDailyActivityBatch]:
    adapter = GarminAdapter()
    if not adapter.is_authenticated():
        raise RuntimeError("Garmin is not authenticated. Run 'garth login' first.")

    if window_start_date is None:
        window_start_date = (datetime.now() - timedelta(days=days)).date()
    start = datetime.combine(window_start_date, datetime.min.time())
    activities = adapter.get_activities(start)
    manager = get_training_load_manager()
    calculator = manager.calculator.session_calculator

    grouped: dict[str, list] = defaultdict(list)
    for activity in activities:
        grouped[activity.start_time.astimezone().date().isoformat()].append(activity)

    batches: list[CanonicalDailyActivityBatch] = []
    for day_iso, items in sorted(grouped.items()):
        totals: dict[str, Any] = {
            "duration_min": 0.0,
            "distance_km": 0.0,
            "calories": 0,
            "trimp": 0.0,
            "sport_counts": defaultdict(int),
            "external_ids": [],
        }

        for activity in items:
            sport = (
                Sport(activity.sport_type)
                if activity.sport_type in [s.value for s in Sport]
                else Sport.OTHER
            )
            duration_min = round(activity.duration_seconds / 60, 1)
            distance_km = round((activity.distance_meters or 0) / 1000, 2)
            trimp = calculator.calculate_trimp(
                sport=sport,
                duration_min=duration_min,
                avg_hr=activity.heart_rate_avg,
                distance_km=distance_km if distance_km > 0 else None,
            )
            totals["duration_min"] += duration_min
            totals["distance_km"] += distance_km
            totals["calories"] += activity.calories or 0
            totals["trimp"] += trimp
            totals["sport_counts"][sport.value] += 1
            totals["external_ids"].append(activity.activity_id)

        primary_sport = max(
            totals["sport_counts"].items(),
            key=lambda item: item[1],
            default=(Sport.OTHER.value, 0),
        )[0]

        batches.append(
            CanonicalDailyActivityBatch(
                source="garmin",
                activity_date=datetime.fromisoformat(day_iso).date(),
                external_ids=sorted(totals["external_ids"]),
                activity_count=len(items),
                primary_sport=primary_sport,
                duration_min=round(totals["duration_min"], 1),
                distance_km=round(totals["distance_km"], 2),
                calories=int(totals["calories"]),
                trimp=round(totals["trimp"], 1),
            )
        )
    return batches


def sync_garmin_training_load(days: int = 30, dry_run: bool = False) -> dict[str, Any]:
    manager = get_training_load_manager()
    state = _load_state()
    window_start_date = (datetime.now() - timedelta(days=days)).date()
    batches = _aggregate_garmin_days(days, window_start_date=window_start_date)
    current_dates = {batch.activity_date.isoformat() for batch in batches}
    report: dict[str, Any] = {
        "days": days,
        "dry_run": dry_run,
        "added": 0,
        "updated": 0,
        "skipped": 0,
        "removed": 0,
        "items": [],
    }

    for previous_date in sorted(list(state["days"].keys())):
        try:
            previous_date_obj = datetime.fromisoformat(previous_date).date()
        except ValueError:
            state["days"].pop(previous_date, None)
            continue
        if previous_date_obj < window_start_date or previous_date in current_dates:
            continue

        existing = manager.calculator.get_session(previous_date_obj)
        if not existing:
            if not dry_run:
                state["days"].pop(previous_date, None)
            continue
        if not existing.description.startswith("[garmin-sync]"):
            if not dry_run:
                state["days"].pop(previous_date, None)
            continue

        if not dry_run:
            manager.calculator.remove_session(previous_date_obj)
            manager.save()
            state["days"].pop(previous_date, None)

        report["removed"] += 1
        report["items"].append({"date": previous_date, "action": "removed-stale"})

    for batch in batches:
        date_key = batch.activity_date.isoformat()
        existing = manager.calculator.get_session(batch.activity_date)
        existing_state = state["days"].get(date_key)
        same_fingerprint = bool(
            existing_state and existing_state.get("fingerprint") == batch.fingerprint()
        )

        if existing and same_fingerprint and existing.description.startswith("[garmin-sync]"):
            report["skipped"] += 1
            report["items"].append(
                {
                    "date": date_key,
                    "action": "skipped-unchanged",
                    "activity_count": batch.activity_count,
                }
            )
            continue

        action = "updated" if existing else "added"

        if not dry_run:
            manager.add_activity(
                session_date=batch.activity_date,
                trimp=batch.trimp,
                sport=batch.primary_sport,
                duration_min=batch.duration_min,
                description=f"[garmin-sync] {batch.activity_count} activities, distance={batch.distance_km:.2f}km",
            )
            state["days"][date_key] = {
                "source": batch.source,
                "external_ids": batch.external_ids,
                "activity_count": batch.activity_count,
                "trimp": batch.trimp,
                "duration_min": batch.duration_min,
                "fingerprint": batch.fingerprint(),
            }

        report[action] += 1
        report["items"].append(
            {
                "date": date_key,
                "action": action,
                "activity_count": batch.activity_count,
                "trimp": batch.trimp,
                "duration_min": batch.duration_min,
            }
        )

    if not dry_run:
        _save_state(state)
    return report
