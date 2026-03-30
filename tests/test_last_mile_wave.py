import builtins
import runpy
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace


def test_last_mile_wave(monkeypatch, tmp_path):
    import garmin_coach.adapters.fetch as fetch
    import garmin_coach.adapters.garmin as garmin
    import garmin_coach.adapters.nike as nike
    import garmin_coach.adapters.strava as strava
    import garmin_coach.calendar_sync as calendar_sync
    import garmin_coach.coach_engine as coach_engine
    import garmin_coach.handler as handler
    import garmin_coach.handler.intent as intent
    import garmin_coach.handler.templates as templates
    import garmin_coach.models as models
    import garmin_coach.morning_checkin as morning
    import garmin_coach.nutrition as nutrition
    import garmin_coach.periodization as periodization
    import garmin_coach.profile_manager as profile_manager
    import garmin_coach.rate_limit as rate_limit
    import garmin_coach.scheduler as scheduler
    import garmin_coach.update_check as update_check
    import garmin_coach.wizard as wizard
    import garmin_coach.wizard.oauth as oauth

    fetcher = fetch.UnifiedFetcher()
    fetcher.register(
        "nike", SimpleNamespace(get_profile=lambda: (_ for _ in ()).throw(RuntimeError("x")))
    )
    assert fetcher.combined_profile() is None

    act = SimpleNamespace(
        activity_type=SimpleNamespace(type_key="running"),
        start_time_local="2026-03-29T07:00:00",
        distance=1000,
        duration=60,
        activity_id=1,
        activity_name="Run",
    )
    monkeypatch.setattr(
        garmin,
        "garth",
        SimpleNamespace(
            resume=lambda home: True, DailySummary=SimpleNamespace(get=lambda d: [act])
        ),
    )
    activities = garmin.GarminAdapter().get_activities(datetime(2026, 3, 29), datetime(2026, 3, 29))
    assert activities[0].start_time == datetime.fromisoformat("2026-03-29T07:00:00")
    monkeypatch.setattr(
        garmin,
        "garth",
        SimpleNamespace(resume=lambda home: True, DailySummary=SimpleNamespace(get=lambda d: [])),
    )
    assert garmin.GarminAdapter().get_daily_summary(datetime(2026, 3, 29)) is None

    nike.NIKE_CONFIG_DIR = str(tmp_path)
    (tmp_path / "nike_token.json").write_text('{"user_id":"1","name":"N"}')
    adapter_nike = nike.NikeAdapter()
    assert adapter_nike.get_profile().name == "N"
    assert adapter_nike.get_profile().name == "N"

    monkeypatch.setattr(strava, "get_strava_token", lambda: None)
    assert strava.StravaAdapter().is_authenticated() is False
    sa = strava.StravaAdapter()
    sa._profile_cache = SimpleNamespace(name="cached")
    assert sa.get_profile().name == "cached"
    sa = strava.StravaAdapter()
    monkeypatch.setattr(sa, "_get_headers", lambda: {})
    assert sa.get_profile() is None
    assert sa.get_activities(datetime(2026, 3, 29)) == []
    sa = strava.StravaAdapter()
    sa._token = {"access_token": "tok"}
    monkeypatch.setattr(
        strava.requests,
        "get",
        lambda *args, **kwargs: SimpleNamespace(
            status_code=200,
            json=lambda: {
                "id": 1,
                "firstname": "P",
                "lastname": "D",
                "athlete_type": {"code": ["run", "ride"]},
            },
        ),
    )
    assert sa.get_profile().sport_preferences == ["run", "ride"]
    page = [
        {
            "id": i,
            "name": str(i),
            "type": "Run",
            "start_date": "2026-03-29T07:00:00Z",
            "elapsed_time": 60,
            "distance": 1000,
            "average_speed": 2,
            "total_elevation_gain": 1,
        }
        for i in range(100)
    ]
    calls = {"n": 0}

    def paged(*args, **kwargs):
        calls["n"] += 1
        return SimpleNamespace(status_code=200, json=lambda: page if calls["n"] == 1 else [])

    monkeypatch.setattr(strava.requests, "get", paged)
    sa = strava.StravaAdapter()
    sa._token = {"access_token": "tok"}
    assert len(sa.get_activities(datetime(2026, 3, 29), datetime(2026, 3, 29))) == 100
    assert calls["n"] == 2
    monkeypatch.setattr(
        strava,
        "datetime",
        SimpleNamespace(
            now=lambda: datetime(2026, 3, 30, 0, 0), fromisoformat=datetime.fromisoformat
        ),
    )
    sa.get_daily_summary = lambda d: SimpleNamespace(tsb=1)
    assert len(sa.get_time_series("tsb", datetime(2026, 3, 29))) >= 1

    log = models.WorkoutLog(date="2026-03-29")
    client = SimpleNamespace(principal=lambda: (_ for _ in ()).throw(RuntimeError("bad")))
    monkeypatch.setattr(calendar_sync, "_caldav_available", lambda: True)
    monkeypatch.setitem(
        __import__("sys").modules,
        "caldav",
        SimpleNamespace(DAVClient=lambda *args, **kwargs: client, Calendar=object, Event=object),
    )
    assert calendar_sync.find_and_update_workout_event("2026-03-29", log) is None
    client2 = SimpleNamespace(
        principal=lambda: SimpleNamespace(
            calendars=lambda: [SimpleNamespace(name="Other", search_events=lambda **kwargs: [])]
        )
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "caldav",
        SimpleNamespace(DAVClient=lambda *args, **kwargs: client2, Calendar=object, Event=object),
    )
    assert calendar_sync.find_and_update_workout_event("2026-03-29", log) is None

    assert coach_engine.score_hrv_or_readiness(None, 50) == (1, "readiness fair")
    mm = models.MorningMetrics(
        sleep_hours=7, resting_hr=50, body_battery=80, training_readiness=70, hrv_status="balanced"
    )
    result = models.MorningResult(
        date="2026-03-29",
        phase=models.Phase.PRECHECK,
        week=1,
        planned_session="easy",
        recommended_session="go",
        status=models.Status.GREEN,
        reasons=[],
        total_score=0,
        execution_guidance=[],
        week_brief="brief",
        session_purpose="purpose",
        pace_hr_guidance="guide",
        downgrade_rule="rule",
        metrics=mm,
        freshness={},
    )
    assert result.to_dict()["date"] == "2026-03-29"

    monkeypatch.setattr(handler, "log_warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(handler.os.path, "exists", lambda path: True)
    monkeypatch.setitem(
        __import__("sys").modules,
        "yaml",
        SimpleNamespace(safe_load=lambda f: (_ for _ in ()).throw(RuntimeError("bad"))),
    )
    assert handler._load_config() == {}
    assert "Moderate training" in handler.MessageHandler(
        config={}, user_context={}
    )._handle_ask_nutrition({"ctl": 40})
    assert intent.detect_intent("일어났어") == intent.Intent.WAKE_UP
    assert intent.detect_intent("운동 끝") == intent.Intent.WORKOUT_COMPLETE
    assert templates.get_form_description(-30) == templates.FORM_DESCRIPTIONS["overreaching"]

    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "logfire":
            raise ImportError("blocked")
        if name == "requests":
            raise ImportError("blocked")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    log_mod = runpy.run_path("/tmp/garmin-personal-coach/garmin_coach/logging_config.py")
    upd_mod = runpy.run_path("/tmp/garmin-personal-coach/garmin_coach/update_check.py")
    assert log_mod["_logfire_module"] is None
    assert upd_mod["requests"] is None
    monkeypatch.setattr(builtins, "__import__", orig_import)

    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"rhr_history": []}')
    monkeypatch.setattr(morning, "BASELINE_FILE", baseline)
    assert morning.load_baseline()["rhr_history"] == []
    monkeypatch.setattr(
        "sys.argv", ["morning_checkin", "--date", "2026-03-29", "--phase", "final", "--pain"]
    )
    assert morning.parse_args().phase == "final"
    monkeypatch.setattr(morning, "main", lambda: None)
    runpy.run_module("garmin_coach.morning_checkin", run_name="__main__")

    assert nutrition.calculate_basal_metabolic_rate(
        70, 175, 30, "female"
    ) < nutrition.calculate_basal_metabolic_rate(70, 175, 30, "male")
    ml = rate_limit.MultiLimiter()
    limiter = ml.get_limiter("x", max_requests=1, window_seconds=10)
    assert limiter.max_requests == 1
    assert rate_limit.RateLimiter().get_reset_time("missing") == 0
    monkeypatch.setattr(scheduler, "_is_shutdown_requested", lambda: True)
    monkeypatch.setattr(
        scheduler,
        "ProfileManager",
        lambda: SimpleNamespace(
            load=lambda: SimpleNamespace(
                schedule=SimpleNamespace(
                    morning_checkin={"enabled": True, "time": "06:00"},
                    final_check={"enabled": True, "time": "06:30"},
                    evening_checkin={"enabled": True, "time": "22:00"},
                    weekly_review={"enabled": False, "day": "sunday", "time": "21:00"},
                )
            )
        ),
    )
    monkeypatch.setattr(scheduler, "_register_signal_handlers", lambda: None)
    monkeypatch.setattr(scheduler, "resume_garth", lambda: True)
    scheduler.dispatch_scheduled()

    monkeypatch.setattr(update_check.os.path, "exists", lambda path: False)
    assert update_check._read_cache() is None

    monkeypatch.setattr(wizard, "run_wizard", lambda: None)
    runpy.run_module("garmin_coach.wizard", run_name="__main__")

    monkeypatch.setattr(
        oauth.time, "sleep", lambda x: setattr(oauth.OAuthCallbackHandler, "received_params", {})
    )
    monkeypatch.setattr(oauth.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(
        oauth,
        "HTTPServer",
        lambda *args, **kwargs: SimpleNamespace(
            handle_request=lambda: None, server_close=lambda: None
        ),
    )
    monkeypatch.setattr(
        oauth.threading, "Thread", lambda target: SimpleNamespace(start=lambda: target())
    )
    assert oauth.OAuthFlow.strava_auth("id", "secret") is None
    monkeypatch.setattr(oauth.os.path, "exists", lambda path: False)
    assert oauth.OAuthFlow.check_strava_token() is False

    profile = profile_manager.UserProfile(profile=profile_manager.ProfileData(name="Pat"))
    pm = periodization.PeriodizationEngine(
        profile=profile, plan_start=date(2026, 1, 1), goal_date=date(2026, 1, 15)
    )
    assert pm._build_phase_sequence(9)[-1].name == periodization.Phase.BUILD
    assert pm._generate_sessions(1, SimpleNamespace(name="other"), False, date(2026, 1, 1)) == []
    profile.profile.sports = [profile_manager.Sport.TRIATHLON, profile_manager.Sport.CYCLING]
    tri = periodization.PeriodizationEngine(profile=profile, plan_start=date(2026, 1, 1))
    assert any(
        s["sport"] == "cycling"
        for s in tri._base_sessions(date(2026, 1, 1), ["triathlon", "cycling"], 5, True)
    )
    assert tri.get_week(999) is None
    tri._weeks = [
        periodization.WeekPlan(
            week_number=1,
            phase=periodization.Phase.BUILD,
            week_start=date(2026, 1, 8),
            sessions=[],
            total_volume_hours=0,
        )
    ]
    assert tri.get_current_phase(date(2026, 1, 1)) == periodization.Phase.BASE

    raw = {
        "profile": {
            "name": "Pat",
            "sports": ["running"],
            "primary_sport": "running",
            "fitness_level": "intermediate",
        }
    }
    assert (
        profile_manager.ProfileData.from_dict(
            {
                "sports": ["running"],
                "primary_sport": "running",
                "fitness_level": "motivational" if False else "intermediate",
            }
        ).primary_sport
        == profile_manager.Sport.RUNNING
    )
    pmgr = profile_manager.ProfileManager(tmp_path / "empty.yaml")
    assert pmgr.load() is None
    (tmp_path / "empty.yaml").write_text("")
    assert pmgr.load() is None
    assert profile_manager._parse_duration("bad") is None
    assert profile_manager._validate_time("") is False
