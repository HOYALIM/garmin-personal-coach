import runpy
from datetime import date
from types import SimpleNamespace

import pytest


def test_targeted_cleanup_branches(monkeypatch, capsys, tmp_path):
    import garmin_coach.adapters as adapters
    import garmin_coach.ai_coach as ai
    import garmin_coach.ai_simple as ai_simple
    import garmin_coach.cli as cli
    import garmin_coach.evening_checkin as evening
    import garmin_coach.final_check as final_check
    import garmin_coach.handler.intent as intent
    import garmin_coach.handler.templates as templates
    import garmin_coach.weekly_review as weekly
    import garmin_coach.wizard as wizard
    import garmin_coach.workout_review as workout_review

    with pytest.raises(ValueError):
        adapters.DataSourceFactory.create("missing")

    monkeypatch.setattr(ai.ProfileManager, "load", lambda self: None)
    engine = ai.AICoachEngine(
        config=__import__("garmin_coach.profile_manager", fromlist=["AICoachConfig"]).AICoachConfig(
            enabled=False
        )
    )
    ctx = ai.CoachContext(
        date="2026-03-29",
        user_profile=__import__(
            "garmin_coach.profile_manager", fromlist=["UserProfile", "ProfileData"]
        ).UserProfile(
            profile=__import__(
                "garmin_coach.profile_manager", fromlist=["ProfileData"]
            ).ProfileData(name="Pat")
        ),
        load_snapshot=__import__(
            "garmin_coach.training_load", fromlist=["LoadSnapshot", "FormCategory"]
        ).LoadSnapshot(
            ctl=10,
            atl=30,
            tsb=-30,
            form=__import__(
                "garmin_coach.training_load", fromlist=["FormCategory"]
            ).FormCategory.EXCESSIVE,
            date=date(2026, 3, 29),
        ),
    )
    assert "High fatigue" in engine._rule_advice(ctx)

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    coach = ai_simple.AICoach()
    assert coach.provider == "openai"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    coach = ai_simple.AICoach(api_key="x", provider="other")
    assert coach.generate_response("msg", {}) is None

    monkeypatch.setattr(
        cli,
        "check_for_updates",
        lambda force=False: SimpleNamespace(
            current="1.0.0", latest="1.0.0", url="u", is_update_available=False
        ),
    )
    monkeypatch.setattr("sys.argv", ["garmin-coach", "--check-updates"])
    assert cli.main() == 0
    assert "up to date" in capsys.readouterr().out.lower()
    monkeypatch.setattr(cli, "get_update_message", lambda info: "update-msg")
    monkeypatch.setattr("sys.argv", ["garmin-coach", "status"])
    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.handler",
        SimpleNamespace(process_message=lambda m: "ok"),
    )
    assert cli.main() == 0
    assert "update-msg" in capsys.readouterr().err

    assert intent.detect_intent("help me") == intent.Intent.ASK_HELP
    assert intent.detect_intent("nutrition plan") == intent.Intent.ASK_NUTRITION
    tpl = templates.ResponseTemplate("analytical")
    assert templates.get_form_description(20) == templates.FORM_DESCRIPTIONS["optimal"]
    assert templates.get_form_description(0) == templates.FORM_DESCRIPTIONS["optimal"]
    assert templates.get_form_description(-15) == templates.FORM_DESCRIPTIONS["tired"]

    class Bad:
        def __format__(self, spec):
            raise ValueError("bad")

    assert tpl.get("status", tsb=0, ctl=Bad(), atl=1).startswith("Training Stress Balance")

    monkeypatch.setattr(wizard.ProfileManager, "load", lambda self: object())
    monkeypatch.setattr(wizard, "prompt_non_empty", lambda p: "Pat")
    monkeypatch.setattr(wizard, "prompt_number", lambda *args, **kwargs: 30)
    monkeypatch.setattr(
        wizard, "prompt_choice", lambda prompt, options, default=0: options[default]
    )
    yn = iter([True, True, True, False])
    monkeypatch.setattr(wizard, "prompt_yes_no", lambda *args, **kwargs: next(yn))
    monkeypatch.setattr(wizard, "_check_garmin_connection", lambda: False)
    inputs = iter(["1 9", "bad-date", "06:00", "22:00", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    saved = []
    monkeypatch.setattr(wizard.ProfileManager, "save", lambda self, profile: saved.append(profile))
    wizard.run_wizard()
    out = capsys.readouterr().out
    assert "Updating configuration" in out
    assert "Invalid date format, skipping." in out
    assert "Garmin not connected" in out
    assert "Skipping AI setup" in out
    assert saved
    monkeypatch.setattr(wizard, "run_wizard", lambda: saved.append("main"))
    runpy.run_module("garmin_coach.wizard", run_name="__main__")
    assert saved[-1] == "main"

    monkeypatch.setattr(evening, "resume_garth", lambda: True)
    monkeypatch.setattr(evening, "ProfileManager", lambda: SimpleNamespace(exists=lambda: True))
    monkeypatch.setattr(
        evening,
        "TrainingLoadCalculator",
        lambda sex="male": SimpleNamespace(export_json=lambda: "{}"),
    )
    monkeypatch.setattr(evening, "build_evening_context", lambda *args: "ctx")
    monkeypatch.setattr(
        evening,
        "AICoachEngine",
        lambda: SimpleNamespace(
            daily_evening_advice=lambda ctx: SimpleNamespace(source="rule_based", text="ok"),
            format_message=lambda msg: msg.text,
        ),
    )
    monkeypatch.setattr(evening, "save_evening_data", lambda *args: None)

    class FakeEveningDate:
        @staticmethod
        def today():
            return date(2026, 3, 29)

    monkeypatch.setattr(evening, "date", FakeEveningDate)
    evening.DATA_DIR = tmp_path
    evening.run_evening(None, auto=True)
    monkeypatch.setattr("sys.argv", ["evening_checkin", "--auto"])
    monkeypatch.setattr(evening, "run_evening", lambda d, auto=False: saved.append((d, auto)))
    evening.main()
    assert saved[-1][1] is True

    monkeypatch.setattr("sys.argv", ["final_check", "--date", "2026-03-29", "--pain"])
    assert final_check.parse_args().pain is True
    runpy.run_module("garmin_coach.final_check", run_name="__main__")
    assert "FINAL CALL" in capsys.readouterr().out

    assert (
        workout_review.find_today_activity(
            [{"start_time": "2026-03-01T00:00:00+00:00"}], "2026-03-29"
        )
        is None
    )
    log = __import__("garmin_coach.models", fromlist=["WorkoutLog", "SubjectiveRating"]).WorkoutLog(
        date="2026-03-29",
        subjective=__import__(
            "garmin_coach.models", fromlist=["SubjectiveRating"]
        ).SubjectiveRating(energy=1, legs=2, mood=3),
    )
    assert "Energy: 1/5" in workout_review.build_md(log)
    runpy.run_module("garmin_coach.workout_review", run_name="__main__")
    assert "Coach note:" in capsys.readouterr().out

    class FakeWeeklyDate:
        @staticmethod
        def today():
            return date(2026, 3, 29)

        @staticmethod
        def fromisoformat(value: str):
            return date.fromisoformat(value)

    monkeypatch.setattr(weekly, "date", FakeWeeklyDate)
    monkeypatch.setattr(weekly, "resume_garth", lambda: True)
    monkeypatch.setattr(weekly, "ProfileManager", lambda: SimpleNamespace(exists=lambda: True))
    monkeypatch.setattr(
        weekly,
        "TrainingLoadCalculator",
        lambda sex="male": SimpleNamespace(export_json=lambda: "{}"),
    )
    monkeypatch.setattr(type(tmp_path / "training_load.json"), "exists", lambda self: False)
    monkeypatch.setattr(
        weekly,
        "get_week_stats",
        lambda ws, calc: {
            "week_start": ws.isoformat(),
            "session_count": 0,
            "total_hours": 0.0,
            "total_trimp": 0,
            "ctl_change": 0,
            "sport_breakdown": {},
        },
    )
    monkeypatch.setattr(weekly, "fetch_recent_activities", lambda *args: [])
    monkeypatch.setattr(weekly, "build_weekly_context", lambda *args: "ctx")
    monkeypatch.setattr(
        weekly,
        "AICoachEngine",
        lambda: SimpleNamespace(
            weekly_review_advice=lambda ctx: SimpleNamespace(text="ok", source="rule_based"),
            format_message=lambda msg: msg.text,
        ),
    )
    weekly.DATA_DIR = tmp_path
    weekly.run_weekly(None)
    monkeypatch.setattr("sys.argv", ["weekly_review", "--date", "2026-03-29"])
    called = []
    monkeypatch.setattr(weekly, "run_weekly", lambda target=None: called.append(target))
    weekly.main()
    assert called[-1] == date(2026, 3, 29)
