import json
import runpy
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_morning_checkin_helpers_and_main(monkeypatch, tmp_path, capsys):
    import garmin_coach.morning_checkin as morning

    data_dir = tmp_path / "data"
    snapshot_dir = data_dir / "snapshots"
    baseline_file = data_dir / "baseline.json"
    snapshot_dir.mkdir(parents=True)
    monkeypatch.setattr(morning, "DATA_DIR", data_dir)
    monkeypatch.setattr(morning, "SNAPSHOT_DIR", snapshot_dir)
    monkeypatch.setattr(morning, "BASELINE_FILE", baseline_file)

    morning.ensure_dirs()
    assert snapshot_dir.exists()
    assert morning.load_baseline() == {"rhr_history": []}

    baseline = {
        "rhr_history": [{"date": "2026-03-01", "value": 50}, {"date": "2026-03-02", "value": 55}]
    }
    updated = morning.update_baseline(baseline, 48, "2026-03-02")
    assert updated["rhr_history"][-1] == {"date": "2026-03-02", "value": 48}
    assert morning.compute_rhr_baseline(updated) == 49.0
    assert morning.compute_rhr_baseline({"rhr_history": [{"date": "x", "value": "bad"}]}) is None

    snapshot = {
        "status": "GREEN",
        "recommended_session": "5 km easy",
        "planned_session": "5 km easy",
    }
    result = SimpleNamespace(
        to_snapshot=lambda: snapshot,
        format_message=lambda: "morning ok",
    )

    monkeypatch.setattr(
        morning,
        "parse_args",
        lambda: SimpleNamespace(
            date="2026-03-29", soreness=2, pain=False, illness=False, phase="precheck"
        ),
    )
    monkeypatch.setattr(morning, "resume_garth", lambda: True)
    monkeypatch.setattr(
        morning,
        "fetch_morning_metrics",
        lambda target_date: {
            "sleep_hours": 7.5,
            "resting_hr": 48,
            "body_battery": 80,
            "training_readiness": 72,
            "hrv_status": "balanced",
        },
    )
    monkeypatch.setattr(morning, "get_planned_session", lambda target_date: (3, "5 km easy"))
    monkeypatch.setattr(morning, "evaluate", lambda **kwargs: result)

    morning.main()
    assert json.loads((snapshot_dir / "2026-03-29.json").read_text())["status"] == "GREEN"
    assert json.loads(baseline_file.read_text())["rhr_history"][-1]["value"] == 48
    assert "morning ok" in capsys.readouterr().out

    monkeypatch.setattr(morning, "resume_garth", lambda: False)
    with pytest.raises(SystemExit):
        morning.main()


def test_final_check_helpers_and_main(monkeypatch, tmp_path, capsys):
    import garmin_coach.final_check as final_check

    data_dir = tmp_path / "data"
    snapshot_dir = data_dir / "snapshots"
    baseline_file = data_dir / "baseline.json"
    snapshot_dir.mkdir(parents=True)
    monkeypatch.setattr(final_check, "DATA_DIR", data_dir)
    monkeypatch.setattr(final_check, "SNAPSHOT_DIR", snapshot_dir)
    monkeypatch.setattr(final_check, "BASELINE_FILE", baseline_file)

    final_check.ensure_dirs()
    assert final_check.load_baseline() == {"rhr_history": []}
    final_check.save_baseline({"rhr_history": []})
    assert baseline_file.exists()
    assert (
        final_check.compute_rhr_baseline(
            {"rhr_history": [{"date": "a", "value": 50}, {"date": "b", "value": 52}]}
        )
        == 51.0
    )

    result = SimpleNamespace(
        to_snapshot=lambda: {"status": "YELLOW"},
        format_message=lambda: "final ok",
    )
    monkeypatch.setattr(
        final_check,
        "parse_args",
        lambda: SimpleNamespace(date="2026-03-29", soreness=3, pain=True, illness=False),
    )
    monkeypatch.setattr(final_check, "resume_garth", lambda: True)
    monkeypatch.setattr(
        final_check,
        "fetch_morning_metrics",
        lambda target_date: {
            "sleep_hours": 6.0,
            "resting_hr": 51,
            "body_battery": 40,
            "training_readiness": 50,
            "hrv_status": "low",
        },
    )
    monkeypatch.setattr(final_check, "get_planned_session", lambda target_date: (4, "tempo"))
    monkeypatch.setattr(final_check, "evaluate", lambda **kwargs: result)

    final_check.main()
    assert json.loads((snapshot_dir / "2026-03-29.json").read_text())["status"] == "YELLOW"
    assert "final ok" in capsys.readouterr().out

    monkeypatch.setattr(final_check, "resume_garth", lambda: False)
    with pytest.raises(SystemExit):
        final_check.main()


def test_evening_checkin_paths(monkeypatch, tmp_path, capsys):
    import garmin_coach.evening_checkin as evening

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    evening_data = data_dir / "evening_data"
    monkeypatch.setattr(evening, "DATA_DIR", data_dir)
    monkeypatch.setattr(evening, "EVENING_DATA", evening_data)

    inputs = iter(["", "3", "x", "4", "5", "7.0", "notes", "2", "y", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    report = evening.ask_self_report()
    assert report["energy"] == 3
    assert report["legs"] == 3
    assert report["mood"] == 4
    assert report["pain"] is True
    assert report["supplements"] is False

    saved = evening.save_evening_data("2026-03-29", {"energy": 3})
    assert saved.exists()
    assert json.loads(saved.read_text())["self_report"]["energy"] == 3

    fake_profile = SimpleNamespace(profile=SimpleNamespace(name="Pat"))
    fake_pm = SimpleNamespace(
        load=lambda: fake_profile, calculate_all_zones=lambda profile: {"z2": [1, 2]}
    )
    fake_calc = SimpleNamespace(
        get_snapshot=lambda target: SimpleNamespace(to_dict=lambda: {"tsb": 5})
    )
    monkeypatch.setattr(evening, "get_week_number", lambda target_date: 5)
    monkeypatch.setattr(
        evening,
        "get_planned_session",
        lambda target_date: (5, "easy") if target_date == "2026-03-29" else (6, "rest"),
    )
    monkeypatch.setattr(evening, "get_week_brief", lambda week: "base build")
    monkeypatch.setattr(
        evening,
        "fetch_recent_activities",
        lambda start, end: [SimpleNamespace(to_dict=lambda: {"sport": "running"})],
    )
    ctx = evening.build_evening_context("2026-03-29", {"energy": 3}, fake_pm, fake_calc)
    assert ctx.week_number == 5
    assert ctx.upcoming_session["session"] == (6, "rest")

    missing_pm = SimpleNamespace(load=lambda: None)
    with pytest.raises(RuntimeError):
        evening.build_evening_context("2026-03-29", {}, missing_pm, fake_calc)

    monkeypatch.setattr(evening, "resume_garth", lambda: True)
    monkeypatch.setattr(evening, "ProfileManager", lambda: SimpleNamespace(exists=lambda: True))
    monkeypatch.setattr(
        evening,
        "TrainingLoadCalculator",
        lambda sex="male": SimpleNamespace(export_json=lambda: "{}"),
    )
    monkeypatch.setattr(
        evening, "build_evening_context", lambda target_date, self_reported, pm, calc: "ctx"
    )
    monkeypatch.setattr(
        evening,
        "AICoachEngine",
        lambda: SimpleNamespace(
            daily_evening_advice=lambda ctx: SimpleNamespace(source="rule_based", text="night"),
            format_message=lambda msg: f"FMT {msg.text}",
        ),
    )
    monkeypatch.setattr(evening, "ask_self_report", lambda: {"energy": 4})
    evening.run_evening("2026-03-29", auto=False)
    out = capsys.readouterr().out
    assert "FMT night" in out
    assert (data_dir / "training_load.json").exists()

    monkeypatch.setattr(evening, "ProfileManager", lambda: SimpleNamespace(exists=lambda: False))
    evening.run_evening("2026-03-29", auto=True)
    assert "No profile found" in capsys.readouterr().out


def test_setup_wizard_helpers_and_run(monkeypatch, tmp_path, capsys):
    import garmin_coach.setup_wizard as setup_wizard

    responses = iter(["", "Pat"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    assert setup_wizard.ask("Name", "Pat") == "Pat"
    assert setup_wizard.ask("Name") == "Pat"

    int_inputs = iter(["bad", "9", "30"])
    monkeypatch.setattr(setup_wizard, "ask", lambda prompt, default="": next(int_inputs))
    assert setup_wizard.ask_int("Age", 20, 10, 100) == 30

    float_inputs = iter(["bad", "500", "70.5"])
    monkeypatch.setattr(setup_wizard, "ask", lambda prompt, default="": next(float_inputs))
    assert setup_wizard.ask_float("Weight", 70.0, 30.0, 200.0) == 70.5

    monkeypatch.setattr(setup_wizard, "ask", lambda prompt, default="": "yes")
    assert setup_wizard.ask_bool("AI", False) is True

    choice_inputs = iter(["9", "2"])
    monkeypatch.setattr(setup_wizard, "ask", lambda prompt, default="": next(choice_inputs))
    assert setup_wizard.ask_choice("Tone", ["a", "b"], default_idx=0) == "b"

    multi_inputs = iter(["x", "1,3"])
    monkeypatch.setattr(setup_wizard, "ask", lambda prompt, default="": next(multi_inputs))
    assert setup_wizard.ask_multi_choice("Sports", ["running", "cycling", "swimming"]) == [
        "running",
        "swimming",
    ]

    monkeypatch.setattr(
        setup_wizard.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0)
    )
    assert setup_wizard.test_garth_login("a@example.com") is True
    monkeypatch.setattr(
        setup_wizard.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    )
    assert setup_wizard.test_garth_login("a@example.com") is False

    answers = iter(
        [
            "Pat",
            "30",
            "1",
            "175",
            "70",
            "1,2",
            "1",
            "Goal Race",
            "2026-10-10",
            "2",
            "5",
            "10",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "50",
            "190",
            "0",
            "unknown",
            "y",
            "y",
            "y",
            "n",
            "pat@example.com",
            "y",
            "y",
            "06:00",
            "y",
            "06:30",
            "y",
            "22:00",
            "y",
            "7",
            "21:00",
            "y",
            "2",
            "1",
            "y",
            "1",
            "room-1",
        ]
    )
    monkeypatch.setattr(setup_wizard, "ask", lambda prompt, default="": next(answers))
    monkeypatch.setattr(setup_wizard, "test_garth_login", lambda email: True)
    saved = {}
    monkeypatch.setattr(
        setup_wizard,
        "ProfileManager",
        lambda: SimpleNamespace(
            validate=lambda profile: [],
            save=lambda profile: saved.setdefault("profile", profile),
            config_path=tmp_path / "config.yaml",
        ),
    )

    profile = setup_wizard.run()
    assert profile.profile.name == "Pat"
    assert profile.garmin.connected is True
    assert saved["profile"].ai_coach.notification_target == "room-1"
    assert "Profile saved" in capsys.readouterr().out


def test_wizard_validation_and_config(monkeypatch, tmp_path, capsys):
    import garmin_coach.wizard as wizard
    import garmin_coach.wizard.validation as validation

    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    monkeypatch.setattr(wizard, "CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(wizard, "CONFIG_FILE", str(config_file))

    responses = iter(["", "Pat"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    assert wizard.prompt_non_empty("Name: ") == "Pat"

    yn = iter(["maybe", "", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(yn))
    assert wizard.prompt_yes_no("Continue", default=False) is False
    assert wizard.prompt_yes_no("Continue", default=False) is True

    choice = iter(["9", "", "2"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(choice))
    assert wizard.prompt_choice("Sport", ["running", "cycling"], default=0) == "running"
    assert wizard.prompt_choice("Sport", ["running", "cycling"], default=0) == "cycling"

    num = iter(["bad", "5", "15"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(num))
    assert wizard.prompt_number("Age", min_val=10, max_val=20, default=None) == 15

    opt = iter(["", "value"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(opt))
    assert wizard.prompt_optional("Optional", default="x") == "x"
    assert wizard.prompt_optional("Optional", default="x") == "value"

    monkeypatch.setitem(
        __import__("sys").modules,
        "garth",
        SimpleNamespace(
            resume=lambda home: True, connectapi=lambda path, max_retries=1: {"ok": True}
        ),
    )
    assert wizard._check_garmin_connection() is True
    monkeypatch.setitem(
        __import__("sys").modules,
        "garth",
        SimpleNamespace(resume=lambda home: (_ for _ in ()).throw(RuntimeError("nope"))),
    )
    assert wizard._check_garmin_connection() is False

    legacy = {
        "name": "Pat",
        "age": 30,
        "sports": ["running"],
        "garmin_connected": True,
        "ai": {"enabled": True},
    }
    migrated = wizard._migrate_legacy_config(legacy)
    assert migrated["profile"]["name"] == "Pat"
    assert migrated["garmin"]["connected"] is True

    config_file.write_text("name: Pat\nage: 30\nsports:\n  - running\n")
    loaded = wizard.load_config()
    assert loaded["profile"]["name"] == "Pat"

    wizard.save_config({"profile": {"name": "Pat"}})
    assert config_file.exists()
    assert oct(config_file.stat().st_mode & 0o777) == "0o600"

    monkeypatch.setattr(
        wizard,
        "ProfileManager",
        lambda: SimpleNamespace(load=lambda: None, save=lambda profile: saved.append(profile)),
    )
    monkeypatch.setattr(wizard, "_check_garmin_connection", lambda: True)
    inputs = iter(
        [
            "Pat",
            "30",
            "1",
            "175",
            "70",
            "1 2",
            "Race",
            "2026-10-10",
            "2",
            "4",
            "06:00",
            "22:00",
            "y",
            "n",
            "y",
            "y",
            "token",
            "2",
            "3",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    saved = []
    wizard.run_wizard()
    assert saved[0].profile.name == "Pat"
    assert "Setup Complete" in capsys.readouterr().out

    assert validation.validate_age(9)[0] is False
    assert validation.validate_weight("x")[0] is False
    assert validation.validate_height(180)[0] is True
    assert validation.validate_max_hr(300)[0] is False
    assert validation.validate_resting_hr(50)[0] is True
    assert validation.validate_ftp(250)[0] is True
    assert validation.validate_training_days(8)[0] is False
    assert validation.validate_name("")[0] is False
    assert validation.validate_sports(["running", "cycling"])[0] is True
    ok, errors = validation.validate_profile(
        {
            "name": "Pat",
            "age": 30,
            "weight_kg": 70,
            "height_cm": 175,
            "max_heart_rate": 190,
            "resting_heart_rate": 50,
            "ftp": 200,
            "training_days_per_week": 4,
            "sports": ["running"],
        }
    )
    assert ok is True and errors == []
    assert validation.calculate_max_hr(30) == 190
    assert validation.calculate_target_hr(30, 50)["zone5"][1] == 190


def test_wizard_main_entry(monkeypatch):
    called = []
    monkeypatch.setattr("garmin_coach.wizard.run_wizard", lambda: called.append(True))
    runpy.run_module("garmin_coach.wizard.__main__", run_name="__main__")
    assert called == [True]
