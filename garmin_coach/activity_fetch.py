"""Garmin data fetching layer (garth adapter)."""

import os
from datetime import date, datetime
from typing import Any

import garth
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from garmin_coach.logging_config import log_error, log_warning


GARTH_HOME = os.path.expanduser(os.getenv("GARTH_HOME", "~/.garth"))

GARTH_RETRYABLE_EXCEPTIONS = tuple(
    exc
    for exc in (getattr(garth, "GarthException", None), ConnectionError, TimeoutError)
    if exc is not None
) or (Exception,)


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


def resume_garth() -> bool:
    try:
        _execute_garth_call("resume session", lambda: garth.resume(GARTH_HOME))
        return True
    except Exception as exc:
        log_error("Failed to resume Garmin session", exc=exc)
        return False


def safe_get_daily_summary(target_date: str) -> Any:
    try:
        return _execute_garth_call(
            f"daily summary for {target_date}", lambda: garth.DailySummary.get(target_date)
        )
    except Exception as exc:
        log_error(f"Failed to fetch daily summary for {target_date}", exc=exc)
        return None


def safe_get_sleep(target_date: str) -> Any:
    try:
        return _execute_garth_call(
            f"sleep data for {target_date}", lambda: garth.SleepData.get(target_date)
        )
    except Exception as exc:
        log_error(f"Failed to fetch sleep data for {target_date}", exc=exc)
        return None


def safe_get_body_battery(target_date: str) -> Any:
    try:
        return _execute_garth_call(
            f"body battery for {target_date}", lambda: garth.BodyBatteryData.get(target_date)
        )
    except Exception as exc:
        log_error(f"Failed to fetch body battery for {target_date}", exc=exc)
        return None


def safe_get_training_readiness(target_date: str) -> Any:
    try:
        return _execute_garth_call(
            f"training readiness for {target_date}",
            lambda: garth.MorningTrainingReadinessData.get(target_date),
        )
    except Exception as exc:
        log_error(f"Failed to fetch training readiness for {target_date}", exc=exc)
        return None


def safe_get_daily_hr(target_date: str) -> Any:
    try:
        return _execute_garth_call(
            f"daily heart rate for {target_date}", lambda: garth.DailyHeartRate.get(target_date)
        )
    except Exception as exc:
        log_error(f"Failed to fetch HR for {target_date}", exc=exc)
        return None


def safe_get_activities(limit: int = 10) -> list[Any]:
    try:
        return _execute_garth_call(
            f"activities list limit={limit}", lambda: garth.Activity.list(limit=limit)
        )
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


def fetch_morning_metrics(target_date: str) -> dict[str, Any]:
    summary = safe_get_daily_summary(target_date)
    sleep_obj = safe_get_sleep(target_date)
    body_battery_obj = safe_get_body_battery(target_date)
    readiness_obj = safe_get_training_readiness(target_date)
    daily_hr_obj = safe_get_daily_hr(target_date)

    sleep_hours = None
    sleep_raw = None
    if sleep_obj and getattr(sleep_obj, "daily_sleep_dto", None):
        dto = sleep_obj.daily_sleep_dto
        sleep_raw = {
            "sleepTimeSeconds": dto.sleep_time_seconds,
            "deepSleepSeconds": dto.deep_sleep_seconds,
            "lightSleepSeconds": dto.light_sleep_seconds,
            "remSleepSeconds": dto.rem_sleep_seconds,
            "awakeSleepSeconds": dto.awake_sleep_seconds,
            "awakeCount": dto.awake_count,
            "overallScore": getattr(dto.sleep_scores.overall, "value", None)
            if dto.sleep_scores
            else None,
            "overallQualifier": getattr(dto.sleep_scores.overall, "qualifier_key", None)
            if dto.sleep_scores
            else None,
        }
        sleep_hours = extract_sleep_hours(sleep_raw)

    body_battery_value = getattr(summary, "body_battery_at_wake_time", None) if summary else None
    if body_battery_value is None and isinstance(body_battery_obj, list) and body_battery_obj:
        try:
            body_battery_value = max(
                event.event.body_battery_impact
                for event in body_battery_obj
                if getattr(getattr(event, "event", None), "body_battery_impact", None) is not None
            )
        except Exception as exc:
            log_warning("Failed to extract body battery from Garmin payload", exc=exc)
            body_battery_value = None

    readiness_value = getattr(readiness_obj, "score", None) if readiness_obj else None
    hrv_feedback = getattr(readiness_obj, "hrv_factor_feedback", None) if readiness_obj else None
    hrv_status = hrv_feedback.lower() if isinstance(hrv_feedback, str) and hrv_feedback else None

    return {
        "sleep_hours": sleep_hours,
        "resting_hr": (
            getattr(daily_hr_obj, "resting_heart_rate", None)
            if daily_hr_obj
            else getattr(summary, "resting_heart_rate", None)
            if summary
            else None
        ),
        "body_battery": body_battery_value,
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
        type_key = ""
        if hasattr(act, "activity_type") and act.activity_type:
            type_key = getattr(act.activity_type, "type_key", "") or ""

        start_local = None
        if hasattr(act, "start_time_local") and act.start_time_local:
            st = act.start_time_local
            start_local = st.isoformat() if isinstance(st, datetime) else str(st)

        distance_m = getattr(act, "distance", None)
        distance_km = round(distance_m / 1000, 2) if distance_m else None

        duration_s = getattr(act, "duration", None)
        duration_min = round(duration_s / 60, 1) if duration_s else None

        avg_speed = getattr(act, "average_speed", None)
        pace_str = mps_to_pace_str(avg_speed) if avg_speed else None

        avg_hr = getattr(act, "average_hr", None)
        if avg_hr is not None:
            avg_hr = int(avg_hr)

        item = {
            "activity_id": str(getattr(act, "activity_id", "") or ""),
            "type": type_key,
            "start_time": start_local,
            "distance_km": distance_km,
            "duration_min": duration_min,
            "avg_pace": pace_str,
            "avg_hr": avg_hr,
            "calories": getattr(act, "calories", None),
            "activity_name": getattr(act, "activity_name", "") or "",
        }

        if isinstance(limit, date):
            try:
                activity_date = datetime.fromisoformat(start_local).date() if start_local else None
            except Exception:
                activity_date = None
            if activity_date is None:
                continue
            range_end = end_date or limit
            if not (limit <= activity_date <= range_end):
                continue

        results.append(item)
    return results
