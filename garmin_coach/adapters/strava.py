import os
import time
from datetime import datetime, timedelta
from typing import List, Optional

import requests

from garmin_coach.adapters import (
    Activity,
    DataSource,
    DailySummary,
    UserProfile,
)
from garmin_coach.logging_config import log_error


STRAVA_CONFIG_DIR = os.path.expanduser("~/.config/garmin_coach")
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
TOKEN_REFRESH_WINDOW_SECONDS = 300


def get_strava_token() -> Optional[dict]:
    token_file = os.path.join(STRAVA_CONFIG_DIR, "strava_token.json")
    if not os.path.exists(token_file):
        return None
    try:
        import json

        with open(token_file) as f:
            return json.load(f)
    except Exception as e:
        log_error("Strava API error in get_strava_token", exc=e)
        return None


def save_strava_token(token_data: dict):
    os.makedirs(STRAVA_CONFIG_DIR, exist_ok=True)
    token_file = os.path.join(STRAVA_CONFIG_DIR, "strava_token.json")
    import json

    with open(token_file, "w") as f:
        json.dump(token_data, f)
    os.chmod(token_file, 0o600)


def _merge_token_data(token_data: dict, previous: Optional[dict] = None) -> dict:
    merged = dict(previous or {})
    merged.update(token_data)

    if previous:
        for key in [
            "client_id",
            "client_secret",
            "accepted_scope",
            "requested_scope",
        ]:
            if key in previous and key not in merged:
                merged[key] = previous[key]

    return merged


def refresh_strava_token(token_data: Optional[dict] = None) -> Optional[dict]:
    token = dict(token_data or get_strava_token() or {})
    if not token:
        return None

    refresh_token = token.get("refresh_token")
    client_id = token.get("client_id")
    client_secret = token.get("client_secret")
    if not all([refresh_token, client_id, client_secret]):
        return None

    try:
        resp = requests.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            log_error(f"Strava token refresh failed with status {resp.status_code}")
            return None

        refreshed = _merge_token_data(resp.json(), token)
        save_strava_token(refreshed)
        return refreshed
    except Exception as e:
        log_error("Strava API error in refresh_strava_token", exc=e)
        return None


def get_valid_strava_token() -> Optional[dict]:
    token = get_strava_token()
    if not token:
        return None

    access_token = token.get("access_token")
    if not access_token:
        return None

    expires_at = token.get("expires_at")
    if not expires_at:
        return token

    now = time.time()
    if expires_at <= now + TOKEN_REFRESH_WINDOW_SECONDS:
        refreshed = refresh_strava_token(token)
        if refreshed and refreshed.get("access_token"):
            return refreshed
        if expires_at > now:
            return token
        return None

    return token


def _ensure_token_fresh(token: Optional[dict]) -> Optional[dict]:
    if not token:
        return None

    expires_at = token.get("expires_at")
    if not expires_at:
        return token

    now = time.time()
    if expires_at <= now + TOKEN_REFRESH_WINDOW_SECONDS:
        refreshed = refresh_strava_token(token)
        if refreshed and refreshed.get("access_token"):
            return refreshed
        if expires_at > now:
            return token
        return None

    return token


class StravaAdapter(DataSource):
    """Adapter for Strava API."""

    API_BASE = "https://www.strava.com/api/v3"

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._token = None
        self._profile_cache = None

    def _get_headers(self) -> dict:
        self._token = _ensure_token_fresh(self._token) or get_valid_strava_token()
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token.get('access_token')}"}

    def is_authenticated(self) -> bool:
        return _ensure_token_fresh(self._token) is not None or get_valid_strava_token() is not None

    def authenticate(self, credentials: dict) -> bool:
        access_token = credentials.get("access_token")
        if not access_token:
            return False

        save_strava_token(credentials)
        self._token = get_valid_strava_token()
        return self.is_authenticated()

    def _request(self, path: str, params: Optional[dict] = None) -> Optional[requests.Response]:
        headers = self._get_headers()
        if not headers:
            return None

        try:
            resp = requests.get(
                f"{self.API_BASE}{path}",
                headers=headers,
                params=params,
                timeout=10,
            )
            if resp.status_code == 401:
                refreshed = refresh_strava_token(self._token)
                if refreshed and refreshed.get("access_token"):
                    self._token = refreshed
                    resp = requests.get(
                        f"{self.API_BASE}{path}",
                        headers={"Authorization": f"Bearer {refreshed['access_token']}"},
                        params=params,
                        timeout=10,
                    )
            return resp
        except Exception as e:
            log_error(f"Strava API request failed for {path}", exc=e)
            return None

    def get_profile(self) -> Optional[UserProfile]:
        if self._profile_cache:
            return self._profile_cache
        resp = self._request("/athlete")
        if not resp:
            return None

        try:
            if resp.status_code != 200:
                return None
            data = resp.json()

            sports = []
            athlete_type = data.get("athlete_type")
            if isinstance(athlete_type, dict):
                codes = athlete_type.get("code", [])
                if isinstance(codes, list):
                    sports.extend(codes)

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
        except Exception as e:
            log_error("Strava API error in get_profile", exc=e)
            return None

    def get_activities(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        sport_type: Optional[str] = None,
    ) -> List[Activity]:
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
                resp = self._request("/activities", params=params)
                if not resp:
                    break
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data:
                    break

                for act in data:
                    act_type = act.get("type", "").lower()
                    if sport_type and act_type != sport_type.lower():
                        continue

                    start_time = datetime.fromisoformat(act["start_date"].replace("Z", "+00:00"))

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
            except Exception as e:
                log_error("Strava API error in get_activities", exc=e)
                break

        return activities

    def get_daily_summary(self, date: datetime) -> Optional[DailySummary]:
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
