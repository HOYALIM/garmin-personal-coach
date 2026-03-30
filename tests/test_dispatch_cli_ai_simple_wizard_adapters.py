import runpy
from datetime import datetime
from types import SimpleNamespace

import pytest


def test_dispatch_and_cli_branches(monkeypatch, capsys):
    import garmin_coach.cli as cli
    import garmin_coach.dispatch as dispatch

    calls = []
    monkeypatch.setattr(
        dispatch.subprocess,
        "run",
        lambda args, cwd=None: calls.append((args, cwd)) or SimpleNamespace(returncode=7),
    )
    assert dispatch.run_precheck("2026-03-29") == 7
    assert dispatch.run_final_check("2026-03-29") == 7
    assert dispatch.run_workout_review("2026-03-29") == 7
    assert calls[0][0][1] == "morning_checkin.py"
    assert calls[1][0][1] == "final_check.py"
    assert calls[2][0][1] == "workout_review.py"

    monkeypatch.setattr(
        dispatch,
        "parse_args",
        lambda: SimpleNamespace(
            precheck=False, final=False, workout=False, message="hello", date="2026-03-29"
        ),
    )
    trigger_mod = __import__("garmin_coach.triggers", fromlist=["TriggerType"])
    monkeypatch.setattr(
        trigger_mod,
        "detect_trigger",
        lambda message: SimpleNamespace(trigger_type=trigger_mod.TriggerType.WAKE),
    )
    monkeypatch.setattr(dispatch, "run_final_check", lambda d: 3)
    with pytest.raises(SystemExit) as exc:
        dispatch.main()
    assert exc.value.code == 3

    monkeypatch.setattr(trigger_mod, "detect_trigger", lambda message: None)
    with pytest.raises(SystemExit) as exc:
        dispatch.main()
    assert exc.value.code == 1
    assert "No trigger matched" in capsys.readouterr().out

    monkeypatch.setattr(
        dispatch,
        "parse_args",
        lambda: SimpleNamespace(
            precheck=False, final=False, workout=False, message="", date="2026-03-29"
        ),
    )
    with pytest.raises(SystemExit) as exc:
        dispatch.main()
    assert exc.value.code == 1
    assert "Usage:" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["dispatch", "--message", "hello"])
    monkeypatch.setattr(trigger_mod, "detect_trigger", lambda message: None)
    with pytest.raises(SystemExit):
        runpy.run_module("garmin_coach.dispatch", run_name="__main__")

    monkeypatch.setattr("sys.argv", ["garmin-coach"])
    assert cli.main() == 0
    assert "usage:" in capsys.readouterr().out.lower()

    monkeypatch.setattr("sys.argv", ["garmin-coach", "setup"])
    hit = []
    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.wizard",
        SimpleNamespace(run_wizard=lambda: hit.append("setup")),
    )
    assert cli.main() == 0
    monkeypatch.setattr("sys.argv", ["garmin-coach", "log"])
    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.handler",
        SimpleNamespace(process_message=lambda m: "logged" if "운동" in m else "status"),
    )
    assert cli.main() == 0
    assert "logged" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["garmin-coach", "unknown"])
    assert cli.main() == 1
    assert "Unknown command" in capsys.readouterr().err
    monkeypatch.setattr("sys.argv", ["garmin-coach"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("garmin_coach.cli", run_name="__main__")
    assert exc.value.code == 0


def test_ai_simple_branches(monkeypatch):
    import garmin_coach.ai_simple as ai_simple

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    coach = ai_simple.AICoach()
    assert coach.provider == "none"
    assert coach.model == ""
    assert coach.generate_response("hi", {}) is None

    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    coach = ai_simple.AICoach(model="claude-opus")
    assert coach.provider == "anthropic"
    assert coach.model == ai_simple.MODEL_ALIASES["claude-opus"]
    assert "User's name: Pat" in coach._build_system_prompt(
        {"name": "Pat", "ctl": 1, "atl": 2, "tsb": 3, "activities_today": 4}
    )
    assert "very fatigued" in coach._build_user_prompt("msg", {"tsb": -30})
    assert "accumulating fatigue" in coach._build_user_prompt("msg", {"tsb": -11})
    assert "high intensity" in coach._build_user_prompt("msg", {"tsb": 30})
    assert coach._build_user_prompt("msg", {"tsb": 0}).startswith("User said")

    monkeypatch.setitem(
        __import__("sys").modules,
        "openai",
        SimpleNamespace(OpenAI=lambda api_key: (_ for _ in ()).throw(RuntimeError("bad"))),
    )
    coach = ai_simple.AICoach(api_key="x", provider="openai")
    assert coach._call_openai("s", "u") is None
    monkeypatch.setitem(
        __import__("sys").modules,
        "anthropic",
        SimpleNamespace(Anthropic=lambda api_key: (_ for _ in ()).throw(RuntimeError("bad"))),
    )
    coach = ai_simple.AICoach(api_key="x", provider="anthropic")
    assert coach._call_anthropic("s", "u") is None


def test_wizard_and_adapter_branches(monkeypatch, tmp_path, capsys):
    import garmin_coach.wizard as wizard
    import garmin_coach.adapters as adapters
    import garmin_coach.adapters.strava as strava

    inputs = iter(["x", "2"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    assert wizard.prompt_choice("Pick", ["a", "b"], default=0) == "b"

    num_inputs = iter(["", "99", "5"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(num_inputs))
    assert wizard.prompt_number("Count", default=3) == 3
    assert wizard.prompt_number("Count", min_val=1, max_val=10) == 5
    assert "at most 10" in capsys.readouterr().out
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert wizard.prompt_optional("Optional", default="x") == "x"

    nested = {"profile": {"name": "Pat"}}
    assert wizard._migrate_legacy_config(nested) is nested
    monkeypatch.setattr(wizard.os.path, "exists", lambda p: False)
    assert wizard.load_config() == {}
    monkeypatch.setattr(wizard.os.path, "exists", lambda p: True)
    monkeypatch.setattr(
        "builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bad"))
    )
    assert wizard.load_config() == {}

    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.adapters.garmin",
        SimpleNamespace(GarminAdapter="G"),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.adapters.strava",
        SimpleNamespace(StravaAdapter="S"),
    )
    monkeypatch.setitem(
        __import__("sys").modules, "garmin_coach.adapters.nike", SimpleNamespace(NikeAdapter="N")
    )
    assert adapters.GarminAdapter == "G"
    assert adapters.StravaAdapter == "S"
    assert adapters.NikeAdapter == "N"
    with pytest.raises(AttributeError):
        getattr(adapters, "MissingAdapter")

    assert adapters.DataSource.is_authenticated(object()) is None
    assert adapters.DataSource.authenticate(object(), {}) is None
    assert adapters.DataSource.get_profile(object()) is None
    assert adapters.DataSource.get_activities(object(), datetime.now()) is None
    assert adapters.DataSource.get_daily_summary(object(), datetime.now()) is None
    assert adapters.DataSource.get_time_series(object(), "ctl", datetime.now()) is None

    strava.STRAVA_CONFIG_DIR = str(tmp_path)
    adapter = strava.StravaAdapter()
    adapter._token = {"access_token": "tok"}
    monkeypatch.setattr(
        strava.requests,
        "get",
        lambda *args, **kwargs: SimpleNamespace(status_code=500, json=lambda: []),
    )
    assert adapter.get_activities(datetime(2026, 3, 28), datetime(2026, 3, 29)) == []

    page1 = [
        {
            "id": 1,
            "name": "Run",
            "type": "Ride",
            "start_date": "2026-03-29T07:00:00Z",
            "elapsed_time": 100,
            "distance": 1000,
            "average_speed": 2,
            "total_elevation_gain": 1,
        },
        {
            "id": 2,
            "name": "Run2",
            "type": "Run",
            "start_date": "2026-04-10T07:00:00Z",
            "elapsed_time": 100,
            "distance": 1000,
            "average_speed": 2,
            "total_elevation_gain": 1,
        },
        {
            "id": 3,
            "name": "Run3",
            "type": "Run",
            "start_date": "2026-03-29T07:00:00Z",
            "elapsed_time": 100,
            "distance": 1000,
            "average_speed": 2,
            "total_elevation_gain": 1,
        },
    ]
    responses = iter(
        [
            SimpleNamespace(status_code=200, json=lambda: page1),
            SimpleNamespace(status_code=200, json=lambda: []),
        ]
    )
    monkeypatch.setattr(strava.requests, "get", lambda *args, **kwargs: next(responses))
    acts = adapter.get_activities(datetime(2026, 3, 28), datetime(2026, 3, 29), sport_type="run")
    assert len(acts) == 1
    assert acts[0].activity_id == "3"

    monkeypatch.setattr(
        strava.requests, "get", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    assert adapter.get_activities(datetime(2026, 3, 28), datetime(2026, 3, 29)) == []

    adapter.get_daily_summary = lambda d: SimpleNamespace(tsb=1.0)
    data = adapter.get_time_series("tsb", datetime(2026, 3, 28), datetime(2026, 3, 29))
    assert len(data) == 2
