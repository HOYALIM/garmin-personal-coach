"""Daily health snapshot — the Data Plane of PRD v3.0.

One day of health data is fetched as a single parallel batch (SnapshotFetcher)
and served cache-first (SnapshotService):

- past dates are immutable → cached forever, never re-fetched
- today changes (body battery, stress) → 30-minute TTL
- partial failure is tolerated: whatever metrics arrive form a valid snapshot
- every consumer gets a freshness label so stale data is never silently fresh

Engine/Flows must read through SnapshotService; direct GarminAdapter health
calls belong only inside this module and GarminSyncService.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable

from garmin_coach.logging_config import log_warning
from garmin_coach.models import (
    BodyBatteryData,
    BodyCompositionData,
    HRVData,
    RHRData,
    SleepData,
    SpO2Data,
    StressData,
    TrainingReadinessData,
)
from garmin_coach.storage.database import DEFAULT_USER_ID, GarminCoachDatabase

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

TODAY_TTL = timedelta(minutes=30)
STALE_AFTER = timedelta(hours=24)

# metric name → (adapter method, parse function used to rebuild from cached raw)
_METRIC_SPECS: dict[str, tuple[str, Callable[[Any], Any]]] = {
    "training_readiness": ("get_training_readiness", parse_training_readiness),
    "sleep": ("get_sleep_data", parse_sleep_data),
    "hrv": ("get_hrv_data", parse_hrv_data),
    "body_battery": ("get_body_battery", parse_body_battery),
    "stress": ("get_stress_data", parse_stress_data),
    "rhr": ("get_rhr_day", parse_rhr_data),
    # P1: fetched in the same batch, but never block a snapshot
    "spo2": ("get_spo2_data", parse_spo2_data),
    "body_composition": ("get_body_composition", parse_body_composition),
}

P0_METRICS = ("training_readiness", "sleep", "hrv", "body_battery", "stress", "rhr")


@dataclass
class DailySnapshot:
    metric_date: date
    fetched_at: datetime
    sleep: SleepData | None = None
    hrv: HRVData | None = None
    body_battery: BodyBatteryData | None = None
    stress: StressData | None = None
    rhr: RHRData | None = None
    spo2: SpO2Data | None = None
    body_composition: BodyCompositionData | None = None
    training_readiness: TrainingReadinessData | None = None
    errors: dict[str, str] = field(default_factory=dict)
    from_cache: bool = False

    @property
    def present_metrics(self) -> list[str]:
        return [name for name in _METRIC_SPECS if getattr(self, name) is not None]

    @property
    def is_empty(self) -> bool:
        return not self.present_metrics

    def age(self, now: datetime | None = None) -> timedelta:
        return (now or datetime.now()) - self.fetched_at

    def freshness_label(self, now: datetime | None = None) -> str | None:
        """PRD v3.0 freshness contract: None / relative age / sync warning."""
        if self.is_empty:
            return "⚠️ 워치 동기화를 확인해주세요"
        age = self.age(now)
        if age < TODAY_TTL:
            return None
        if age < STALE_AFTER:
            hours = int(age.total_seconds() // 3600)
            if hours < 1:
                return f"🕐 {int(age.total_seconds() // 60)}분 전 데이터"
            return f"🕐 {hours}시간 전 데이터"
        return "⚠️ 워치 동기화를 확인해주세요"

    def to_payload(self) -> dict[str, Any]:
        """Serialize for the snapshots table: raw payloads only, so the
        cache path re-parses with the exact same parse_* functions."""
        payload: dict[str, Any] = {
            "snapshot_version": 1,
            "fetched_at": self.fetched_at.isoformat(),
            "errors": dict(self.errors),
            "metrics": {},
        }
        for name in _METRIC_SPECS:
            value = getattr(self, name)
            payload["metrics"][name] = value.raw if value is not None else None
        return payload

    @classmethod
    def from_payload(cls, metric_date: date, payload: dict[str, Any]) -> "DailySnapshot | None":
        if not isinstance(payload, dict) or "fetched_at" not in payload:
            return None
        try:
            fetched_at = datetime.fromisoformat(str(payload["fetched_at"]))
        except ValueError:
            return None
        snapshot = cls(
            metric_date=metric_date,
            fetched_at=fetched_at,
            errors=dict(payload.get("errors") or {}),
            from_cache=True,
        )
        metrics = payload.get("metrics") or {}
        for name, (_, parse) in _METRIC_SPECS.items():
            raw = metrics.get(name)
            if raw is None:
                continue
            # body_battery raw is wrapped as {"payload": ...} by its parser
            if name == "body_battery" and isinstance(raw, dict) and "payload" in raw:
                raw = raw["payload"]
            try:
                setattr(snapshot, name, parse(raw))
            except Exception as exc:
                snapshot.errors[name] = f"cache parse: {exc}"
        return snapshot


class SnapshotFetcher:
    """Fetch one day of health metrics as a parallel batch.

    One retry per metric, no batch-level retry: a metric that fails twice is
    recorded in errors and simply missing until the next refresh cycle.
    """

    def __init__(
        self,
        adapter: Any,
        max_workers: int = 6,
        now: Callable[[], datetime] = datetime.now,
    ):
        self.adapter = adapter
        self.max_workers = max_workers
        self._now = now

    def fetch(self, target_date: date) -> DailySnapshot:
        date_str = target_date.isoformat()
        snapshot = DailySnapshot(metric_date=target_date, fetched_at=self._now())
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                name: pool.submit(self._fetch_metric, method_name, date_str)
                for name, (method_name, _) in _METRIC_SPECS.items()
            }
            for name, future in futures.items():
                try:
                    setattr(snapshot, name, future.result())
                except Exception as exc:
                    snapshot.errors[name] = str(exc)
                    log_warning(f"Snapshot metric {name} failed for {date_str}: {exc}")
        return snapshot

    def _fetch_metric(self, method_name: str, date_str: str) -> Any:
        method = getattr(self.adapter, method_name)
        args = (date_str, date_str) if method_name == "get_body_battery" else (date_str,)
        try:
            return method(*args)
        except Exception:
            return method(*args)  # single retry per metric


class SnapshotService:
    """Cache-first access to daily snapshots (PRD v3.0 §2).

    - past dates: served from cache forever once a non-empty snapshot exists
    - today: cache within TODAY_TTL, refreshed past it
    - refresh failure: falls back to the stale cached snapshot rather than
      returning nothing, so coaching can degrade instead of breaking
    """

    def __init__(
        self,
        fetcher: SnapshotFetcher,
        database: GarminCoachDatabase,
        user_id: str = DEFAULT_USER_ID,
        now: Callable[[], datetime] = datetime.now,
    ):
        self.fetcher = fetcher
        self.database = database
        self.user_id = user_id
        self._now = now

    def get(self, target_date: date | None = None, force_refresh: bool = False) -> DailySnapshot:
        target_date = target_date or self._now().date()
        cached = self._load_cached(target_date)
        if not force_refresh and cached is not None and self._is_usable(cached, target_date):
            return cached

        fresh = self.fetcher.fetch(target_date)
        if fresh.is_empty and cached is not None and not cached.is_empty:
            # Refresh failed outright — degrade to stale rather than empty.
            return cached
        if not fresh.is_empty or cached is None:
            self._store(fresh)
        return fresh

    def _is_usable(self, cached: DailySnapshot, target_date: date) -> bool:
        if cached.is_empty:
            return False
        if target_date < self._now().date():
            return True  # past days are immutable
        return cached.age(self._now()) < TODAY_TTL

    def _load_cached(self, target_date: date) -> DailySnapshot | None:
        payload = self.database.load_snapshot(self.user_id, target_date.isoformat())
        if payload is None:
            return None
        return DailySnapshot.from_payload(target_date, payload)

    def _store(self, snapshot: DailySnapshot) -> None:
        try:
            self.database.save_snapshot(
                self.user_id, snapshot.metric_date.isoformat(), snapshot.to_payload()
            )
        except Exception as exc:
            log_warning(f"Failed to cache snapshot for {snapshot.metric_date}: {exc}")


__all__ = [
    "P0_METRICS",
    "STALE_AFTER",
    "TODAY_TTL",
    "DailySnapshot",
    "SnapshotFetcher",
    "SnapshotService",
]
