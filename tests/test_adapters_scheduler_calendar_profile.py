import json
import runpy
from datetime import date, datetime
from types import SimpleNamespace


def test_calendar_sync_paths(monkeypatch):
    import garmin_coach.calendar_sync as calendar_sync
    from garmin_coach.models import ActivitySummary, WorkoutLog

    log = WorkoutLog(date="2026-03-29", planned="easy", final_status="GREEN", completed="done")
    log.activity = ActivitySummary(type="running", distance_km=5.0, avg_pace="6:00/km", avg_hr=150)
    log.coach_note = "nice"
    log.updated_at = "2026-03-29T10:00:00"

    monkeypatch.setattr(calendar_sync, "CALDAV_URL", "")
    monkeypatch.setattr(calendar_sync, "CALDAV_USER", "")
    monkeypatch.setattr(calendar_sync, "CALDAV_PASS", "")
    assert calendar_sync._caldav_available() is False

    monkeypatch.setattr(calendar_sync, "CALDAV_URL", "http://x")
    monkeypatch.setattr(calendar_sync, "CALDAV_USER", "u")
    monkeypatch.setattr(calendar_sync, "CALDAV_PASS", "p")
    monkeypatch.setitem(__import__("sys").modules, "caldav", SimpleNamespace())
    assert calendar_sync._caldav_available() is True

    block = calendar_sync.build_workout_block(log)
    assert "Garmin Coach Workout Log" in block
    assert "Distance: 5.0 km" in block
    assert calendar_sync.strip_workout_block(f"before\n{block}after").startswith("before")
    assert "nice" in calendar_sync.merge_description("existing", log)
    assert calendar_sync.event_matches_workout("Long Run") is True
    assert calendar_sync.event_matches_workout("") is False

    monkeypatch.setattr(calendar_sync, "_caldav_available", lambda: False)
    assert calendar_sync.find_and_update_workout_event("2026-03-29", log) is None

    monkeypatch.setattr(calendar_sync, "_caldav_available", lambda: True)
    monkeypatch.setitem(__import__("sys").modules, "caldav", None)
    assert calendar_sync.find_and_update_workout_event("2026-03-29", log) is None

    class FakeEvent:
        def __init__(self, summary, data=""):
            self.summary = summary
            self.data = data
            self.saved = False

        def save(self):
            self.saved = True

    target_event = FakeEvent("Morning run", "desc")
    skip_event = FakeEvent("Meeting")
    fake_calendar = SimpleNamespace(
        name="Training Calendar",
        search_events=lambda start, end, expand=True: [skip_event, target_event],
    )
    fake_client = SimpleNamespace(
        principal=lambda: SimpleNamespace(calendars=lambda: [fake_calendar])
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "caldav",
        SimpleNamespace(
            DAVClient=lambda *args, **kwargs: fake_client, Calendar=object, Event=object
        ),
    )
    updated = calendar_sync.find_and_update_workout_event("2026-03-29", log)
    assert updated == "Morning run (2026-03-29)"
    assert target_event.saved is True


def test_scheduler_paths(monkeypatch, capsys, tmp_path):
    import garmin_coach.scheduler as scheduler

    monkeypatch.setattr(
        scheduler,
        "datetime",
        type("FakeDateTime", (), {"now": staticmethod(lambda: datetime(2026, 3, 29, 6, 0))}),
    )
    assert scheduler.parse_time("06:30").hour == 6
    assert scheduler.should_run_now(scheduler.parse_time("06:00")) is True

    scheduler._shutdown_requested = True
    assert scheduler.run_job("morning_checkin") == -1
    scheduler._shutdown_requested = False
    monkeypatch.setattr(scheduler.subprocess, "run", lambda args: SimpleNamespace(returncode=0))
    assert scheduler.run_job("morning_checkin") == 0

    monkeypatch.setattr(scheduler, "_register_signal_handlers", lambda: None)
    monkeypatch.setattr(scheduler, "resume_garth", lambda: False)
    monkeypatch.setattr(scheduler, "should_run_now", lambda *args, **kwargs: True)
    ran = []
    monkeypatch.setattr(scheduler, "run_job", lambda name: ran.append(name) or 0)
    profile = SimpleNamespace(
        schedule=SimpleNamespace(
            morning_checkin={"enabled": True, "time": "06:00"},
            final_check={"enabled": True, "time": "06:30"},
            evening_checkin={"enabled": False, "time": "22:00"},
            weekly_review={"enabled": True, "day": "sunday", "time": "21:00"},
        )
    )
    monkeypatch.setattr(
        scheduler,
        "ProfileManager",
        lambda: SimpleNamespace(load=lambda: profile, config_path=tmp_path / "config.yaml"),
    )
    scheduler._shutdown_requested = False
    scheduler.dispatch_scheduled()
    assert ran == ["morning_checkin", "final_check", "weekly_review"]
    assert "No Garmin session" in capsys.readouterr().out

    monkeypatch.setattr(
        scheduler,
        "ProfileManager",
        lambda: SimpleNamespace(load=lambda: None, config_path=tmp_path / "config.yaml"),
    )
    try:
        scheduler.dispatch_scheduled()
    except SystemExit:
        pass

    monkeypatch.setattr(scheduler, "dispatch_scheduled", lambda: ran.append("dispatch"))
    monkeypatch.setattr(
        "sys.argv", ["scheduler", "--install-cron", "--profile", str(tmp_path / "p.yaml")]
    )
    scheduler.main()
    monkeypatch.setattr("sys.argv", ["scheduler", "--dispatch"])
    scheduler.main()
    monkeypatch.setattr("sys.argv", ["scheduler"])
    scheduler.main()
    output = capsys.readouterr().out
    assert "crontab -e" in output
    assert "Usage:" in output


def test_profile_manager_remaining_branches(tmp_path):
    from garmin_coach.profile_manager import (
        AICoachConfig,
        AIFlexibility,
        AITone,
        FitnessData,
        FitnessLevel,
        GarminConfig,
        GarMiniAuthMethod,
        HRZones,
        NotificationMethod,
        PaceZones,
        PowerZones,
        ProfileData,
        ProfileManager,
        ProfileValidationError,
        ScheduleConfig,
        Sex,
        Sport,
        SwimZones,
        TrainingZones,
        UserProfile,
    )

    pm = ProfileManager(tmp_path / "config.yaml")
    profile = UserProfile(
        profile=ProfileData(
            name="Pat",
            age=30,
            sex=Sex.FEMALE,
            sports=[Sport.RUNNING],
            goal_date="bad-date",
            available_days=8,
            max_weekly_hours=50,
        ),
        fitness=FitnessData(
            recent_5k="bad", cycling_ftp_w=10, resting_hr=10, max_hr=300, swim_100m_pace="bad"
        ),
        garmin=GarminConfig(email="a", connected=True, auth_method=GarMiniAuthMethod.GARTH),
        schedule=ScheduleConfig(
            morning_checkin={"enabled": True, "time": "bad"},
            final_check={"enabled": True, "time": "06:00"},
            evening_checkin={"enabled": True, "time": "22:00"},
            weekly_review={"enabled": True, "day": "noday", "time": "xx"},
        ),
        ai_coach=AICoachConfig(
            enabled=True,
            flexibility=AIFlexibility.FLEXIBLE,
            tone=AITone.DIRECT,
            can_modify_plan=True,
            notification_method=NotificationMethod.TELEGRAM,
        ),
    )
    errors = pm.validate(profile)
    assert any("goal_date" in e for e in errors)
    assert any("weekly_review.day" in e for e in errors)
    try:
        pm.validate_or_raise(profile)
    except ProfileValidationError as exc:
        assert exc.errors

    ok = UserProfile(
        profile=ProfileData(
            name="Pat",
            age=30,
            sex=Sex.MALE,
            sports=[Sport.RUNNING, Sport.CYCLING],
            goal_date="2026-12-01",
            fitness_level=FitnessLevel.ADVANCED,
        ),
        fitness=FitnessData(
            recent_5k="20:00",
            recent_10k="42:00",
            recent_half="1:40:00",
            recent_marathon="3:45:00",
            cycling_ftp_w=250,
            resting_hr=50,
            max_hr=190,
            swim_100m_pace="1:40",
        ),
    )
    pm.save(ok)
    loaded = pm.load()
    assert loaded.profile.name == "Pat"
    assert HRZones(1, 2, 3, 4, 5, 6, 7, 8, 9, 10).for_sport(Sport.RUNNING)["z1_min"] == 1
    assert PaceZones(z1="7:00/km").to_dict()["z1"] == "7:00/km"
    assert PowerZones(z1_max=100).to_dict()["z1_max"] == 100
    assert SwimZones(easy_max="2:00/100m").to_dict()["easy_max"] == "2:00/100m"
    assert TrainingZones(hr=pm.calculate_hr_zones(ok)).to_dict()["hr"]
    assert pm.calculate_running_pace_zones(ok).threshold_pace
    assert pm.calculate_cycling_power_zones(ok).z7_min > 0
    assert pm.calculate_swim_zones(ok).easy_max
    assert pm.calculate_all_zones(ok).hr.z5_max == 190
    assert pm.weekly_hours_target(ok) == (10.0, 15.0)


def test_fetch_and_adapter_remaining_paths(monkeypatch, tmp_path):
    import garmin_coach.adapters.fetch as fetch
    import garmin_coach.adapters.garmin as garmin
    import garmin_coach.adapters.strava as strava
    from garmin_coach.adapters import Activity, DailySummary, UserProfile

    fetcher = fetch.UnifiedFetcher()
    assert fetcher.get_source("missing") is None
    fetcher.register(
        "strava",
        SimpleNamespace(
            get_activities=lambda *args: [],
            get_daily_summary=lambda date: None,
            get_profile=lambda: None,
            is_authenticated=lambda: True,
        ),
    )
    assert fetcher.primary_source() is fetcher.get_source("strava")
    fetcher.register(
        "broken",
        SimpleNamespace(
            get_activities=lambda *args: (_ for _ in ()).throw(RuntimeError("boom")),
            get_daily_summary=lambda date: (_ for _ in ()).throw(RuntimeError("boom")),
            get_profile=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            is_authenticated=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        ),
    )
    assert fetcher.all_activities(datetime.now()) == []
    assert fetcher.merged_daily_summary(datetime.now()) is None
    assert fetcher.combined_profile() is None
    assert fetcher.health_status()["broken"] is False

    act = Activity(
        "1", "Run", "running", datetime.now(), 1800, 5000, 300, 150, 170, None, 300, 5, {}
    )
    summary = DailySummary(datetime.now(), 10, 5, 5, 20, [act], 30, 5.0, 300)
    fetcher.register(
        "garmin",
        SimpleNamespace(
            get_activities=lambda *args: [act],
            get_daily_summary=lambda d: summary,
            get_profile=lambda: UserProfile("u", "Pat", 30, 70, 190, 50, 250, ["run"]),
            is_authenticated=lambda: True,
        ),
    )
    assert fetcher.merged_daily_summary(datetime.now()).total_distance_km == 5.0
    assert fetcher.combined_profile().name == "Pat"

    fetch._default_fetcher = None
    monkeypatch.setattr(
        fetch, "GarminAdapter", lambda: SimpleNamespace(is_authenticated=lambda: True)
    )
    monkeypatch.setattr(
        fetch, "StravaAdapter", lambda: SimpleNamespace(is_authenticated=lambda: False)
    )
    monkeypatch.setattr(
        fetch, "NikeAdapter", lambda: SimpleNamespace(is_authenticated=lambda: True)
    )
    got = fetch.get_fetcher()
    assert got.get_source("garmin") is not None
    monkeypatch.setattr(fetch, "get_fetcher", lambda: fetcher)
    assert fetch.fetch_activities(1) is not None
    assert fetch.fetch_today_summary() is not None
    assert fetch.fetch_profile().name == "Pat"

    assert garmin.mps_to_pace_sec_per_km(0) is None
    assert garmin.mps_to_pace_sec_per_km(2) == 500.0
    assert garmin.seconds_to_hms(3661) == "01:01:01"

    fake_garth = SimpleNamespace(
        resume=lambda home: True,
        connectapi=lambda path, max_retries=1: {
            "displayName": "Pat",
            "userId": "u1",
            "age": 30,
            "weight": 70,
            "maxHeartRate": 190,
        }
        if path == "/usersettings"
        else {
            "weight": 71,
            "restingHeartRate": 50,
            "cyclingSettings": {"ftp": 250},
            "sports": [{"sportType": {"typeKey": "running"}}],
        },
        DailySummary=SimpleNamespace(
            get=lambda d: [
                SimpleNamespace(
                    activity_type=SimpleNamespace(type_key="running"),
                    start_time_local=datetime(2026, 3, 29, 7, 0),
                    distance=5000,
                    duration=1800,
                    calories=300,
                    average_heart_rate=150,
                    max_heart_rate=170,
                    average_power=220,
                    average_speed=3.5,
                    elevation_gain=50,
                    activity_id=1,
                    activity_name="Run",
                )
            ]
        ),
    )
    monkeypatch.setattr(garmin, "garth", fake_garth)
    adapter = garmin.GarminAdapter()
    assert adapter.is_authenticated() is True
    assert adapter.authenticate({}) is True
    assert adapter.get_profile().name == "Pat"
    assert adapter.get_profile().name == "Pat"
    acts = adapter.get_activities(
        datetime(2026, 3, 29), datetime(2026, 3, 29), sport_type="running"
    )
    assert acts[0].sport_type == "running"
    assert adapter.get_daily_summary(datetime(2026, 3, 29)) is None
    adapter.get_daily_summary = lambda d: SimpleNamespace(ctl=1.0)
    assert adapter.get_time_series("ctl", datetime(2026, 3, 29), datetime(2026, 3, 29))

    monkeypatch.setattr(
        garmin,
        "garth",
        SimpleNamespace(resume=lambda home: (_ for _ in ()).throw(RuntimeError("no"))),
    )
    adapter = garmin.GarminAdapter()
    assert adapter.is_authenticated() is False
    assert adapter.get_profile() is None
    assert adapter.get_activities(datetime(2026, 3, 29), datetime(2026, 3, 29)) == []
    assert adapter.get_daily_summary(datetime(2026, 3, 29)) is None

    strava.STRAVA_CONFIG_DIR = str(tmp_path)
    assert strava.get_strava_token() is None
    strava.save_strava_token({"access_token": "tok", "refresh_token": "r", "expires_at": 999})
    assert strava.get_strava_token()["access_token"] == "tok"
    token_file = tmp_path / "strava_token.json"
    token_file.write_text("bad")
    assert strava.get_strava_token() is None

    adapter = strava.StravaAdapter()
    adapter._token = None
    monkeypatch.setattr(strava, "get_strava_token", lambda: None)
    assert adapter._get_headers() == {}
    monkeypatch.setattr(strava, "get_strava_token", lambda: {"access_token": "tok"})
    assert adapter._get_headers()["Authorization"] == "Bearer tok"
    assert adapter.is_authenticated() is True
    assert adapter.authenticate({}) is False
    monkeypatch.setattr(strava, "save_strava_token", lambda token: None)
    monkeypatch.setattr(strava.StravaAdapter, "is_authenticated", lambda self: True)
    assert adapter.authenticate({"access_token": "tok"}) is True

    adapter = strava.StravaAdapter()
    adapter._token = {"access_token": "tok"}
    monkeypatch.setattr(
        strava.requests,
        "get",
        lambda *args, **kwargs: SimpleNamespace(
            status_code=200,
            json=lambda: {
                "id": 1,
                "firstname": "Pat",
                "lastname": "Doe",
                "athlete_type": {"code": []},
            },
        ),
    )
    assert adapter.get_profile().name == "Pat Doe"
    monkeypatch.setattr(
        strava.requests,
        "get",
        lambda *args, **kwargs: SimpleNamespace(status_code=500, json=lambda: {}),
    )
    adapter._profile_cache = None
    assert adapter.get_profile() is None
    monkeypatch.setattr(
        strava.requests, "get", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    assert adapter.get_profile() is None

    adapter = strava.StravaAdapter()
    adapter._token = {"access_token": "tok"}
    calls = {"n": 0}

    def fake_get(url, headers=None, params=None, timeout=10):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(
                status_code=200,
                json=lambda: [
                    {
                        "id": 1,
                        "name": "Run",
                        "type": "Run",
                        "start_date": "2026-03-29T07:00:00Z",
                        "elapsed_time": 1800,
                        "distance": 5000,
                        "average_speed": 3.5,
                        "average_heartrate": 150,
                        "max_heartrate": 170,
                        "average_watts": 200,
                        "total_elevation_gain": 10,
                    }
                ],
            )
        return SimpleNamespace(status_code=200, json=lambda: [])

    monkeypatch.setattr(strava.requests, "get", fake_get)
    acts = adapter.get_activities(datetime(2026, 3, 28), datetime(2026, 3, 29), sport_type="run")
    assert acts[0].sport_type == "run"
    adapter.get_activities = lambda start, end=None, sport_type=None: acts
    assert adapter.get_daily_summary(datetime(2026, 3, 29)).total_distance_km == 5.0
    adapter = strava.StravaAdapter()
    adapter._token = {"access_token": "tok"}
    monkeypatch.setattr(
        strava.requests, "get", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    assert adapter.get_activities(datetime(2026, 3, 28)) == []
    monkeypatch.setattr(
        strava.StravaAdapter, "get_activities", lambda self, start, end=None, sport_type=None: []
    )
    assert adapter.get_daily_summary(datetime(2026, 3, 29)) is None
