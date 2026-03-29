import os
from datetime import datetime, timedelta
from typing import List, Optional

import requests

from garmin_coach.adapters import (
    Activity,
    DataSource,
    DailySummary,
    UserProfile,
)


STRAVA_CONFIG_DIR = os.path.expanduser("~/.config/garmin_coach")


def get_strava_token() -> Optional[dict]:
    token_file = os.path.join(STRAVA_CONFIG_DIR, "strava_token.json")
    if not os.path.exists(token_file):
        return None
    try:
        import json

        with open(token_file) as f:
            return json.load(f)
    except Exception:
        return None


def save_strava_token(token_data: dict):
    os.makedirs(STRAVA_CONFIG_DIR, exist_ok=True)
    token_file = os.path.join(STRAVA_CONFIG_DIR, "strava_token.json")
    import json

    with open(token_file, "w") as f:
        json.dump(token_data, f)


class StravaAdapter(DataSource):
    """Adapter for Strava API."""

    API_BASE = "https://www.strava.com/api/v3"

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._token = None
        self._profile_cache = None

    def _get_headers(self) -> dict:
        if not self._token:
            self._token = get_strava_token()
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token.get('access_token')}"}

    def is_authenticated(self) -> bool:
        token = get_strava_token()
        if not token:
            return False
        return True

    def authenticate(self, credentials: dict) -> bool:
        access_token = credentials.get("access_token")
        if not access_token:
            return False

        save_strava_token(
            {
                "access_token": access_token,
                "refresh_token": credentials.get("refresh_token", ""),
                "expires_at": credentials.get("expires_at", 0),
            }
        )
        self._token = None
        return self.is_authenticated()

    def get_profile(self) -> Optional[UserProfile]:
        if self._profile_cache:
            return self._profile_cache
        headers = self._get_headers()
        if not headers:
            return None

        try:
            resp = requests.get(f"{self.API_BASE}/athlete", headers=headers, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()

            sports = []
            for activity_type in data.get("athlete_type", {}).get("code", []):
                sports.append(activity_type)

            self._profile_cache = UserProfile(
                user_id=str(data.get("id", "strava_user")),
                name=f"{data.get('firstname', '')} {data.get('lastname', '')}".strip(),
                age=None,
                weight_kg=None,
                max_heart_rate=None,
                resting_heart_rate=None,
                ftp=None,
                sport_preferences=sports or ["running", "cycling"],
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
        headers = self._get_headers()
        if not headers:
            return []

        if end_date is None:
            end_date = datetime.now()

        activities = []
        page = 1
        per_page = 100

        while True:
            try:
                params = {
                    "after": int(start_date.timestamp()),
                    "per_page": per_page,
                    "page": page,
                }
                resp = requests.get(
                    f"{self.API_BASE}/activities",
                    headers=headers,
                    params=params,
                    timeout=10,
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data:
                    break

                for act in data:
                    act_type = act.get("type", "").lower()
                    if sport_type and act_type != sport_type.lower():
                        continue

                    start_time = datetime.fromisoformat(
                        act["start_date"].replace("Z", "+00:00")
                    )

                    if start_time.date() > end_date.date():
                        continue

                    distance = act.get("distance", 0)
                    elapsed_time = act.get("elapsed_time", 0)
                    avg_speed = act.get("average_speed", 0)

                    pace = None
                    if avg_speed and avg_speed > 0:
                        pace = 1000.0 / avg_speed

                    activities.append(
                        Activity(
                            activity_id=str(act.get("id", "")),
                            name=act.get("name", "Unknown"),
                            sport_type=act_type,
                            start_time=start_time,
                            duration_seconds=elapsed_time,
                            distance_meters=distance,
                            calories=act.get("calories"),
                            heart_rate_avg=act.get("average_heartrate"),
                            heart_rate_max=act.get("max_heartrate"),
                            power_avg=act.get("average_watts"),
                            pace_sec_per_km=pace,
                            elevation_gain=act.get("total_elevation_gain"),
                            raw_data={"strava": True, "activity": act},
                        )
                    )

                if len(data) < per_page:
                    break
                page += 1
            except Exception:
                break

        return activities

    def get_daily_summary(self, date: datetime) -> Optional[DailySummary]:
        start_of_day = datetime(date.year, date.month, date.day)
        end_of_day = start_of_day + timedelta(days=1) - timedelta(seconds=1)

        activities = self.get_activities(start_of_day, end_of_day)

        if not activities:
            return None

        total_duration = sum(a.duration_seconds for a in activities)
        total_distance = sum(a.distance_meters or 0 for a in activities) / 1000
        total_calories = sum(a.calories or 0 for a in activities)

        ctl = len(activities) * 5.0
        atl = len(activities) * 3.0
        tsb = ctl - atl

        trimp = sum(
            a.heart_rate_avg or 50 * a.duration_seconds / 60 for a in activities
        )

        return DailySummary(
            date=date,
            ctl=ctl,
            atl=atl,
            tsb=tsb,
            trimp=trimp,
            activities=activities,
            total_duration_minutes=total_duration // 60,
            total_distance_km=round(total_distance, 2),
            total_calories=total_calories,
        )

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
