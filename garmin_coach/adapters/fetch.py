from datetime import datetime, timedelta
from typing import List, Optional

from garmin_coach.adapters import DataSource, Activity, DailySummary, UserProfile
from garmin_coach.adapters.garmin import GarminAdapter
from garmin_coach.adapters.strava import StravaAdapter
from garmin_coach.adapters.nike import NikeAdapter
from garmin_coach.logging_config import log_error


class UnifiedFetcher:
    """Unified interface for fetching data from multiple sources."""

    def __init__(self):
        self._sources = {}

    def register(self, name: str, source: DataSource):
        self._sources[name] = source

    def get_source(self, name: str) -> Optional[DataSource]:
        return self._sources.get(name)

    def primary_source(self) -> Optional[DataSource]:
        # Garmin is the only authoritative primary source.
        # Strava is a supplemental ingestion path via strava-sync; it is
        # never a runtime fallback for Garmin.
        return self._sources.get("garmin")

    def all_activities(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        sport_type: Optional[str] = None,
    ) -> List[Activity]:
        all_acts = []
        for name, source in self._sources.items():
            try:
                acts = source.get_activities(start_date, end_date, sport_type)
                for act in acts:
                    act.raw_data["source"] = name
                all_acts.extend(acts)
            except Exception as e:
                log_error(f"Data fetch error in all_activities for source {name}", exc=e)
        all_acts.sort(key=lambda a: a.start_time, reverse=True)
        return all_acts

    def merged_daily_summary(self, date: datetime) -> Optional[DailySummary]:
        # Only Garmin contributes to the authoritative training-load summary.
        # Strava activities enter via strava-sync → training_load_manager, not
        # via this path.  StravaAdapter.get_daily_summary() already returns None,
        # but excluding it here makes the boundary explicit and prevents any
        # future Strava adapter changes from accidentally leaking into load math.
        summaries = []
        load_sources = {k: v for k, v in self._sources.items() if k != "strava"}
        for name, source in load_sources.items():
            try:
                summary = source.get_daily_summary(date)
                if summary:
                    summaries.append(summary)
            except Exception as e:
                log_error(f"Data fetch error in merged_daily_summary for source {name}", exc=e)

        if not summaries:
            return None

        all_activities = []
        total_duration = 0
        total_distance = 0.0
        total_calories = 0

        for s in summaries:
            all_activities.extend(s.activities)
            total_duration += s.total_duration_minutes
            total_distance += s.total_distance_km
            total_calories += s.total_calories

        ctl = max((s.ctl for s in summaries), default=0)
        atl = max((s.atl for s in summaries), default=0)
        tsb = ctl - atl

        return DailySummary(
            date=date,
            ctl=ctl,
            atl=atl,
            tsb=tsb,
            trimp=sum(s.trimp for s in summaries),
            activities=all_activities,
            total_duration_minutes=total_duration,
            total_distance_km=round(total_distance, 2),
            total_calories=total_calories,
        )

    def combined_profile(self) -> Optional[UserProfile]:
        for name in ["garmin", "strava", "nike"]:
            source = self._sources.get(name)
            if source:
                try:
                    profile = source.get_profile()
                    if profile:
                        return profile
                except Exception as e:
                    log_error(f"Data fetch error in combined_profile for source {name}", exc=e)
        return None

    def health_status(self) -> dict:
        status = {}
        for name, source in self._sources.items():
            try:
                status[name] = source.is_authenticated()
            except Exception as e:
                log_error(f"Data fetch error in health_status for source {name}", exc=e)
                status[name] = False
        return status


_default_fetcher: Optional[UnifiedFetcher] = None


def get_fetcher() -> UnifiedFetcher:
    global _default_fetcher
    if _default_fetcher is None:
        _default_fetcher = UnifiedFetcher()
        garmin = GarminAdapter()
        if garmin.is_authenticated():
            _default_fetcher.register("garmin", garmin)
        strava = StravaAdapter()
        if strava.is_authenticated():
            _default_fetcher.register("strava", strava)
        nike = NikeAdapter()
        if nike.is_authenticated():
            _default_fetcher.register("nike", nike)
    return _default_fetcher


def fetch_activities(days: int = 7, sport: str = None) -> List[Activity]:
    start = datetime.now() - timedelta(days=days)
    fetcher = get_fetcher()
    return fetcher.all_activities(start, datetime.now(), sport)


def fetch_today_summary() -> Optional[DailySummary]:
    fetcher = get_fetcher()
    return fetcher.merged_daily_summary(datetime.now())


def fetch_profile() -> Optional[UserProfile]:
    fetcher = get_fetcher()
    return fetcher.combined_profile()
