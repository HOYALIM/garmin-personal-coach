import io
import json
from datetime import datetime
from types import SimpleNamespace


def test_adapter_support_wave(monkeypatch, tmp_path):
    import garmin_coach.adapters.fetch as fetch
    import garmin_coach.adapters.garmin as garmin
    import garmin_coach.adapters.nike as nike
    import garmin_coach.calendar_sync as calendar_sync
    import garmin_coach.logging_config as logging_config
    import garmin_coach.nutrition.hydration as hydration
    import garmin_coach.training_load_manager as tlm
    import garmin_coach.wizard.oauth as oauth
    from garmin_coach.models import WorkoutLog

    fetcher = fetch.UnifiedFetcher()
    assert fetcher.primary_source() is None
    source = SimpleNamespace(is_authenticated=lambda: True)
    # Phase 2: Strava is supplemental, not a primary-source fallback.
    fetcher.register("strava", source)
    assert fetcher.primary_source() is None
    # Garmin registered → becomes primary.
    garmin_src = SimpleNamespace(is_authenticated=lambda: True)
    fetcher.register("garmin", garmin_src)
    assert fetcher.primary_source() is garmin_src
    fetch._default_fetcher = None
    monkeypatch.setattr(
        fetch, "GarminAdapter", lambda: SimpleNamespace(is_authenticated=lambda: False)
    )
    monkeypatch.setattr(
        fetch, "StravaAdapter", lambda: SimpleNamespace(is_authenticated=lambda: True)
    )
    monkeypatch.setattr(
        fetch, "NikeAdapter", lambda: SimpleNamespace(is_authenticated=lambda: False)
    )
    gf = fetch.get_fetcher()
    assert gf.get_source("strava") is not None
    assert gf.get_source("nike") is None

    fake_garth = SimpleNamespace(
        resume=lambda home: True,
        connectapi=lambda path, max_retries=1: {} if path == "/usersettings" else {},
        DailySummary=SimpleNamespace(get=lambda d: None),
    )
    monkeypatch.setattr(garmin, "garth", fake_garth)
    adapter = garmin.GarminAdapter()
    assert adapter.get_profile() is None
    monkeypatch.setattr(
        garmin,
        "datetime",
        SimpleNamespace(
            now=lambda: datetime(2026, 3, 29, 12, 0, 0), fromisoformat=datetime.fromisoformat
        ),
    )
    assert adapter.get_activities(datetime(2026, 3, 29), sport_type="run") == []

    bad_daily = [
        SimpleNamespace(activity_type=SimpleNamespace(type_key="run"), start_time_local="bad-date")
    ]
    fake_garth2 = SimpleNamespace(
        resume=lambda home: True,
        connectapi=lambda *args, **kwargs: {"displayName": "Pat", "userId": "u1"},
        DailySummary=SimpleNamespace(get=lambda d: bad_daily if d.endswith("29") else []),
    )
    monkeypatch.setattr(garmin, "garth", fake_garth2)
    acts = garmin.GarminAdapter().get_activities(
        datetime(2026, 3, 29), datetime(2026, 3, 29), sport_type="bike"
    )
    assert acts == []
    assert garmin.GarminAdapter().get_daily_summary(datetime(2026, 3, 29)) is None
    monkeypatch.setattr(
        garmin, "datetime", SimpleNamespace(now=lambda: datetime(2026, 3, 29, 12, 0, 0))
    )
    assert garmin.GarminAdapter().get_time_series("ctl", datetime(2026, 3, 29)) == []

    nike.NIKE_CONFIG_DIR = str(tmp_path)
    assert nike.get_nike_token() is None
    token_file = tmp_path / "nike_token.json"
    token_file.write_text("bad")
    assert nike.get_nike_token() is None
    na = nike.NikeAdapter()
    assert na.get_profile() is None
    assert na.get_activities(datetime(2026, 3, 29)) == []
    assert na.get_daily_summary(datetime(2026, 3, 29)) is None
    assert na.get_time_series("ctl", datetime(2026, 3, 29)) == []

    monkeypatch.setattr(calendar_sync, "CALDAV_URL", "x")
    monkeypatch.setattr(calendar_sync, "CALDAV_USER", "u")
    monkeypatch.setattr(calendar_sync, "CALDAV_PASS", "p")
    monkeypatch.setitem(__import__("sys").modules, "caldav", None)
    assert calendar_sync._caldav_available() is False
    log = WorkoutLog(date="2026-03-29")
    assert calendar_sync.merge_description("", log).startswith(calendar_sync.WORKOUT_BLOCK_START)
    assert calendar_sync.find_and_update_workout_event("2026-03-29", log) is None

    class Raw:
        text = "rawtext"

    class Event:
        def __init__(self):
            self.summary = "long run"
            self.raw = Raw()
            self.saved = False

        def save(self):
            self.saved = True

    class Cal:
        name = "Training"

        def search_events(self, start, end, expand=True):
            return [Event()]

    client = SimpleNamespace(principal=lambda: SimpleNamespace(calendars=lambda: [Cal()]))
    monkeypatch.setitem(
        __import__("sys").modules,
        "caldav",
        SimpleNamespace(DAVClient=lambda *args, **kwargs: client, Calendar=object, Event=object),
    )
    assert calendar_sync.find_and_update_workout_event("2026-03-29", log) == "long run (2026-03-29)"

    class BadLogfire:
        def configure(self, **kwargs):
            raise RuntimeError("nope")

        def info(self, message, **context):
            raise RuntimeError("nope")

    monkeypatch.setattr(logging_config, "_logfire_module", BadLogfire())
    logging_config._configure_logfire()
    logging_config._emit_to_logfire("info", "x")
    monkeypatch.setattr(logging_config, "_logfire_module", None)
    logging_config._configure_logfire()
    logging_config._emit_to_logfire("info", "x")

    hydration.DATA_DIR = str(tmp_path)
    hydration.HYDRATION_FILE = str(tmp_path / "hydration.json")
    with open(hydration.HYDRATION_FILE, "w") as f:
        f.write("bad")
    assert hydration.load_hydration_data() == {}
    fake_dt = SimpleNamespace(
        now=lambda: datetime(2026, 3, 29, 10, 0, 0),
        strftime=datetime.strftime,
    )
    monkeypatch.setattr(
        hydration, "datetime", SimpleNamespace(now=lambda: datetime(2026, 3, 29, 10, 0, 0))
    )
    hydration.log_water(250)
    assert hydration.check_hydration_status(2000) == "just_started"
    monkeypatch.setattr(hydration, "get_today_intake", lambda: 1500)
    assert hydration.check_hydration_status(2000) == "almost_there"
    monkeypatch.setattr(hydration, "get_today_intake", lambda: 600)
    assert hydration.check_hydration_status(2000) == "getting_started"
    monkeypatch.setattr(hydration, "get_today_intake", lambda: 500)
    assert hydration.get_hydration_summary()["target_ml"] == 2500

    cfg = tmp_path / "config.yaml"
    cfg.write_text("not: [valid")
    tlm.DATA_DIR = str(tmp_path)
    tlm.LOAD_FILE = str(tmp_path / "training_load.json")
    tlm.PROFILE_FILE = str(cfg)
    tlm.TrainingLoadManager.reset()
    mgr = tlm.TrainingLoadManager()
    assert mgr._sex == "male"
    tlm.TrainingLoadManager.reset()
    with open(tlm.LOAD_FILE, "w") as f:
        f.write("bad")
    mgr = tlm.TrainingLoadManager()
    mgr._calc.export_json = lambda path: (_ for _ in ()).throw(RuntimeError("bad"))
    mgr.save()

    handler = oauth.OAuthCallbackHandler.__new__(oauth.OAuthCallbackHandler)
    handler.path = "/callback?code=abc"
    handler.wfile = io.BytesIO()
    handler.send_response = lambda code: None
    handler.send_header = lambda key, value: None
    handler.end_headers = lambda: None
    oauth.OAuthCallbackHandler.received_params = None
    handler.do_GET()
    assert oauth.OAuthCallbackHandler.received_params["code"] == ["abc"]
    oauth.OAuthCallbackHandler.log_message(handler, "%s")
