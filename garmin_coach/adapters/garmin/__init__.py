from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, List, Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from garmin_coach.adapters import Activity, DailySummary, DataSource, UserProfile
from garmin_coach.logging_config import log_error, log_warning
from garmin_coach.models import (
    ActivitySummary,
    BodyBatteryData,
    BodyCompositionData,
    HRVData,
    RHRData,
    SleepData,
    SpO2Data,
    StressData,
    TrainingReadinessData,
)

from .activity import enrich_activity_summary
from .auth import authenticate_credentials, ensure_secure_directory, validate_token_store
from .client import garmin_client
from .health import (
    parse_body_battery,
    parse_body_composition,
    parse_hrv_data,
    parse_rhr_data,
    parse_sleep_data,
    parse_spo2_data,
    parse_stress_data,
    parse_training_readiness,
)

# garth-compatible facade: existing call sites and test monkeypatches keep
# working against the module attribute named "garth".
garth = garmin_client

GARTH_HOME = os.path.expanduser(
    os.getenv("GARMINTOKENS") or os.getenv("GARTH_HOME") or "~/.garminconnect"
)


def _connectapi_first_success(paths: list[str]) -> Any:
    last_exc = None
    for path in paths:
        try:
            result = garth.connectapi(path)
            if result:
                return result
        except Exception as exc:
            last_exc = exc
    if last_exc and len(paths) == 1:
        raise last_exc
    if last_exc:
        return None
    return None


def _looks_like_user_profile(data: Any) -> bool:
    return isinstance(data, dict) and any(
        data.get(key)
        for key in ("displayName", "fullName", "firstName", "userId", "id", "profileId")
    )


def mps_to_pace_sec_per_km(mps: float) -> Optional[float]:
    if mps <= 0:
        return None
    return 1000.0 / mps


def seconds_to_hms(seconds: int) -> str:
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class GarminAdapter(DataSource):
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._profile_cache = None

    def is_authenticated(self) -> bool:
        try:
            validate_token_store(garth, GARTH_HOME)
            _connectapi_first_success(["/userprofile-service/socialProfile", "/usersettings"])
            return True
        except Exception as e:
            log_error("Garmin API error in is_authenticated", exc=e)
            return False

    def authenticate(self, credentials: dict) -> bool:
        try:
            if authenticate_credentials(garth, GARTH_HOME, credentials):
                return self.is_authenticated()
        except Exception as e:
            log_error("Garmin authentication failed", exc=e)
        return self.is_authenticated()

    def get_profile(self) -> Optional[UserProfile]:
        if self._profile_cache:
            return self._profile_cache
        try:
            garth.resume(GARTH_HOME)
            user = _connectapi_first_success(
                ["/userprofile-service/socialProfile", "/usersettings"]
            )
            if not _looks_like_user_profile(user):
                try:
                    user = garth.connectapi("/usersettings")
                except Exception:
                    user = None
            try:
                user_info = garth.connectapi("/usersummary") or {}
            except Exception:
                user_info = {}
            if not isinstance(user, dict) or not user:
                return None
            if not isinstance(user_info, dict):
                user_info = {}
            display_name = (
                user.get("fullName")
                or user.get("displayName")
                or user.get("firstName")
                or "Athlete"
            )
            age = user.get("age")
            weight = user.get("weight") or user_info.get("weight")
            max_hr = user.get("maxHeartRate")
            rest_hr = user_info.get("restingHeartRate")
            ftp = (
                user_info.get("cyclingSettings", {}).get("ftp")
                if isinstance(user_info.get("cyclingSettings"), dict)
                else None
            )
            sports = []
            if "sports" in user_info:
                sports = [
                    s.get("sportType", {}).get("typeKey", "unknown") for s in user_info["sports"]
                ]
            self._profile_cache = UserProfile(
                user_id=str(
                    user.get("userId") or user.get("id") or user.get("profileId") or "garmin_user"
                ),
                name=display_name,
                age=age,
                weight_kg=weight,
                max_heart_rate=max_hr,
                resting_heart_rate=rest_hr,
                ftp=ftp,
                sport_preferences=sports,
            )
            return self._profile_cache
        except Exception as e:
            log_error("Garmin API error in get_profile", exc=e)
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    def get_activities(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        sport_type: Optional[str] = None,
    ) -> List[Activity]:
        try:
            garth.resume(GARTH_HOME)
        except Exception as e:
            log_error("Garmin API error in get_activities", exc=e)
            return []
        if end_date is None:
            end_date = datetime.now()
        try:
            raw_activities = garth.get_activities_by_date(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                sport_type,
            )
        except Exception as e:
            log_error("Garmin API error fetching activities", exc=e)
            return []
        activities = []
        for act in raw_activities or []:
            if not isinstance(act, dict):
                continue
            act_type = act.get("activityType")
            act_sport = act_type.get("typeKey") if isinstance(act_type, dict) else None
            if sport_type and act_sport != sport_type:
                continue
            start_time = None
            raw_start = act.get("startTimeLocal") or act.get("startTimeGMT")
            if raw_start:
                try:
                    start_time = datetime.fromisoformat(str(raw_start))
                except Exception:
                    continue
            duration = act.get("duration") or 0
            avg_speed = act.get("averageSpeed") or 0
            activities.append(
                Activity(
                    activity_id=str(act.get("activityId", "")),
                    name=act.get("activityName") or "Unknown",
                    sport_type=act_sport or "unknown",
                    start_time=start_time or start_date,
                    duration_seconds=int(duration) if duration else 0,
                    distance_meters=act.get("distance"),
                    calories=act.get("calories"),
                    heart_rate_avg=act.get("averageHR"),
                    heart_rate_max=act.get("maxHR"),
                    power_avg=act.get("avgPower") or act.get("averagePower"),
                    pace_sec_per_km=mps_to_pace_sec_per_km(avg_speed) if avg_speed else None,
                    elevation_gain=act.get("elevationGain"),
                    raw_data={"garmin": True, "activity": act},
                )
            )
        return activities

    def get_daily_summary(self, date: datetime) -> Optional[DailySummary]:
        try:
            garth.resume(GARTH_HOME)
            summary = garth.get_user_summary(date.strftime("%Y-%m-%d"))
            if not summary or not isinstance(summary, dict):
                return None
            activities = self.get_activities(date, date)
            total_duration = sum(a.duration_seconds for a in activities)
            total_distance = sum(a.distance_meters or 0 for a in activities) / 1000
            total_calories = sum(a.calories or 0 for a in activities)
            status = summary.get("trainingStatus") or {}
            ctl = status.get("ctl", 0) if isinstance(status, dict) else 0
            atl = status.get("atl", 0) if isinstance(status, dict) else 0
            tsb = ctl - atl if ctl and atl else 0
            trimp = summary.get("hrTrimp", 0) or 0
            return DailySummary(
                date=date,
                ctl=float(ctl),
                atl=float(atl),
                tsb=float(tsb),
                trimp=float(trimp),
                activities=activities,
                total_duration_minutes=int(total_duration / 60),
                total_distance_km=float(total_distance),
                total_calories=int(total_calories),
            )
        except Exception as e:
            log_error("Garmin API error in get_daily_summary", exc=e)
            return None

    def get_time_series(
        self, metric: str, start_date: datetime, end_date: Optional[datetime] = None
    ) -> List[tuple]:
        if end_date is None:
            end_date = datetime.now()
        data = []
        current = start_date
        while current <= end_date:
            summary = self.get_daily_summary(current)
            if summary:
                value = getattr(summary, metric, None)
                if value is not None:
                    data.append((current, value))
            current += timedelta(days=1)
        return data

    def get_activity_details(self, activity_id: str) -> dict[str, Any]:
        try:
            garth.resume(GARTH_HOME)
            details = getattr(garth, "connectapi")(
                f"/activity-service/activity/{activity_id}/details"
            )
            return details if isinstance(details, dict) else {}
        except Exception as exc:
            log_warning(f"Failed to fetch Garmin activity details for {activity_id}: {exc}")
            return {}

    def get_activity_summary(self, activity_id: str) -> ActivitySummary | None:
        details = self.get_activity_details(activity_id)
        if not details:
            return None
        base = ActivitySummary(
            activity_id=activity_id,
            type=details.get("activityTypeDTO", {}).get("typeKey")
            if isinstance(details.get("activityTypeDTO"), dict)
            else details.get("activityType"),
            sport_type=details.get("activityTypeDTO", {}).get("typeKey")
            if isinstance(details.get("activityTypeDTO"), dict)
            else details.get("activityType"),
            start_time=details.get("startTimeLocal") or details.get("startTimeGMT"),
            distance_km=((details.get("distance") or 0) / 1000)
            if details.get("distance") is not None
            else None,
            duration_min=((details.get("duration") or 0) / 60)
            if details.get("duration") is not None
            else None,
            avg_hr=details.get("averageHR") or details.get("averageHeartRate"),
            max_hr=details.get("maxHR") or details.get("maxHeartRate"),
            avg_power=details.get("averagePower"),
            calories=details.get("calories"),
            raw=details,
        )
        return enrich_activity_summary(base, details)

    def _retry_health_call(self, func_name: str, *args: Any) -> Any:
        ensure_secure_directory(GARTH_HOME)
        for attempt in range(3):
            try:
                garth.resume(GARTH_HOME)
                func = getattr(garth, func_name, None)
                if callable(func):
                    return func(*args)
                endpoint = {
                    "get_sleep_data": "/wellness-service/wellness/dailySleepData/{date}",
                    "get_hrv_data": "/wellness-service/wellness/hrv/{date}",
                    "get_body_battery": "/wellness-service/wellness/bodyBattery/{start}/{end}",
                    "get_stress_data": "/wellness-service/wellness/dailyStress/{date}",
                    "get_resting_heart_rate": "/userstats-service/wellness/daily/{date}",
                    "get_spo2_data": "/wellness-service/wellness/dailyPulseOx/{date}",
                    "get_body_composition": "/weight-service/weight/dateRange/{date}/{date}",
                    "get_training_readiness": "/wellness-service/wellness/trainingReadiness/{date}",
                }.get(func_name)
                if endpoint:
                    if not args:
                        return None
                    first_arg = args[0]
                    end_arg = args[1] if len(args) > 1 else first_arg
                    formatted = endpoint.format(date=first_arg, start=first_arg, end=end_arg)
                    return garth.connectapi(formatted)
                return None
            except Exception as exc:
                if attempt == 2:
                    log_warning(f"Garmin health call {func_name} failed: {exc}")
                    return None
        return None

    def get_sleep_data(self, date_str: str) -> SleepData | None:
        return parse_sleep_data(self._retry_health_call("get_sleep_data", date_str))

    def get_hrv_data(self, date_str: str) -> HRVData | None:
        return parse_hrv_data(self._retry_health_call("get_hrv_data", date_str))

    def get_body_battery(self, start_str: str, end_str: str) -> BodyBatteryData | None:
        return parse_body_battery(self._retry_health_call("get_body_battery", start_str, end_str))

    def get_stress_data(self, date_str: str) -> StressData | None:
        return parse_stress_data(self._retry_health_call("get_stress_data", date_str))

    def get_rhr_day(self, date_str: str) -> RHRData | None:
        return parse_rhr_data(self._retry_health_call("get_resting_heart_rate", date_str))

    def get_spo2_data(self, date_str: str) -> SpO2Data | None:
        return parse_spo2_data(self._retry_health_call("get_spo2_data", date_str))

    def get_body_composition(self, date_str: str) -> BodyCompositionData | None:
        payload = self._retry_health_call("get_body_composition", date_str)
        if isinstance(payload, list):
            payload = payload[0] if payload else None
        return parse_body_composition(payload)

    def get_training_readiness(self, date_str: str) -> TrainingReadinessData | None:
        return parse_training_readiness(self._retry_health_call("get_training_readiness", date_str))


__all__ = [
    "GARTH_HOME",
    "GarminAdapter",
    "_connectapi_first_success",
    "_looks_like_user_profile",
    "garth",
    "datetime",
    "mps_to_pace_sec_per_km",
    "seconds_to_hms",
]
