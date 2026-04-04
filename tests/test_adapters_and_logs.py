import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest


def test_adapter_factory_and_unified_fetcher(monkeypatch):
    from garmin_coach.adapters import Activity, DataSourceFactory
    from garmin_coach.adapters.fetch import UnifiedFetcher

    class DummySource:
        def __init__(self, config=None):
            self.config = config or {}

    DataSourceFactory.register("dummy", DummySource)
    created = DataSourceFactory.create("dummy", {"x": 1})
    assert created.config["x"] == 1
    assert "dummy" in DataSourceFactory.available_sources()

    fetcher = UnifiedFetcher()
    activity = Activity(
        activity_id="1",
        name="Run",
        sport_type="running",
        start_time=datetime.now(),
        duration_seconds=1800,
        distance_meters=5000,
        calories=300,
        heart_rate_avg=150,
        heart_rate_max=170,
        power_avg=None,
        pace_sec_per_km=300,
        elevation_gain=10,
        raw_data={},
    )
    summary = SimpleNamespace(
        activities=[activity],
        total_duration_minutes=30,
        total_distance_km=5.0,
        total_calories=300,
        ctl=20,
        atl=15,
        trimp=50,
    )
    source = SimpleNamespace(
        get_activities=lambda *args, **kwargs: [activity],
        get_daily_summary=lambda day: summary,
        get_profile=lambda: SimpleNamespace(name="Pat"),
        is_authenticated=lambda: True,
    )
    fetcher.register("garmin", source)
    assert fetcher.primary_source() is source
    assert (
        fetcher.all_activities(datetime.now() - timedelta(days=1))[0].raw_data["source"] == "garmin"
    )
    assert fetcher.merged_daily_summary(datetime.now()).total_distance_km == 5.0
    assert fetcher.combined_profile().name == "Pat"
    assert fetcher.health_status()["garmin"] is True


def test_garmin_adapter(monkeypatch):
    from garmin_coach.adapters.garmin import GarminAdapter

    monkeypatch.setattr("garmin_coach.adapters.garmin.garth.resume", lambda home: True)
    monkeypatch.setattr(
        "garmin_coach.adapters.garmin.garth.connectapi",
        lambda path, max_retries=1: {"displayName": "Pat", "userId": "u1"}
        if path == "/usersettings"
        else {"weight": 70, "restingHeartRate": 50, "sports": []},
    )
    adapter = GarminAdapter()
    assert adapter.is_authenticated() is True
    profile = adapter.get_profile()
    assert profile.name == "Pat"


def test_strava_and_nike_adapters(monkeypatch, tmp_path):
    import garmin_coach.adapters.strava as strava
    import garmin_coach.adapters.nike as nike

    strava_dir = tmp_path / "strava"
    nike_dir = tmp_path / "nike"
    strava_dir.mkdir()
    nike_dir.mkdir()
    monkeypatch.setattr(strava, "STRAVA_CONFIG_DIR", str(strava_dir))
    monkeypatch.setattr(nike, "NIKE_CONFIG_DIR", str(nike_dir))

    strava.save_strava_token({"access_token": "x", "expires_at": 9999999999})
    assert strava.get_strava_token()["access_token"] == "x"

    athlete_resp = SimpleNamespace(
        status_code=200,
        json=lambda: {"id": 1, "firstname": "Pat", "lastname": "Doe", "athlete_type": {"code": []}},
    )
    activities_resp = SimpleNamespace(
        status_code=200,
        json=lambda: [
            {
                "id": 1,
                "name": "Run",
                "type": "Run",
                "start_date": "2026-03-29T07:00:00Z",
                "elapsed_time": 1800,
                "distance": 5000,
                "average_speed": 3.3,
            }
        ],
    )

    calls = {"count": 0}

    def fake_get(url, **kwargs):
        calls["count"] += 1
        return (
            athlete_resp
            if "athlete" in url
            else activities_resp
            if calls["count"] == 2
            else SimpleNamespace(status_code=200, json=lambda: [])
        )

    monkeypatch.setattr(strava.requests, "get", fake_get)
    strava_adapter = strava.StravaAdapter()
    assert strava_adapter.is_authenticated() is True
    assert strava_adapter.get_profile().name == "Pat Doe"
    assert strava_adapter.get_activities(datetime(2026, 3, 28))

    nike_adapter = nike.NikeAdapter()
    assert nike_adapter.authenticate({"user_id": "n1", "name": "Nike User"}) is True
    assert nike_adapter.get_profile().name == "Nike User"


def test_training_log_and_workout_review(monkeypatch, tmp_path):
    import garmin_coach.training_log as training_log
    import garmin_coach.workout_review as workout_review

    data_dir = tmp_path / "data"
    snapshot_dir = data_dir / "snapshots"
    evening_dir = data_dir / "evening_reviews"
    training_md = data_dir / "training_logs"
    training_json = data_dir / "training_log_json"
    for path in [snapshot_dir, evening_dir, training_md, training_json]:
        path.mkdir(parents=True, exist_ok=True)

    (snapshot_dir / "2026-03-29.json").write_text(
        json.dumps({"recommended_session": "5 km easy", "status": "GREEN"})
    )
    (evening_dir / "2026-03-29.json").write_text(
        json.dumps({"completed": "done", "energy": 4, "legs": 3, "mood": 4})
    )

    monkeypatch.setattr(training_log, "SNAPSHOT_DIR", snapshot_dir)
    monkeypatch.setattr(training_log, "EVENING_DIR", evening_dir)
    monkeypatch.setattr(training_log, "TRAINING_MD_DIR", training_md)
    monkeypatch.setattr(training_log, "TRAINING_JSON_DIR", training_json)
    ingest_calls = []
    monkeypatch.setattr(
        training_log,
        "upsert_activity_to_training_load",
        lambda session_date, activity, source_tag, description=None: ingest_calls.append(
            (session_date.isoformat(), source_tag, description)
        ),
    )
    monkeypatch.setattr(
        training_log,
        "parse_args",
        lambda: SimpleNamespace(
            date="2026-03-29",
            completed="",
            distance_km=5.0,
            duration_min=30.0,
            avg_pace="6:00/km",
            avg_hr=150,
            energy=4,
            legs=3,
            mood=4,
            pain=False,
            illness=False,
            notes="felt good",
            tomorrow_note="easy",
            source="manual",
        ),
    )
    training_log.main()
    assert (training_md / "2026-03-29.md").exists()
    assert ingest_calls[0][0] == "2026-03-29"
    assert ingest_calls[0][1] == "manual-log"

    monkeypatch.setattr(workout_review, "TRAINING_MD_DIR", training_md)
    monkeypatch.setattr(workout_review, "TRAINING_JSON_DIR", training_json)
    monkeypatch.setattr(workout_review, "SNAPSHOT_DIR", snapshot_dir)
    monkeypatch.setattr(
        workout_review,
        "upsert_activity_to_training_load",
        lambda session_date, activity, source_tag, description=None: ingest_calls.append(
            (session_date.isoformat(), source_tag, description)
        ),
    )
    monkeypatch.setattr(workout_review, "resume_garth", lambda: True)
    monkeypatch.setattr(
        workout_review,
        "fetch_recent_activities",
        lambda limit=5: [
            {
                "type": "running",
                "start_time": datetime.now().isoformat(),
                "distance_km": 10.0,
                "duration_min": 60.0,
                "avg_pace": "6:00/km",
                "avg_hr": 150,
            }
        ],
    )
    monkeypatch.setattr(
        workout_review, "find_and_update_workout_event", lambda target_date, log: "Event"
    )
    monkeypatch.setattr(
        workout_review,
        "parse_args",
        lambda: SimpleNamespace(
            date="2026-03-29",
            no_calendar=False,
            distance_km=None,
            duration_min=None,
            avg_pace="",
            avg_hr=None,
            energy=3,
            legs=2,
            mood=3,
            pain=False,
            illness=False,
            notes="",
            tomorrow_note="",
        ),
    )
    workout_review.main()
    assert (training_json / "2026-03-29.json").exists()
    assert ingest_calls[-1][1] == "garmin-review"


def test_training_log_duration_only_still_updates_load(monkeypatch, tmp_path):
    import garmin_coach.training_log as training_log

    data_dir = tmp_path / "data"
    snapshot_dir = data_dir / "snapshots"
    evening_dir = data_dir / "evening_reviews"
    training_md = data_dir / "training_logs"
    training_json = data_dir / "training_log_json"
    for path in [snapshot_dir, evening_dir, training_md, training_json]:
        path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(training_log, "SNAPSHOT_DIR", snapshot_dir)
    monkeypatch.setattr(training_log, "EVENING_DIR", evening_dir)
    monkeypatch.setattr(training_log, "TRAINING_MD_DIR", training_md)
    monkeypatch.setattr(training_log, "TRAINING_JSON_DIR", training_json)
    ingest_calls = []
    monkeypatch.setattr(
        training_log,
        "upsert_activity_to_training_load",
        lambda session_date, activity, source_tag, description=None: ingest_calls.append(
            (session_date.isoformat(), activity.duration_min, source_tag)
        ),
    )
    monkeypatch.setattr(
        training_log,
        "parse_args",
        lambda: SimpleNamespace(
            date="2026-03-29",
            completed="duration only",
            distance_km=None,
            duration_min=40.0,
            avg_pace="",
            avg_hr=None,
            energy=4,
            legs=3,
            mood=4,
            pain=False,
            illness=False,
            notes="steady",
            tomorrow_note="easy",
            source="manual",
        ),
    )
    training_log.main()
    assert ingest_calls == [("2026-03-29", 40.0, "manual-log")]


def test_primary_source_is_garmin_only(monkeypatch):
    """primary_source() returns Garmin when present, and None when only
    Strava is registered — Strava is not a fallback primary source."""
    from garmin_coach.adapters.fetch import UnifiedFetcher

    garmin_src = object()
    strava_src = object()

    fetcher = UnifiedFetcher()
    # No sources → None
    assert fetcher.primary_source() is None

    # Strava only → None (not a runtime primary)
    fetcher.register("strava", strava_src)
    assert fetcher.primary_source() is None

    # Garmin added → Garmin wins
    fetcher.register("garmin", garmin_src)
    assert fetcher.primary_source() is garmin_src


def test_merged_daily_summary_excludes_strava():
    """Strava is never consulted for merged_daily_summary — Garmin is the
    only authoritative training-load source via this path."""
    from datetime import datetime
    from garmin_coach.adapters.fetch import UnifiedFetcher

    consulted = []

    class FakeSource:
        def __init__(self, name):
            self.name = name

        def get_daily_summary(self, date):
            consulted.append(self.name)
            return None

    fetcher = UnifiedFetcher()
    fetcher.register("garmin", FakeSource("garmin"))
    fetcher.register("strava", FakeSource("strava"))
    fetcher.merged_daily_summary(datetime.now())

    assert "garmin" in consulted
    assert "strava" not in consulted
