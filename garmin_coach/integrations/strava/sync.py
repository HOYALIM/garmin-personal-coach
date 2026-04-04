from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from garmin_coach.adapters.strava import StravaAdapter
from garmin_coach.integrations.models import CanonicalDailyActivityBatch
from garmin_coach.logging_config import log_warning
from garmin_coach.training_load import Sport
from garmin_coach.training_load_manager import get_training_load_manager


DATA_DIR = os.path.expanduser("~/.config/garmin_coach")
INTEGRATIONS_DIR = os.path.join(DATA_DIR, "integrations")
STRAVA_SYNC_STATE_FILE = os.path.join(INTEGRATIONS_DIR, "strava_sync_state.json")


def _ensure_dir() -> None:
    os.makedirs(INTEGRATIONS_DIR, exist_ok=True)


def _load_state() -> dict[str, Any]:
    if not os.path.exists(STRAVA_SYNC_STATE_FILE):
        return {"days": {}}
    try:
        with open(STRAVA_SYNC_STATE_FILE) as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {"days": data.get("days", {})}
    except Exception as exc:
        log_warning(f"Failed to read Strava sync state: {exc}")
    return {"days": {}}


def _save_state(state: dict[str, Any]) -> None:
    _ensure_dir()
    with open(STRAVA_SYNC_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.chmod(STRAVA_SYNC_STATE_FILE, 0o600)


def _to_training_sport(sport_type: str) -> Sport:
    raw = (sport_type or "").lower()
    if raw in {"run", "running"}:
        return Sport.RUNNING
    if raw in {"ride", "cycling", "virtualride", "ebikeride"}:
        return Sport.CYCLING
    if raw in {"swim", "swimming"}:
        return Sport.SWIMMING
    if raw in {"triathlon"}:
        return Sport.TRIATHLON
    return Sport.OTHER


def _activity_local_date(activity: Any) -> str:
    raw_data = getattr(activity, "raw_data", None)
    raw_activity = raw_data.get("activity", {}) if isinstance(raw_data, dict) else {}
    start_date_local = raw_activity.get("start_date_local")
    if isinstance(start_date_local, str):
        try:
            return datetime.fromisoformat(start_date_local).date().isoformat()
        except ValueError:
            pass
    return activity.start_time.astimezone().date().isoformat()


def _aggregate_strava_days(days: int, window_start_date=None) -> list[CanonicalDailyActivityBatch]:
    adapter = StravaAdapter()
    if not adapter.is_authenticated():
        raise RuntimeError("Strava is not authenticated. Run 'garmin-coach connect-strava' first.")

    if window_start_date is None:
        window_start_date = (datetime.now() - timedelta(days=days)).date()
    start = datetime.combine(window_start_date, datetime.min.time())
    activities = adapter.get_activities(start)
    manager = get_training_load_manager()
    calculator = manager.calculator.session_calculator

    grouped: dict[str, list] = defaultdict(list)
    for activity in activities:
        grouped[_activity_local_date(activity)].append(activity)

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
            sport = _to_training_sport(activity.sport_type)
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
                source="strava",
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


def sync_strava_training_load(days: int = 30, dry_run: bool = False) -> dict[str, Any]:
    manager = get_training_load_manager()
    state = _load_state()
    window_start_date = (datetime.now() - timedelta(days=days)).date()
    batches = _aggregate_strava_days(days, window_start_date=window_start_date)
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

        if previous_date_obj < window_start_date:
            continue

        if previous_date in current_dates:
            continue

        existing = manager.calculator.get_session(previous_date_obj)
        if not existing:
            # Session was already removed externally; clean up the stale state
            # entry so we don't try to reconcile it again.
            if not dry_run:
                state["days"].pop(previous_date, None)
            continue

        # Ownership guard: verify the session in training_load was written by
        # strava-sync.  If another source (e.g. Garmin) has since imported a
        # session for this day, yield to it and forget our state record rather
        # than deleting data we don't own.
        if not existing.description.startswith("[strava-sync]"):
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
        # Ownership: state record is the primary indicator (we synced this day).
        # Secondary check: if a session exists but does not carry the
        # [strava-sync] description label, another source (e.g. Garmin) has
        # imported it — yield and clear our state record so we stop claiming
        # ownership of this day.
        existing_is_strava = bool(existing_state and existing and existing.description.startswith("[strava-sync]"))
        if existing_state and existing and not existing.description.startswith("[strava-sync]"):
            # Garmin (or another source) has taken over; yield and forget.
            state["days"].pop(date_key, None)
            existing_state = None
        same_fingerprint = bool(
            existing_state and existing_state.get("fingerprint") == batch.fingerprint()
        )

        if existing and not existing_is_strava:
            report["skipped"] += 1
            report["items"].append(
                {"date": date_key, "action": "skipped-existing", "source": "existing-runtime"}
            )
            continue

        action = "updated" if existing_is_strava else "added"
        if existing_is_strava and same_fingerprint:
            report["skipped"] += 1
            report["items"].append(
                {
                    "date": date_key,
                    "action": "skipped-unchanged",
                    "activity_count": batch.activity_count,
                }
            )
            continue

        if not dry_run:
            manager.add_activity(
                session_date=batch.activity_date,
                trimp=batch.trimp,
                sport=batch.primary_sport,
                duration_min=batch.duration_min,
                description=batch.description(),
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
