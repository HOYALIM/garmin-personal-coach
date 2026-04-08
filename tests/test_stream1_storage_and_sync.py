from datetime import date, datetime
from types import SimpleNamespace
from typing import Any, cast


def test_storage_scoping_and_recent_queries(tmp_path):
    from garmin_coach.storage.database import GarminCoachDatabase

    db = GarminCoachDatabase(tmp_path / "coach.db")
    db.save_activity(
        "u1",
        "a1",
        "2026-04-06T07:00:00",
        {"activity_id": "a1", "start_time": "2026-04-06T07:00:00"},
    )
    db.save_daily_health("u1", "2026-04-06", {"sleep": {"sleepScore": 80}})
    assert db.list_recent_activities("u1", limit=1)[0]["activity_id"] == "a1"
    assert db.list_recent_daily_health("u1", limit=1)[0]["sleep"]["sleepScore"] == 80
    db.close()


def test_storage_rejects_nested_sensitive_payloads(tmp_path):
    import pytest

    from garmin_coach.storage.database import GarminCoachDatabase

    db = GarminCoachDatabase(tmp_path / "coach.db")
    with pytest.raises(ValueError):
        db.save_daily_health("u1", "2026-04-06", {"items": [{"access_token": "secret"}]})
    db.close()


def test_sync_daily_health_populates_recent_context(monkeypatch, tmp_path):
    from garmin_coach.integrations.sync import GarminSyncService
    from garmin_coach.storage.database import GarminCoachDatabase

    class FakeAdapter:
        def get_activities(self, start, end):
            return []

        def get_activity_summary(self, activity_id):
            return None

        def get_sleep_data(self, date_str):
            from garmin_coach.models import SleepData

            return SleepData(score=80, raw={"sleepScore": 80})

        def get_hrv_data(self, date_str):
            from garmin_coach.models import HRVData

            return HRVData(deviation_pct=0)

        def get_body_battery(self, start, end):
            from garmin_coach.models import BodyBatteryData

            return BodyBatteryData(morning_value=70)

        def get_stress_data(self, date_str):
            return None

        def get_rhr_day(self, date_str):
            from garmin_coach.models import RHRData

            return RHRData(value_bpm=50, baseline_bpm=50, deviation_bpm=0)

        def get_spo2_data(self, date_str):
            return None

        def get_body_composition(self, date_str):
            return None

        def get_training_readiness(self, date_str):
            from garmin_coach.models import TrainingReadinessData

            return TrainingReadinessData(score=82, level="green")

    fake_calc = SimpleNamespace(
        get_snapshot=lambda today: SimpleNamespace(
            ctl=10, atl=8, tsb=2, date=date.fromisoformat(today)
        ),
        get_weekly_stats=lambda today: SimpleNamespace(
            week_start=date(2026, 3, 31), total_trimp=100
        ),
        get_sessions_in_range=lambda start, end: [
            SimpleNamespace(trimp=10, duration_min=30, distance_km=5.0, sport="running")
        ],
        export_time_series=lambda days=8: [{"ctl": 5}] * 8,
        calculate_ctl=lambda today: 10,
    )
    monkeypatch.setattr(
        "garmin_coach.integrations.sync.get_training_load_manager",
        lambda: SimpleNamespace(calculator=fake_calc),
    )

    db = GarminCoachDatabase(tmp_path / "coach.db")
    db.save_activity(
        "u1",
        "a1",
        "2026-04-05T07:00:00",
        {"activity_id": "a1", "max_hr": 180, "start_time": "2026-04-05T07:00:00"},
    )
    db.save_daily_health("u1", "2026-04-05", {"sleep": {"sleepScore": 77}})
    service = GarminSyncService(cast(Any, FakeAdapter()), db, user_id="u1")
    metrics = service.sync_daily_health(date(2026, 4, 6))
    assert metrics.recent_activities[0].activity_id == "a1"
    assert 77 in metrics.recent_sleep_scores
    assert metrics.readiness is not None
    assert metrics.readiness.confidence == "medium"
    assert metrics.training_load.weekly_volume_km == 5.0


def test_weekly_volume_prefers_real_distance_over_duration():
    from garmin_coach.integrations.training_load import calculate_weekly_volume_km

    fake_calc = SimpleNamespace(
        get_sessions_in_range=lambda start, end: [
            SimpleNamespace(distance_km=8.2, duration_min=60, sport="cycling"),
            SimpleNamespace(distance_meters=3200, duration_min=25, sport="running"),
        ]
    )
    assert calculate_weekly_volume_km(cast(Any, fake_calc), "2026-04-01", "2026-04-07") == 11.4
