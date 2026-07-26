"""PRD v3.0 Data Plane: parallel snapshot fetcher + cache-first service.

The FakeAdapter below feeds REAL captured Garmin payloads from
tests/fixtures/garmin/ through the real parsers. An earlier version invented
payload shapes here ({"sleepScore": 85}), which agreed with equally invented
parsers and hid the fact that nothing parsed in production.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from garmin_coach.adapters.garmin.health import (
    parse_body_battery,
    parse_body_composition,
    parse_hrv_data,
    parse_rhr_data,
    parse_sleep_data,
    parse_spo2_data,
    parse_stress_data,
    parse_training_readiness,
)
from garmin_coach.adapters.garmin.snapshot import (
    TODAY_TTL,
    DailySnapshot,
    SnapshotFetcher,
    SnapshotService,
)
from garmin_coach.storage.database import DEFAULT_USER_ID, GarminCoachDatabase

TODAY = date(2026, 7, 12)
NOW = datetime(2026, 7, 12, 7, 0, 0)

FIXTURES = Path(__file__).parent / "fixtures" / "garmin"


def fixture(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text())


# Values below come straight out of the captured fixtures — see
# tests/test_garmin_health_parsers.py for the field-by-field assertions.
REAL_SLEEP_SCORE = 73
REAL_STRESS_AVG = 15
REAL_BB_MORNING = 23
REAL_BB_CHARGED = 59


class FakeAdapter:
    """Feeds real captured payloads through the real parsers; counts calls.

    ``unsynced=True`` swaps in the fixtures from a day the watch never
    uploaded (envelope present, every leaf null) so tests can exercise the
    "no data yet" path that a synthetic payload would never reproduce.
    """

    def __init__(
        self,
        fail: set[str] | None = None,
        fail_once: set[str] | None = None,
        unsynced: bool = False,
    ):
        self.fail = fail or set()
        self.fail_once = dict.fromkeys(fail_once or set(), True)
        self.calls: list[str] = []
        self.unsynced = unsynced

    def _guard(self, name: str):
        self.calls.append(name)
        if name in self.fail:
            raise RuntimeError(f"{name} down")
        if self.fail_once.get(name):
            self.fail_once[name] = False
            raise RuntimeError(f"{name} flaky")

    def _fx(self, name: str):
        return fixture(name if self.unsynced else f"{name}_populated")

    def get_sleep_data(self, date_str):
        self._guard("sleep")
        return parse_sleep_data(self._fx("sleep"))

    def get_hrv_data(self, date_str):
        self._guard("hrv")
        # Capture account has HRV disabled ({}), so keep a synthetic populated
        # case here; parser-level coverage lives in test_garmin_health_parsers.
        if self.unsynced:
            return parse_hrv_data(fixture("hrv"))
        return parse_hrv_data({"lastNightAvg": 55, "baselineValue": 50})

    def get_body_battery(self, start_str, end_str):
        self._guard("body_battery")
        return parse_body_battery(self._fx("body_battery"))

    def get_stress_data(self, date_str):
        self._guard("stress")
        return parse_stress_data(self._fx("stress"))

    def get_rhr_day(self, date_str):
        self._guard("rhr")
        return parse_rhr_data(self._fx("rhr"))

    def get_spo2_data(self, date_str):
        self._guard("spo2")
        return parse_spo2_data(fixture("spo2"))

    def get_body_composition(self, date_str):
        self._guard("body_composition")
        return parse_body_composition(fixture("body_composition"))

    def get_training_readiness(self, date_str):
        self._guard("training_readiness")
        if self.unsynced:
            return parse_training_readiness(fixture("training_readiness"))
        return parse_training_readiness([{"score": 82}])


@pytest.fixture
def db():
    database = GarminCoachDatabase(":memory:")
    yield database
    database.close()


def make_service(adapter, db, now=NOW):
    fetcher = SnapshotFetcher(adapter, now=lambda: now)
    return SnapshotService(fetcher, db, now=lambda: now)


# -- fetcher ----------------------------------------------------------------


def test_fetch_aggregates_all_metrics_in_one_batch():
    adapter = FakeAdapter()
    snapshot = SnapshotFetcher(adapter).fetch(TODAY)
    assert snapshot.sleep.score == REAL_SLEEP_SCORE
    assert snapshot.hrv.value_ms == 55
    assert snapshot.body_battery.morning_value == REAL_BB_MORNING
    assert snapshot.stress.avg == REAL_STRESS_AVG
    assert snapshot.rhr.value_bpm == 54.0
    assert snapshot.training_readiness.score == 82
    assert snapshot.errors == {}
    assert not snapshot.from_cache


def test_fetch_tolerates_partial_failure():
    adapter = FakeAdapter(fail={"hrv", "sleep"})
    snapshot = SnapshotFetcher(adapter).fetch(TODAY)
    assert snapshot.sleep is None
    assert snapshot.hrv is None
    assert "hrv" in snapshot.errors and "sleep" in snapshot.errors
    assert snapshot.training_readiness.score == 82  # rest survives
    assert not snapshot.is_empty


def test_fetch_retries_each_metric_once():
    adapter = FakeAdapter(fail_once={"rhr"})
    snapshot = SnapshotFetcher(adapter).fetch(TODAY)
    assert snapshot.rhr.value_bpm == 54.0
    assert adapter.calls.count("rhr") == 2
    assert "rhr" not in snapshot.errors


# -- cache-first service ----------------------------------------------------


def test_today_second_read_is_cache_hit(db):
    adapter = FakeAdapter()
    service = make_service(adapter, db)
    first = service.get(TODAY)
    calls_after_first = len(adapter.calls)
    second = service.get(TODAY)
    assert len(adapter.calls) == calls_after_first  # no new API calls
    assert second.from_cache
    assert not first.from_cache
    assert second.sleep.score == first.sleep.score


def test_today_refetches_after_ttl(db):
    adapter = FakeAdapter()
    service = make_service(adapter, db, now=NOW)
    service.get(TODAY)
    calls_after_first = len(adapter.calls)

    later = NOW + TODAY_TTL + timedelta(minutes=1)
    stale_service = make_service(adapter, db, now=later)
    refreshed = stale_service.get(TODAY)
    assert len(adapter.calls) > calls_after_first
    assert not refreshed.from_cache


def test_past_date_is_cached_forever(db):
    adapter = FakeAdapter()
    yesterday = TODAY - timedelta(days=1)
    service = make_service(adapter, db)
    service.get(yesterday)
    calls_after_first = len(adapter.calls)

    much_later = NOW + timedelta(days=30)
    later_service = make_service(adapter, db, now=much_later)
    cached = later_service.get(yesterday)
    assert len(adapter.calls) == calls_after_first
    assert cached.from_cache


def test_refresh_failure_degrades_to_stale_cache(db):
    good = FakeAdapter()
    service = make_service(good, db)
    service.get(TODAY)

    all_metrics = set(
        ["sleep", "hrv", "body_battery", "stress", "rhr", "spo2", "body_composition",
         "training_readiness"]
    )
    broken = FakeAdapter(fail=all_metrics)
    later = NOW + TODAY_TTL + timedelta(hours=1)
    degraded_service = make_service(broken, db, now=later)
    snapshot = degraded_service.get(TODAY)
    assert snapshot.from_cache  # stale beats empty
    assert snapshot.sleep.score == REAL_SLEEP_SCORE


def test_force_refresh_bypasses_cache(db):
    adapter = FakeAdapter()
    service = make_service(adapter, db)
    service.get(TODAY)
    calls_after_first = len(adapter.calls)
    fresh = service.get(TODAY, force_refresh=True)
    assert len(adapter.calls) > calls_after_first
    assert not fresh.from_cache


# -- serialization round-trip ------------------------------------------------


def test_payload_round_trip_preserves_parsed_values():
    original = SnapshotFetcher(FakeAdapter()).fetch(TODAY)
    restored = DailySnapshot.from_payload(TODAY, original.to_payload())
    assert restored is not None
    assert restored.from_cache
    assert restored.sleep.score == original.sleep.score
    assert restored.hrv.deviation_pct == original.hrv.deviation_pct
    assert restored.body_battery.morning_value == original.body_battery.morning_value
    assert restored.rhr.deviation_bpm == original.rhr.deviation_bpm
    assert restored.training_readiness.level == original.training_readiness.level


def test_from_payload_rejects_legacy_daily_health_shape():
    legacy = {"metric_date": TODAY.isoformat(), "sleep": {"sleepScore": 70}}
    assert DailySnapshot.from_payload(TODAY, legacy) is None


# -- freshness contract -------------------------------------------------------


def test_freshness_labels():
    snapshot = SnapshotFetcher(FakeAdapter()).fetch(TODAY)
    fetched = snapshot.fetched_at
    assert snapshot.freshness_label(fetched + timedelta(minutes=5)) is None
    assert "분 전" in snapshot.freshness_label(fetched + timedelta(minutes=45))
    assert "2시간 전" in snapshot.freshness_label(fetched + timedelta(hours=2))
    assert "워치 동기화" in snapshot.freshness_label(fetched + timedelta(days=2))


def test_empty_snapshot_always_warns():
    empty = DailySnapshot(metric_date=TODAY, fetched_at=NOW)
    assert "동기화" in empty.freshness_label(NOW)


def test_no_data_yet_is_distinguished_from_fetch_failure():
    """'watch has not uploaded' and 'we could not reach Garmin' are different
    problems with different user actions; both used to render identically."""
    no_data = DailySnapshot(metric_date=TODAY, fetched_at=NOW)
    assert no_data.awaiting_watch_sync is True
    assert "아직 없어요" in no_data.freshness_label(NOW)

    failed = DailySnapshot(metric_date=TODAY, fetched_at=NOW, errors={"sleep": "boom"})
    assert failed.awaiting_watch_sync is False
    assert "가져오지 못했어요" in failed.freshness_label(NOW)


def test_unsynced_day_fixtures_yield_no_present_metrics():
    """Real payloads from a day the watch never uploaded must not be counted
    as collected — that false 'success' is what hid the parser breakage."""
    snapshot = SnapshotFetcher(FakeAdapter(unsynced=True)).fetch(TODAY)
    assert snapshot.present_metrics == []
    assert snapshot.is_empty
    assert snapshot.errors == {}  # nothing failed; there is simply no data
    assert snapshot.awaiting_watch_sync


# -- snapshots table ----------------------------------------------------------


def test_snapshot_storage_isolated_from_daily_health(db):
    db.save_daily_health(DEFAULT_USER_ID, TODAY.isoformat(), {"sleep": {"sleepScore": 1}})
    service = make_service(FakeAdapter(), db)
    snapshot = service.get(TODAY)
    assert snapshot.sleep.score == REAL_SLEEP_SCORE  # not polluted by legacy payload
    legacy = db.load_daily_health(DEFAULT_USER_ID, TODAY.isoformat())
    assert legacy == {"sleep": {"sleepScore": 1}}  # legacy table untouched
