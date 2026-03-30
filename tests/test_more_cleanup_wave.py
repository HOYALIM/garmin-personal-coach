import runpy
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_more_cleanup_wave(monkeypatch, capsys, tmp_path):
    import garmin_coach.evening_checkin as evening
    import garmin_coach.handler as handler
    import garmin_coach.logging_config as logging_config
    import garmin_coach.setup_wizard as setup_wizard
    import garmin_coach.workout_review as workout_review

    calc_file = tmp_path / "training_load.json"
    calc_file.write_text("{}")
    monkeypatch.setattr(evening, "DATA_DIR", tmp_path)
    monkeypatch.setattr(evening, "resume_garth", lambda: True)
    monkeypatch.setattr(evening, "ProfileManager", lambda: SimpleNamespace(exists=lambda: True))
    monkeypatch.setattr(evening, "save_evening_data", lambda *args: None)
    loaded = []

    class FakeCalc:
        def __init__(self, sex="male"):
            self.sex = sex

        def export_json(self):
            return "{}"

        @staticmethod
        def from_json(path):
            loaded.append(path)
            return SimpleNamespace(export_json=lambda: "{}")

    monkeypatch.setattr(evening, "TrainingLoadCalculator", FakeCalc)
    monkeypatch.setattr(evening, "build_evening_context", lambda *args: "ctx")
    monkeypatch.setattr(
        evening,
        "AICoachEngine",
        lambda: SimpleNamespace(
            daily_evening_advice=lambda ctx: SimpleNamespace(text="ok", source="rule_based"),
            format_message=lambda msg: msg.text,
        ),
    )
    evening.run_evening("2026-03-29", auto=True)
    assert loaded and loaded[0] == calc_file
    monkeypatch.setattr("sys.argv", ["evening_checkin", "--auto"])
    runpy.run_module("garmin_coach.evening_checkin", run_name="__main__")
    assert "No profile found" in capsys.readouterr().out

    assert "Good session" in handler.MessageHandler(
        config={}, user_context={}
    )._handle_workout_complete({"tsb": -20})
    assert "Keep building" in handler.MessageHandler(
        config={}, user_context={}
    )._handle_workout_complete({"tsb": 0})
    assert "Rest day" in handler.MessageHandler(config={}, user_context={})._handle_ask_plan(
        {"has_data": True, "tsb": -30}
    )
    assert "active recovery" in handler.MessageHandler(config={}, user_context={})._handle_ask_plan(
        {"has_data": True, "tsb": -15}
    )
    assert "Building base fitness" in handler.MessageHandler(
        config={}, user_context={}
    )._handle_ask_nutrition({"ctl": 5})

    class FakeLogfire:
        def __init__(self):
            self.calls = []

        def configure(self, **kwargs):
            self.calls.append(("configure", kwargs))

        def info(self, message, **context):
            self.calls.append(("info", message, context))

        def warning(self, message, **context):
            self.calls.append(("warning", message, context))

        def error(self, message, **context):
            self.calls.append(("error", message, context))

        def debug(self, message, **context):
            self.calls.append(("debug", message, context))

    fake_logfire = FakeLogfire()
    monkeypatch.setattr(logging_config, "_logfire_module", fake_logfire)
    monkeypatch.setenv("LOGFIRE_TOKEN", "tok")
    logging_config._configure_logfire()
    logging_config._emit_to_logfire("info", "hello", x=1)
    assert fake_logfire.calls[0][0] == "configure"
    assert fake_logfire.calls[1][0] == "info"

    ask_values = iter(
        [
            "Pat",
            "Race",
            "2026-10-10",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "pat@example.com",
            "06:00",
            "06:30",
            "22:00",
            "21:00",
            "room",
        ]
    )
    monkeypatch.setattr(setup_wizard, "ask", lambda prompt, default="": next(ask_values))
    monkeypatch.setattr(
        setup_wizard,
        "ask_int",
        lambda prompt, default, lo, hi: 30
        if "Age" in prompt
        else 50
        if "Resting HR" in prompt
        else 190
        if "Max HR" in prompt
        else 0
        if "FTP" in prompt
        else 5,
    )
    monkeypatch.setattr(
        setup_wizard,
        "ask_float",
        lambda prompt, default, lo, hi: 175.0
        if "Height" in prompt
        else 70.0
        if "Weight" in prompt
        else 10.0,
    )
    monkeypatch.setattr(setup_wizard, "ask_multi_choice", lambda *args, **kwargs: ["running"])
    monkeypatch.setattr(
        setup_wizard,
        "ask_choice",
        lambda prompt, options, default_idx=0: options[0 if len(options) == 1 else default_idx],
    )
    monkeypatch.setattr(setup_wizard, "ask_bool", lambda *args, **kwargs: False)
    monkeypatch.setattr(setup_wizard, "test_garth_login", lambda email: False)
    monkeypatch.setattr(
        setup_wizard,
        "ProfileManager",
        lambda: SimpleNamespace(
            validate=lambda profile: ["bad"],
            save=lambda profile: None,
            config_path=tmp_path / "config.yaml",
        ),
    )
    with pytest.raises(SystemExit):
        setup_wizard.run()
    out = capsys.readouterr().out
    assert "garth not logged in yet" in out
    assert "Validation warnings" in out
    assert "Aborted." in out

    assert (
        workout_review.find_today_activity(
            [{"start_time": ""}, {"start_time": date.today().isoformat()}], "2026-03-29"
        )
        is None
    )
    start = "2999-01-01T00:00:00+00:00"
    assert workout_review.find_today_activity([{"start_time": start}], "2026-03-29") == {
        "start_time": start
    }
