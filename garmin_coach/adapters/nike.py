import os
from datetime import datetime, timedelta
from typing import List, Optional

from garmin_coach.adapters import (
    Activity,
    DataSource,
    DailySummary,
    UserProfile,
)


NIKE_CONFIG_DIR = os.path.expanduser("~/.config/garmin_coach")


def get_nike_token() -> Optional[dict]:
    token_file = os.path.join(NIKE_CONFIG_DIR, "nike_token.json")
    if not os.path.exists(token_file):
        return None
    try:
        import json

        with open(token_file) as f:
            return json.load(f)
    except Exception:
        return None


class NikeAdapter(DataSource):
    """Adapter for Nike Run Club.

    Note: Nike retired their public API in 2020. This adapter provides
    a stub implementation that can be extended if alternative data
    sources become available (e.g., Nike Run Club app exports).
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._profile_cache = None

    def is_authenticated(self) -> bool:
        token = get_nike_token()
        return token is not None

    def authenticate(self, credentials: dict) -> bool:
        import json

        os.makedirs(NIKE_CONFIG_DIR, exist_ok=True)
        token_file = os.path.join(NIKE_CONFIG_DIR, "nike_token.json")
        with open(token_file, "w") as f:
            json.dump(credentials, f)
        return self.is_authenticated()

    def get_profile(self) -> Optional[UserProfile]:
        if self._profile_cache:
            return self._profile_cache
        token = get_nike_token()
        if not token:
            return None
        self._profile_cache = UserProfile(
            user_id=token.get("user_id", "nike_user"),
            name=token.get("name", "Nike User"),
            age=None,
            weight_kg=None,
            max_heart_rate=None,
            resting_heart_rate=None,
            ftp=None,
            sport_preferences=["running"],
        )
        return self._profile_cache

    def get_activities(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        sport_type: Optional[str] = None,
    ) -> List[Activity]:
        return []

    def get_daily_summary(self, date: datetime) -> Optional[DailySummary]:
        return None

    def get_time_series(
        self, metric: str, start_date: datetime, end_date: Optional[datetime] = None
    ) -> List[tuple]:
        return []
