from datetime import date, datetime, timezone
from types import SimpleNamespace


def test_sync_strava_training_load_adds_new_days(monkeypatch, tmp_path):
    import garmin_coach.integrations.strava.sync as sync

    monkeypatch.setattr(sync, "INTEGRATIONS_DIR", str(tmp_path))
    monkeypatch.setattr(sync, "STRAVA_SYNC_STATE_FILE", str(tmp_path / "strava_sync_state.json"))

    class FakeManager:
        def __init__(self):
            self.saved = []
            self.sessions = {}
            calc = SimpleNamespace(get_session=lambda d: self.sessions.get(d.isoformat()))
            calc.session_calculator = SimpleNamespace(
                calculate_trimp=lambda **kwargs: round(kwargs["duration_min"] * 0.8, 1)
            )
            self.calculator = calc

        def add_activity(self, session_date, trimp, sport, duration_min, description=""):
            self.saved.append((session_date.isoformat(), trimp, sport, duration_min, description))
            self.sessions[session_date.isoformat()] = SimpleNamespace(description=description)

    fake_manager = FakeManager()
    monkeypatch.setattr(sync, "get_training_load_manager", lambda: fake_manager)

    class FakeAdapter:
        def is_authenticated(self):
            return True

        def get_activities(self, start_date, end_date=None, sport_type=None):
            return [
                SimpleNamespace(
                    activity_id="a1",
                    sport_type="Run",
                    start_time=datetime(2026, 3, 29, 7, 0, tzinfo=timezone.utc),
                    duration_seconds=1800,
                    distance_meters=5000,
                    calories=300,
                    heart_rate_avg=150,
                ),
                SimpleNamespace(
                    activity_id="a2",
                    sport_type="Run",
                    start_time=datetime(2026, 3, 29, 18, 0, tzinfo=timezone.utc),
                    duration_seconds=1200,
                    distance_meters=3000,
                    calories=200,
                    heart_rate_avg=145,
                ),
            ]

    monkeypatch.setattr(sync, "StravaAdapter", FakeAdapter)

    result = sync.sync_strava_training_load(days=7, dry_run=False)

    assert result["added"] == 1
    assert result["updated"] == 0
    assert fake_manager.saved[0][0] == "2026-03-29"
    assert fake_manager.saved[0][2] == "running"
    assert "[strava-sync]" in fake_manager.saved[0][4]


def test_sync_strava_training_load_skips_existing_non_strava(monkeypatch, tmp_path):
    import garmin_coach.integrations.strava.sync as sync

    monkeypatch.setattr(sync, "INTEGRATIONS_DIR", str(tmp_path))
    monkeypatch.setattr(sync, "STRAVA_SYNC_STATE_FILE", str(tmp_path / "strava_sync_state.json"))

    existing = {"2026-03-29": SimpleNamespace(description="garmin imported")}
    calc = SimpleNamespace(
        get_session=lambda d: existing.get(d.isoformat()),
        session_calculator=SimpleNamespace(calculate_trimp=lambda **kwargs: 10.0),
    )
    manager = SimpleNamespace(
        calculator=calc,
        add_activity=lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not add")),
    )
    monkeypatch.setattr(sync, "get_training_load_manager", lambda: manager)

    class FakeAdapter:
        def is_authenticated(self):
            return True

        def get_activities(self, start_date, end_date=None, sport_type=None):
            return [
                SimpleNamespace(
                    activity_id="a1",
                    sport_type="Run",
                    start_time=datetime(2026, 3, 29, 7, 0, tzinfo=timezone.utc),
                    duration_seconds=1800,
                    distance_meters=5000,
                    calories=300,
                    heart_rate_avg=150,
                )
            ]

    monkeypatch.setattr(sync, "StravaAdapter", FakeAdapter)
    result = sync.sync_strava_training_load(days=7, dry_run=False)
    assert result["skipped"] == 1


def test_sync_strava_training_load_dry_run(monkeypatch, tmp_path):
    import garmin_coach.integrations.strava.sync as sync

    monkeypatch.setattr(sync, "INTEGRATIONS_DIR", str(tmp_path))
    monkeypatch.setattr(sync, "STRAVA_SYNC_STATE_FILE", str(tmp_path / "strava_sync_state.json"))
    calc = SimpleNamespace(
        get_session=lambda d: None,
        session_calculator=SimpleNamespace(calculate_trimp=lambda **kwargs: 20.0),
    )
    manager = SimpleNamespace(
        calculator=calc,
        add_activity=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run should not add")
        ),
    )
    monkeypatch.setattr(sync, "get_training_load_manager", lambda: manager)

    class FakeAdapter:
        def is_authenticated(self):
            return True

        def get_activities(self, start_date, end_date=None, sport_type=None):
            return [
                SimpleNamespace(
                    activity_id="a1",
                    sport_type="Ride",
                    start_time=datetime(2026, 3, 29, 7, 0, tzinfo=timezone.utc),
                    duration_seconds=1800,
                    distance_meters=10000,
                    calories=300,
                    heart_rate_avg=150,
                )
            ]

    monkeypatch.setattr(sync, "StravaAdapter", FakeAdapter)
    result = sync.sync_strava_training_load(days=7, dry_run=True)

    assert result["dry_run"] is True
    assert result["added"] == 1
    assert not (tmp_path / "strava_sync_state.json").exists()


def test_sync_strava_training_load_uses_start_date_local(monkeypatch, tmp_path):
    import garmin_coach.integrations.strava.sync as sync

    monkeypatch.setattr(sync, "INTEGRATIONS_DIR", str(tmp_path))
    monkeypatch.setattr(sync, "STRAVA_SYNC_STATE_FILE", str(tmp_path / "strava_sync_state.json"))
    calc = SimpleNamespace(
        get_session=lambda d: None,
        session_calculator=SimpleNamespace(calculate_trimp=lambda **kwargs: 20.0),
    )
    manager = SimpleNamespace(calculator=calc, add_activity=lambda **kwargs: None)
    monkeypatch.setattr(sync, "get_training_load_manager", lambda: manager)

    class FakeAdapter:
        def is_authenticated(self):
            return True

        def get_activities(self, start_date, end_date=None, sport_type=None):
            return [
                SimpleNamespace(
                    activity_id="late-run",
                    sport_type="Run",
                    start_time=datetime(2026, 3, 29, 23, 30, tzinfo=timezone.utc),
                    duration_seconds=1800,
                    distance_meters=5000,
                    calories=300,
                    heart_rate_avg=150,
                    raw_data={"activity": {"start_date_local": "2026-03-30T08:30:00"}},
                )
            ]

    monkeypatch.setattr(sync, "StravaAdapter", FakeAdapter)
    result = sync.sync_strava_training_load(days=7, dry_run=True)
    assert result["items"][0]["date"] == "2026-03-30"


def test_sync_strava_training_load_updates_when_fingerprint_changes(monkeypatch, tmp_path):
    import json
    import garmin_coach.integrations.strava.sync as sync

    monkeypatch.setattr(sync, "INTEGRATIONS_DIR", str(tmp_path))
    state_file = tmp_path / "strava_sync_state.json"
    monkeypatch.setattr(sync, "STRAVA_SYNC_STATE_FILE", str(state_file))
    state_file.write_text(
        json.dumps({"days": {"2026-03-29": {"fingerprint": "old", "external_ids": ["a1"]}}})
    )

    saved = []

    class FakeManager:
        def __init__(self):
            self.calculator = SimpleNamespace(
                get_session=lambda d: SimpleNamespace(description="[strava-sync] old batch"),
                session_calculator=SimpleNamespace(calculate_trimp=lambda **kwargs: 20.0),
            )

        def add_activity(self, session_date, trimp, sport, duration_min, description=""):
            saved.append((session_date.isoformat(), trimp, sport, duration_min, description))

    monkeypatch.setattr(sync, "get_training_load_manager", lambda: FakeManager())

    class FakeAdapter:
        def is_authenticated(self):
            return True

        def get_activities(self, start_date, end_date=None, sport_type=None):
            return [
                SimpleNamespace(
                    activity_id="a1",
                    sport_type="Run",
                    start_time=datetime(2026, 3, 29, 7, 0, tzinfo=timezone.utc),
                    duration_seconds=2400,
                    distance_meters=6000,
                    calories=350,
                    heart_rate_avg=155,
                    raw_data={"activity": {"start_date_local": "2026-03-29T16:00:00"}},
                )
            ]

    monkeypatch.setattr(sync, "StravaAdapter", FakeAdapter)
    result = sync.sync_strava_training_load(days=7, dry_run=False)
    assert result["updated"] == 1
    assert saved


def test_sync_strava_training_load_removes_stale_previous_day(monkeypatch, tmp_path):
    import json
    import garmin_coach.integrations.strava.sync as sync

    monkeypatch.setattr(sync, "INTEGRATIONS_DIR", str(tmp_path))
    state_file = tmp_path / "strava_sync_state.json"
    monkeypatch.setattr(sync, "STRAVA_SYNC_STATE_FILE", str(state_file))
    state_file.write_text(json.dumps({"days": {"2026-03-29": {"fingerprint": "old"}}}))

    removed = []
    saved = []

    class FakeCalculator:
        def __init__(self):
            self.session_calculator = SimpleNamespace(calculate_trimp=lambda **kwargs: 20.0)

        def get_session(self, d):
            if d.isoformat() == "2026-03-29":
                return SimpleNamespace(description="[strava-sync] old batch")
            return None

        def remove_session(self, d):
            removed.append(d.isoformat())
            return True

    class FakeManager:
        def __init__(self):
            self.calculator = FakeCalculator()

        def add_activity(self, session_date, trimp, sport, duration_min, description=""):
            saved.append(session_date.isoformat())

        def save(self):
            return None

    monkeypatch.setattr(sync, "get_training_load_manager", lambda: FakeManager())

    class FakeAdapter:
        def is_authenticated(self):
            return True

        def get_activities(self, start_date, end_date=None, sport_type=None):
            return [
                SimpleNamespace(
                    activity_id="shifted",
                    sport_type="Run",
                    start_time=datetime(2026, 3, 29, 23, 30, tzinfo=timezone.utc),
                    duration_seconds=1800,
                    distance_meters=5000,
                    calories=300,
                    heart_rate_avg=150,
                    raw_data={"activity": {"start_date_local": "2026-03-30T08:30:00"}},
                )
            ]

    monkeypatch.setattr(sync, "StravaAdapter", FakeAdapter)
    result = sync.sync_strava_training_load(days=7, dry_run=False)
    assert result["removed"] == 1
    assert removed == ["2026-03-29"]
    assert saved == ["2026-03-30"]


def test_sync_strava_training_load_keeps_old_days_outside_window(monkeypatch, tmp_path):
    import json
    import garmin_coach.integrations.strava.sync as sync

    monkeypatch.setattr(sync, "INTEGRATIONS_DIR", str(tmp_path))
    state_file = tmp_path / "strava_sync_state.json"
    monkeypatch.setattr(sync, "STRAVA_SYNC_STATE_FILE", str(state_file))
    state_file.write_text(json.dumps({"days": {"2026-03-01": {"fingerprint": "old"}}}))

    removed = []

    class FakeCalculator:
        def __init__(self):
            self.session_calculator = SimpleNamespace(calculate_trimp=lambda **kwargs: 20.0)

        def get_session(self, d):
            if d.isoformat() == "2026-03-01":
                return SimpleNamespace(description="[strava-sync] old batch")
            return None

        def remove_session(self, d):
            removed.append(d.isoformat())
            return True

    class FakeManager:
        def __init__(self):
            self.calculator = FakeCalculator()

        def add_activity(self, session_date, trimp, sport, duration_min, description=""):
            return None

        def save(self):
            return None

    monkeypatch.setattr(sync, "get_training_load_manager", lambda: FakeManager())

    class FakeAdapter:
        def is_authenticated(self):
            return True

        def get_activities(self, start_date, end_date=None, sport_type=None):
            return []

    monkeypatch.setattr(sync, "StravaAdapter", FakeAdapter)
    result = sync.sync_strava_training_load(days=7, dry_run=False)
    assert result["removed"] == 0
    assert removed == []


def test_sync_strava_training_load_uses_midnight_window_start(monkeypatch, tmp_path):
    import garmin_coach.integrations.strava.sync as sync

    monkeypatch.setattr(sync, "INTEGRATIONS_DIR", str(tmp_path))
    monkeypatch.setattr(sync, "STRAVA_SYNC_STATE_FILE", str(tmp_path / "strava_sync_state.json"))
    calc = SimpleNamespace(
        get_session=lambda d: None,
        session_calculator=SimpleNamespace(calculate_trimp=lambda **kwargs: 20.0),
    )
    manager = SimpleNamespace(calculator=calc, add_activity=lambda **kwargs: None)
    monkeypatch.setattr(sync, "get_training_load_manager", lambda: manager)

    captured = {}

    class FakeAdapter:
        def is_authenticated(self):
            return True

        def get_activities(self, start_date, end_date=None, sport_type=None):
            captured["start_date"] = start_date
            return []

    monkeypatch.setattr(sync, "StravaAdapter", FakeAdapter)
    sync.sync_strava_training_load(days=7, dry_run=True)
    assert captured["start_date"].hour == 0
    assert captured["start_date"].minute == 0


def test_sync_yields_to_garmin_takeover(monkeypatch, tmp_path):
    """When Garmin has imported a session for a day we previously synced,
    we yield to Garmin: clear our state record and skip the day."""
    import json
    import garmin_coach.integrations.strava.sync as sync

    monkeypatch.setattr(sync, "INTEGRATIONS_DIR", str(tmp_path))
    state_file = tmp_path / "strava_sync_state.json"
    monkeypatch.setattr(sync, "STRAVA_SYNC_STATE_FILE", str(state_file))
    # Existing state says we own 2026-03-29
    state_file.write_text(json.dumps({
        "days": {"2026-03-29": {"fingerprint": "old", "source": "strava", "external_ids": ["a1"]}}
    }))

    added = []

    class FakeManager:
        def __init__(self):
            self.calculator = SimpleNamespace(
                # Session exists but has Garmin description (not ours)
                get_session=lambda d: SimpleNamespace(description="Garmin Morning Run"),
                session_calculator=SimpleNamespace(calculate_trimp=lambda **kwargs: 20.0),
            )

        def add_activity(self, **kwargs):
            added.append(kwargs)

    monkeypatch.setattr(sync, "get_training_load_manager", lambda: FakeManager())

    from datetime import timezone
    class FakeAdapter:
        def is_authenticated(self):
            return True

        def get_activities(self, start_date, end_date=None, sport_type=None):
            return [
                SimpleNamespace(
                    activity_id="a1",
                    sport_type="Run",
                    start_time=datetime(2026, 3, 29, 7, 0, tzinfo=timezone.utc),
                    duration_seconds=1800,
                    distance_meters=5000,
                    calories=300,
                    heart_rate_avg=150,
                    raw_data={"activity": {}},
                )
            ]

    monkeypatch.setattr(sync, "StravaAdapter", FakeAdapter)
    result = sync.sync_strava_training_load(days=7, dry_run=False)

    # Should skip, not overwrite the Garmin session
    assert result["skipped"] == 1
    assert not added
    # State record for that day should be cleared (yielded to Garmin)
    saved = json.loads(state_file.read_text())
    assert "2026-03-29" not in saved["days"]


def test_stale_removal_not_existing_clears_state(monkeypatch, tmp_path):
    """If a previously-synced session was externally removed (not found in
    training_load), just clean up the state record without counting as removed."""
    import json
    import garmin_coach.integrations.strava.sync as sync

    monkeypatch.setattr(sync, "INTEGRATIONS_DIR", str(tmp_path))
    state_file = tmp_path / "strava_sync_state.json"
    monkeypatch.setattr(sync, "STRAVA_SYNC_STATE_FILE", str(state_file))
    state_file.write_text(json.dumps({
        "days": {"2026-03-29": {"fingerprint": "old", "external_ids": ["a1"]}}
    }))

    class FakeManager:
        def __init__(self):
            self.calculator = SimpleNamespace(
                get_session=lambda d: None,  # session gone
                session_calculator=SimpleNamespace(calculate_trimp=lambda **kwargs: 20.0),
            )

        def add_activity(self, **kwargs):
            pass

        def save(self):
            pass

    monkeypatch.setattr(sync, "get_training_load_manager", lambda: FakeManager())

    from datetime import timezone
    class FakeAdapter:
        def is_authenticated(self):
            return True

        def get_activities(self, *a, **kw):
            # Return activity on a different day so 2026-03-29 is stale
            return [
                SimpleNamespace(
                    activity_id="b1",
                    sport_type="Run",
                    start_time=datetime(2026, 3, 30, 7, 0, tzinfo=timezone.utc),
                    duration_seconds=1800,
                    distance_meters=5000,
                    calories=300,
                    heart_rate_avg=150,
                    raw_data={"activity": {}},
                )
            ]

    monkeypatch.setattr(sync, "StravaAdapter", FakeAdapter)
    result = sync.sync_strava_training_load(days=7, dry_run=False)

    # Not counted as removed (session wasn't there to remove)
    assert result["removed"] == 0
    # State entry cleared
    saved = json.loads(state_file.read_text())
    assert "2026-03-29" not in saved["days"]
