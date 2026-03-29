"""Data adapters for multiple fitness platforms.

Abstract interface for fetching training data from various sources:
- Garmin Connect (primary)
- Strava
- Nike Run Club
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


__all__ = [
    "DataSource",
    "Activity",
    "DailySummary",
    "UserProfile",
]


def __getattr__(name):
    if name == "GarminAdapter":
        from garmin_coach.adapters.garmin import GarminAdapter

        return GarminAdapter
    if name == "StravaAdapter":
        from garmin_coach.adapters.strava import StravaAdapter

        return StravaAdapter
    if name == "NikeAdapter":
        from garmin_coach.adapters.nike import NikeAdapter

        return NikeAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@dataclass
class Activity:
    """Standardized activity data."""

    activity_id: str
    name: str
    sport_type: str  # running, cycling, swimming, etc.
    start_time: datetime
    duration_seconds: int
    distance_meters: Optional[float]
    calories: Optional[int]
    heart_rate_avg: Optional[int]
    heart_rate_max: Optional[int]
    power_avg: Optional[int]
    pace_sec_per_km: Optional[float]
    elevation_gain: Optional[float]
    raw_data: dict  # Original data from source


@dataclass
class DailySummary:
    """Daily training load summary."""

    date: datetime
    ctl: float  # Chronic Training Load (42-day)
    atl: float  # Acute Training Load (7-day)
    tsb: float  # Training Stress Balance (form)
    trimp: float
    activities: List[Activity]
    total_duration_minutes: int
    total_distance_km: float
    total_calories: int


@dataclass
class UserProfile:
    """User profile data from source."""

    user_id: str
    name: str
    age: Optional[int]
    weight_kg: Optional[float]
    max_heart_rate: Optional[int]
    resting_heart_rate: Optional[int]
    ftp: Optional[int]  # Functional Threshold Power
    sport_preferences: List[str]


class DataSource(ABC):
    """Abstract interface for fitness data providers."""

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if user is authenticated with this source."""
        pass

    @abstractmethod
    def authenticate(self, credentials: dict) -> bool:
        """Authenticate with the data source."""
        pass

    @abstractmethod
    def get_profile(self) -> Optional[UserProfile]:
        """Fetch user profile from the source."""
        pass

    @abstractmethod
    def get_activities(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        sport_type: Optional[str] = None,
    ) -> List[Activity]:
        """Fetch activities within a date range."""
        pass

    @abstractmethod
    def get_daily_summary(self, date: datetime) -> Optional[DailySummary]:
        """Get training load summary for a specific day."""
        pass

    @abstractmethod
    def get_time_series(
        self, metric: str, start_date: datetime, end_date: Optional[datetime] = None
    ) -> List[tuple]:
        """Get time series data for a metric (e.g., CTL, ATL, TSB)."""
        pass


class DataSourceFactory:
    """Factory for creating data source adapters."""

    _sources = {}

    @classmethod
    def register(cls, name: str, source_class: type):
        """Register a data source adapter."""
        cls._sources[name] = source_class

    @classmethod
    def create(cls, name: str, config: dict = None) -> DataSource:
        """Create a data source adapter by name."""
        if name not in cls._sources:
            raise ValueError(f"Unknown data source: {name}")
        return cls._sources[name](config or {})

    @classmethod
    def available_sources(cls) -> List[str]:
        """List registered data source names."""
        return list(cls._sources.keys())
