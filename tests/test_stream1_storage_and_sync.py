from datetime import date, datetime
from types import SimpleNamespace


def test_storage_round_trip_and_user_scoping(tmp_path):
    from garmin_coach.storage.database import GarminCoachDatabase

    db = GarminCoachDatabase(tmp_path / "coach.db")
    db.save_daily_health("user-a", "2026-04-06", {"sleep": 80})
    db.save_daily_health("user-b", "2026-04-06", {"sleep": 40})
    assert db.load_daily_health("user-a", "2026-04-06") == {"sleep": 80}
    assert db.load_daily_health("user-b", "2026-04-06") == {"sleep": 40}
    db.close()


def test_storage_rejects_sensitive_payloads(tmp_path):
    import pytest

    from garmin_coach.storage.database import GarminCoachDatabase

    db = GarminCoachDatabase(tmp_path / "coach.db")
    with pytest.raises(ValueError):
        db.save_daily_health("user-a", "2026-04-06", {"password": "secret"})
    db.close()


def test_storage_rejects_sensitive_payloads_nested_in_lists(tmp_path):
    import pytest

    from garmin_coach.storage.database import GarminCoachDatabase

    db = GarminCoachDatabase(tmp_path / "coach.db")
    with pytest.raises(ValueError):
        db.save_daily_health(
            "user-a",
            "2026-04-06",
            {"items": [{"safe": 1}, {"access_token": "secret"}]},
        )
    db.close()


def test_sync_service_isolates_subscriber_failures(monkeypatch, tmp_path):
    from garmin_coach.integrations.sync import GarminSyncService, SyncEventBus
    from garmin_coach.models import DailyHealthUpdatedEvent, NewActivityEvent, SyncEventType
    from garmin_coach.storage.database import GarminCoachDatabase

    class FakeAdapter:
        def get_activities(self, start, end):
            return [
                SimpleNamespace(
                    activity_id="a1",
                    sport_type="running",
                    start_time=datetime(2026, 4, 6, 7, 0),
                    distance_meters=1000,
                    duration_seconds=300,
                    heart_rate_avg=150,
                    heart_rate_max=170,
                    power_avg=None,
                    calories=100,
                    raw_data={},
                )
            ]

        def get_activity_summary(self, activity_id):
            return None

        def get_sleep_data(self, date_str):
            from garmin_coach.models import SleepData

            return SleepData(score=80)

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
            return None

    fake_calc = SimpleNamespace(
        get_snapshot=lambda today: SimpleNamespace(
            ctl=10, atl=8, tsb=2, date=date.fromisoformat(today)
        ),
        export_time_series=lambda days=8: [{"ctl": 5}] * 8,
        get_weekly_stats=lambda today: SimpleNamespace(
            week_start=date(2026, 3, 31), total_trimp=100
        ),
        get_sessions_in_range=lambda start, end: [
            SimpleNamespace(trimp=10),
            SimpleNamespace(trimp=20),
        ],
    )
    monkeypatch.setattr(
        "garmin_coach.integrations.sync.get_training_load_manager",
        lambda: SimpleNamespace(calculator=fake_calc),
    )

    bus = SyncEventBus()
    seen = {"activity": 0, "health": 0}

    def boom(payload):
        raise RuntimeError("subscriber failed")

    bus.on_new_activity(boom)
    bus.on_new_activity(lambda payload: seen.__setitem__("activity", seen["activity"] + 1))
    bus.on_daily_health_updated(boom)
    bus.on_daily_health_updated(lambda payload: seen.__setitem__("health", seen["health"] + 1))

    service = GarminSyncService(
        FakeAdapter(), GarminCoachDatabase(tmp_path / "coach.db"), bus=bus, user_id="user-a"
    )
    activities = service.sync_recent_activities(datetime(2026, 4, 6, 6, 45))
    metrics = service.sync_daily_health(date(2026, 4, 6))

    assert seen == {"activity": 1, "health": 1}
    assert activities[0].activity_id == "a1"
    assert metrics.metric_date == date(2026, 4, 6)
    assert any(
        report.event_type == SyncEventType.DAILY_HEALTH_UPDATED
        for report in service.last_dispatch_reports
    )
    db = service.database
    assert db.load_activity("user-a", "a1")["activity_id"] == "a1"
    assert db.load_daily_health("user-a", "2026-04-06")["metric_date"] == "2026-04-06"


def test_sync_event_payloads_are_typed():
    from garmin_coach.models import (
        ActivitySummary,
        DailyHealthUpdatedEvent,
        HealthMetrics,
        NewActivityEvent,
        TrainingLoad,
    )

    activity_event = NewActivityEvent(user_id="user-a", activity=ActivitySummary(activity_id="a1"))
    health_event = DailyHealthUpdatedEvent(
        user_id="user-a",
        metrics=HealthMetrics(metric_date=date(2026, 4, 6), training_load=TrainingLoad()),
    )
    assert activity_event.to_dict()["activity"]["activity_id"] == "a1"
    assert health_event.to_dict()["metrics"]["metric_date"] == "2026-04-06"
