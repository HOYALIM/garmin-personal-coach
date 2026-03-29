import os
from datetime import datetime, timedelta
from typing import List, Optional

import garth

from garmin_coach.adapters import (
    Activity,
    DataSource,
    DailySummary,
    UserProfile,
)


GARTH_HOME = os.path.expanduser(os.getenv("GARTH_HOME", "~/.garth"))


def mps_to_pace_sec_per_km(mps: float) -> Optional[float]:
    if mps <= 0:
        return None
    return 1000.0 / mps


def seconds_to_hms(seconds: int) -> str:
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class GarminAdapter(DataSource):
    """Adapter for Garmin Connect using garth."""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._profile_cache = None

    def is_authenticated(self) -> bool:
        try:
            garth.resume(GARTH_HOME)
            garth.connectapi("/usersettings", max_retries=1)
            return True
        except Exception:
            return False

    def authenticate(self, credentials: dict) -> bool:
        return self.is_authenticated()

    def get_profile(self) -> Optional[UserProfile]:
        if self._profile_cache:
            return self._profile_cache
        try:
            garth.resume(GARTH_HOME)
            user = garth.connectapi("/usersettings")
            user_info = garth.connectapi("/usersummary")

            if not user:
                return None

            display_name = user.get("displayName") or user.get("firstName", "Athlete")
            age = user.get("age")
            weight = user.get("weight") or user_info.get("weight")
            max_hr = user.get("maxHeartRate")
            rest_hr = user_info.get("restingHeartRate")

            ftp = None
            if user_info and "cyclingSettings" in user_info:
                ftp = user_info["cyclingSettings"].get("ftp")

            sports = []
            if user_info and "sports" in user_info:
                sports = [
                    s.get("sportType", {}).get("typeKey", "unknown")
                    for s in user_info["sports"]
                ]

            self._profile_cache = UserProfile(
                user_id=user.get("userId", "garmin_user"),
                name=display_name,
                age=age,
                weight_kg=weight,
                max_heart_rate=max_hr,
                resting_heart_rate=rest_hr,
                ftp=ftp,
                sport_preferences=sports,
            )
            return self._profile_cache
        except Exception:
            return None

    def get_activities(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        sport_type: Optional[str] = None,
    ) -> List[Activity]:
        try:
            garth.resume(GARTH_HOME)
        except Exception:
            return []

        if end_date is None:
            end_date = datetime.now()

        activities = []
        current_date = start_date
        while current_date <= end_date:
            try:
                daily = garth.DailySummary.get(current_date.strftime("%Y-%m-%d"))
                if daily:
                    for act in daily:
                        act_sport = (
                            getattr(act.activity_type, "type_key", None)
                            if hasattr(act, "activity_type")
                            else None
                        )
                        if sport_type and act_sport != sport_type:
                            continue

                        start_time = getattr(act, "start_time_local", None)
                        if start_time and not isinstance(start_time, datetime):
                            start_time = datetime.fromisoformat(str(start_time))

                        distance = getattr(act, "distance", None)
                        duration = getattr(act, "duration", 0)
                        avg_speed = getattr(act, "average_speed", 0)

                        activities.append(
                            Activity(
                                activity_id=str(getattr(act, "activity_id", "")),
                                name=getattr(act, "activity_name", "Unknown"),
                                sport_type=act_sport or "unknown",
                                start_time=start_time or current_date,
                                duration_seconds=int(duration) if duration else 0,
                                distance_meters=distance,
                                calories=getattr(act, "calories", None),
                                heart_rate_avg=getattr(act, "average_heart_rate", None),
                                heart_rate_max=getattr(act, "max_heart_rate", None),
                                power_avg=getattr(act, "average_power", None),
                                pace_sec_per_km=mps_to_pace_sec_per_km(avg_speed)
                                if avg_speed
                                else None,
                                elevation_gain=getattr(act, "elevation_gain", None),
                                raw_data={"garmin": True, "activity": str(act)[:200]},
                            )
                        )
            except Exception:
                pass
            current_date += timedelta(days=1)

        return activities

    def get_daily_summary(self, date: datetime) -> Optional[DailySummary]:
        try:
            garth.resume(GARTH_HOME)
            summary = garth.DailySummary.get(date.strftime("%Y-%m-%d"))
            if not summary:
                return None

            activities = self.get_activities(date, date)
            total_duration = sum(a.duration_seconds for a in activities)
            total_distance = sum(a.distance_meters or 0 for a in activities) / 1000
            total_calories = sum(a.calories or 0 for a in activities)

            ctl = getattr(summary, "training_status", {}).get("ctl", 0)
            atl = getattr(summary, "training_status", {}).get("atl", 0)
            tsb = ctl - atl if ctl and atl else 0

            trimp = getattr(summary, "hr_trimp", 0)

            return DailySummary(
                date=date,
                ctl=float(ctl),
                atl=float(atl),
                tsb=float(tsb),
                trimp=float(trimp),
                activities=activities,
                total_duration_minutes=total_duration // 60,
                total_distance_km=round(total_distance, 2),
                total_calories=total_calories,
            )
        except Exception:
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
