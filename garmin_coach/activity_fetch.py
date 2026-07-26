"""Garmin data fetching layer (legacy shim over the garminconnect facade).

Historically this module called garth directly. garth is dead (Garmin's 2026
auth changes), so it now delegates to
:mod:`garmin_coach.adapters.garmin.client`. Public function signatures are
unchanged so morning_checkin / coach_engine / telegram_bot keep working.

Payload extraction is dual-shape: it accepts both attribute-style objects
(garth's typed classes, still used by the test-suite fixtures) and the plain
camelCase dicts garminconnect returns.
"""

import os
from datetime import date, datetime
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from garmin_coach.adapters.garmin.client import garmin_client
from garmin_coach.logging_config import log_error, log_warning

try:
    from garminconnect import (
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )

    _RETRYABLE_API_EXCEPTIONS: tuple[type[Exception], ...] = (
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )
except Exception:  # pragma: no cover - garminconnect always present in prod
    _RETRYABLE_API_EXCEPTIONS = ()

GARTH_HOME = os.path.expanduser(
    os.getenv("GARMINTOKENS") or os.getenv("GARTH_HOME") or "~/.garminconnect"
)

GARTH_RETRYABLE_EXCEPTIONS = _RETRYABLE_API_EXCEPTIONS + (ConnectionError, TimeoutError)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(GARTH_RETRYABLE_EXCEPTIONS),
    reraise=True,
)
def _execute_garth_call(operation: str, fn):
    try:
        return fn()
    except GARTH_RETRYABLE_EXCEPTIONS as exc:
        log_warning(f"Retrying Garmin operation: {operation}", exc=exc)
        raise


def _field(obj: Any, *names: str, default: Any = None) -> Any:
    """Read the first present field from a dict key or object attribute."""
    if obj is None:
        return default
    for name in names:
        if isinstance(obj, dict):
            value = obj.get(name)
        else:
            value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def resume_garth() -> bool:
    try:
        _execute_garth_call("resume session", lambda: garmin_client.resume(GARTH_HOME))
        return True
    except Exception as exc:
        log_error("Failed to resume Garmin session", exc=exc)
        return False


def safe_get_daily_summary(target_date: str) -> Any:
    try:
        return _execute_garth_call(
            f"daily summary for {target_date}",
            lambda: garmin_client.get_user_summary(target_date),
        )
    except Exception as exc:
        log_error(f"Failed to fetch daily summary for {target_date}", exc=exc)
        return None


def safe_get_sleep(target_date: str) -> Any:
    try:
        return _execute_garth_call(
            f"sleep data for {target_date}",
            lambda: garmin_client.get_sleep_data(target_date),
        )
    except Exception as exc:
        log_error(f"Failed to fetch sleep data for {target_date}", exc=exc)
        return None


def safe_get_body_battery(target_date: str) -> Any:
    try:
        return _execute_garth_call(
            f"body battery for {target_date}",
            lambda: garmin_client.get_body_battery(target_date),
        )
    except Exception as exc:
        log_error(f"Failed to fetch body battery for {target_date}", exc=exc)
        return None


def safe_get_training_readiness(target_date: str) -> Any:
    try:
        return _execute_garth_call(
            f"training readiness for {target_date}",
            lambda: garmin_client.get_training_readiness(target_date),
        )
    except Exception as exc:
        log_error(f"Failed to fetch training readiness for {target_date}", exc=exc)
        return None


def safe_get_daily_hr(target_date: str) -> Any:
    try:
        return _execute_garth_call(
            f"daily heart rate for {target_date}",
            lambda: garmin_client.get_heart_rates(target_date),
        )
    except Exception as exc:
        log_error(f"Failed to fetch HR for {target_date}", exc=exc)
        return None


def safe_get_activities(limit: int = 10) -> list[Any]:
    try:
        result = _execute_garth_call(
            f"activities list limit={limit}",
            lambda: garmin_client.get_activities(0, limit),
        )
        return result if isinstance(result, list) else []
    except Exception as exc:
        log_error(f"Failed to fetch activities (limit={limit})", exc=exc)
        return []


def extract_sleep_hours(sleep_data: Any) -> float | None:
    if not isinstance(sleep_data, dict):
        return None
    for key in ("sleepTimeSeconds", "sleepTime", "totalSleepSeconds"):
        value = sleep_data.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return round(value / 3600, 2)
    return None


def _extract_sleep_raw(sleep_obj: Any) -> dict[str, Any] | None:
    dto = _field(sleep_obj, "daily_sleep_dto", "dailySleepDTO")
    if not dto:
        return None
    scores = _field(dto, "sleep_scores", "sleepScores")
    overall = _field(scores, "overall") if scores else None
    return {
        "sleepTimeSeconds": _field(dto, "sleep_time_seconds", "sleepTimeSeconds"),
        "deepSleepSeconds": _field(dto, "deep_sleep_seconds", "deepSleepSeconds"),
        "lightSleepSeconds": _field(dto, "light_sleep_seconds", "lightSleepSeconds"),
        "remSleepSeconds": _field(dto, "rem_sleep_seconds", "remSleepSeconds"),
        "awakeSleepSeconds": _field(dto, "awake_sleep_seconds", "awakeSleepSeconds"),
        "awakeCount": _field(dto, "awake_count", "awakeCount"),
        "overallScore": _field(overall, "value") if overall else None,
        "overallQualifier": (
            _field(overall, "qualifier_key", "qualifierKey") if overall else None
        ),
    }


def _extract_body_battery(summary: Any, body_battery_obj: Any) -> Any:
    value = _field(
        summary,
        "body_battery_at_wake_time",
        "bodyBatteryAtWakeTime",
        "bodyBatteryMostRecentValue",
    )
    if value is not None or not isinstance(body_battery_obj, list) or not body_battery_obj:
        return value
    impacts = []
    samples = []
    for event in body_battery_obj:
        impact = getattr(getattr(event, "event", None), "body_battery_impact", None)
        if impact is not None:
            impacts.append(impact)
        if isinstance(event, dict):
            for point in event.get("bodyBatteryValuesArray") or []:
                if isinstance(point, (list, tuple)) and len(point) > 1 and point[1] is not None:
                    samples.append(point[1])
    try:
        if impacts:
            return max(impacts)
        if samples:
            return samples[-1]
    except Exception as exc:
        log_warning("Failed to extract body battery from Garmin payload", exc=exc)
    return None


def fetch_morning_metrics(target_date: str) -> dict[str, Any]:
    summary = safe_get_daily_summary(target_date)
    sleep_obj = safe_get_sleep(target_date)
    body_battery_obj = safe_get_body_battery(target_date)
    readiness_obj = safe_get_training_readiness(target_date)
    daily_hr_obj = safe_get_daily_hr(target_date)

    sleep_raw = _extract_sleep_raw(sleep_obj)
    sleep_hours = extract_sleep_hours(sleep_raw) if sleep_raw else None

    if isinstance(readiness_obj, list):
        readiness_obj = readiness_obj[0] if readiness_obj else None
    readiness_value = _field(readiness_obj, "score")
    hrv_feedback = _field(
        readiness_obj, "hrv_factor_feedback", "hrvFactorFeedback", "hrvFactor"
    )
    hrv_status = hrv_feedback.lower() if isinstance(hrv_feedback, str) and hrv_feedback else None

    resting_hr = _field(daily_hr_obj, "resting_heart_rate", "restingHeartRate")
    if resting_hr is None:
        resting_hr = _field(summary, "resting_heart_rate", "restingHeartRate")

    return {
        "sleep_hours": sleep_hours,
        "resting_hr": resting_hr,
        "body_battery": _extract_body_battery(summary, body_battery_obj),
        "training_readiness": readiness_value,
        "hrv_status": hrv_status,
        "raw": {
            "summary": summary,
            "sleep": sleep_raw,
            "body_battery_obj": str(body_battery_obj)[:500] if body_battery_obj else None,
            "readiness_obj": str(readiness_obj)[:500] if readiness_obj else None,
        },
    }


def mps_to_pace_str(mps: float) -> str:
    if mps <= 0:
        return ""
    min_per_km = 1000.0 / 60.0 / mps
    return f"{int(min_per_km)}:{int((min_per_km % 1) * 60):02d}/km"


def fetch_recent_activities(
    limit: int | date = 5, end_date: date | None = None
) -> list[dict[str, Any]]:
    limit_count = limit if isinstance(limit, int) else 100
    raw_activities = safe_get_activities(limit=limit_count)
    results = []
    for act in raw_activities:
        act_type = _field(act, "activity_type", "activityType")
        type_key = (_field(act_type, "type_key", "typeKey", default="") or "") if act_type else ""

        start_local = None
        raw_start = _field(act, "start_time_local", "startTimeLocal")
        if raw_start:
            start_local = (
                raw_start.isoformat() if isinstance(raw_start, datetime) else str(raw_start)
            )

        distance_m = _field(act, "distance")
        distance_km = round(distance_m / 1000, 2) if distance_m else None

        duration_s = _field(act, "duration")
        duration_min = round(duration_s / 60, 1) if duration_s else None

        avg_speed = _field(act, "average_speed", "averageSpeed")
        pace_str = mps_to_pace_str(avg_speed) if avg_speed else None

        avg_hr = _field(act, "average_hr", "averageHR")
        if avg_hr is not None:
            avg_hr = int(avg_hr)

        item = {
            "activity_id": str(_field(act, "activity_id", "activityId", default="") or ""),
            "type": type_key,
            "start_time": start_local,
            "distance_km": distance_km,
            "duration_min": duration_min,
            "avg_pace": pace_str,
            "avg_hr": avg_hr,
            "calories": _field(act, "calories"),
            "activity_name": _field(act, "activity_name", "activityName", default="") or "",
        }

        if isinstance(limit, date):
            try:
                activity_date = (
                    datetime.fromisoformat(start_local.replace(" ", "T")).date()
                    if start_local
                    else None
                )
            except Exception:
                activity_date = None
            if activity_date is None:
                continue
            range_end = end_date or limit
            if not (limit <= activity_date <= range_end):
                continue

        results.append(item)
    return results
