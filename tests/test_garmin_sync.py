from datetime import datetime, timezone
from types import SimpleNamespace


def test_sync_garmin_training_load_adds_days(monkeypatch, tmp_path):
    import garmin_coach.integrations.garmin.sync as sync

    monkeypatch.setattr(sync, "INTEGRATIONS_DIR", str(tmp_path))
    monkeypatch.setattr(sync, "GARMIN_SYNC_STATE_FILE", str(tmp_path / "garmin_sync_state.json"))

    class FakeManager:
        def __init__(self):
            self.saved = []
            self.sessions = {}
            calc = SimpleNamespace(get_session=lambda d: self.sessions.get(d.isoformat()))
            calc.session_calculator = SimpleNamespace(
                calculate_trimp=lambda **kwargs: round(kwargs["duration_min"] * 0.7, 1)
            )
            self.calculator = calc

        def add_activity(self, session_date, trimp, sport, duration_min, description=""):
            self.saved.append((session_date.isoformat(), trimp, sport, duration_min, description))
            self.sessions[session_date.isoformat()] = SimpleNamespace(description=description)

        def save(self):
            return None

    fake_manager = FakeManager()
    monkeypatch.setattr(sync, "get_training_load_manager", lambda: fake_manager)

    class FakeAdapter:
        def is_authenticated(self):
            return True

        def get_activities(self, start_date, end_date=None, sport_type=None):
            return [
                SimpleNamespace(
                    activity_id="g1",
                    sport_type="running",
                    start_time=datetime(2026, 3, 29, 7, 0, tzinfo=timezone.utc),
                    duration_seconds=3600,
                    distance_meters=10000,
                    calories=600,
                    heart_rate_avg=150,
                )
            ]

    monkeypatch.setattr(sync, "GarminAdapter", FakeAdapter)
    result = sync.sync_garmin_training_load(days=7, dry_run=False)

    assert result["added"] == 1
    assert fake_manager.saved[0][0] == "2026-03-29"
    assert fake_manager.saved[0][2] == "running"


def test_sync_garmin_training_load_overwrites_non_garmin(monkeypatch, tmp_path):
    import garmin_coach.integrations.garmin.sync as sync

    monkeypatch.setattr(sync, "INTEGRATIONS_DIR", str(tmp_path))
    monkeypatch.setattr(sync, "GARMIN_SYNC_STATE_FILE", str(tmp_path / "garmin_sync_state.json"))

    existing = {"2026-03-29": SimpleNamespace(description="[manual-log] workout")}

    class FakeManager:
        def __init__(self):
            self.saved = []
            self.calculator = SimpleNamespace(
                get_session=lambda d: existing.get(d.isoformat()),
                session_calculator=SimpleNamespace(calculate_trimp=lambda **kwargs: 42.0),
            )

        def add_activity(self, session_date, trimp, sport, duration_min, description=""):
            self.saved.append((session_date.isoformat(), description))

        def save(self):
            return None

    manager = FakeManager()
    monkeypatch.setattr(sync, "get_training_load_manager", lambda: manager)

    class FakeAdapter:
        def is_authenticated(self):
            return True

        def get_activities(self, start_date, end_date=None, sport_type=None):
            return [
                SimpleNamespace(
                    activity_id="g1",
                    sport_type="running",
                    start_time=datetime(2026, 3, 29, 7, 0, tzinfo=timezone.utc),
                    duration_seconds=3600,
                    distance_meters=10000,
                    calories=600,
                    heart_rate_avg=150,
                )
            ]

    monkeypatch.setattr(sync, "GarminAdapter", FakeAdapter)
    result = sync.sync_garmin_training_load(days=7, dry_run=False)
    assert result["updated"] == 1
    assert manager.saved[0][0] == "2026-03-29"
    assert manager.saved[0][1].startswith("[garmin-sync]")


def test_sync_garmin_training_load_stale_cleanup_respects_window(monkeypatch, tmp_path):
    import json
    import garmin_coach.integrations.garmin.sync as sync

    monkeypatch.setattr(sync, "INTEGRATIONS_DIR", str(tmp_path))
    state_file = tmp_path / "garmin_sync_state.json"
    monkeypatch.setattr(sync, "GARMIN_SYNC_STATE_FILE", str(state_file))
    state_file.write_text(json.dumps({"days": {"2026-03-29": {"fingerprint": "old"}}}))

    removed = []

    class FakeCalculator:
        def __init__(self):
            self.session_calculator = SimpleNamespace(calculate_trimp=lambda **kwargs: 20.0)

        def get_session(self, d):
            if d.isoformat() == "2026-03-29":
                return SimpleNamespace(description="[garmin-sync] old batch")
            return None

        def remove_session(self, d):
            removed.append(d.isoformat())
            return True

    class FakeManager:
        def __init__(self):
            self.calculator = FakeCalculator()

        def add_activity(self, *args, **kwargs):
            return None

        def save(self):
            return None

    monkeypatch.setattr(sync, "get_training_load_manager", lambda: FakeManager())

    class FakeAdapter:
        def is_authenticated(self):
            return True

        def get_activities(self, start_date, end_date=None, sport_type=None):
            return []

    monkeypatch.setattr(sync, "GarminAdapter", FakeAdapter)
    result = sync.sync_garmin_training_load(days=7, dry_run=False)
    assert result["removed"] == 1
    assert removed == ["2026-03-29"]
