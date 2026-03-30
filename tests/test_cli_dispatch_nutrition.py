import json
from datetime import date, datetime
from types import SimpleNamespace


def test_nutrition_module_and_recommendations():
    from garmin_coach.nutrition import (
        calculate_activity_calories,
        calculate_basal_metabolic_rate,
        calculate_hydration,
        calculate_macros,
        calculate_nutrition_targets,
        calculate_total_daily_energy_expenditure,
        recommend_post_workout,
        recommend_pre_workout,
    )

    bmr = calculate_basal_metabolic_rate(70, 175, 30, "male")
    tdee = calculate_total_daily_energy_expenditure(bmr, "active")
    activity = calculate_activity_calories("running", 60, 70)
    carbs, protein, fat = calculate_macros(2500, "running", 60)
    hydration = calculate_hydration(70, 60, "high")
    targets = calculate_nutrition_targets(70, 175, 30, "male", "running", 60)

    assert bmr > 0
    assert tdee > bmr
    assert activity > 0
    assert carbs > 0 and protein > 0 and fat >= 20
    assert hydration > 0
    assert targets.calories > 0
    assert recommend_pre_workout("running", 60)["timing"]
    assert recommend_post_workout("running", 60)["protein"]


def test_hydration_module(monkeypatch, tmp_path):
    import garmin_coach.nutrition.hydration as hydration

    hydration_file = tmp_path / "hydration.json"
    monkeypatch.setattr(hydration, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(hydration, "HYDRATION_FILE", str(hydration_file))

    now = datetime(2026, 3, 29, 9, 0, 0)

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(hydration, "datetime", FakeDateTime)

    hydration.log_water(500, now)
    hydration.log_water(750, now)
    assert hydration.get_today_intake() == 1250
    assert hydration.get_daily_intake(now) == 1250
    assert hydration.check_hydration_status(2000) in {"half_way", "almost_there"}
    summary = hydration.get_hydration_summary(2000)
    assert summary["today_ml"] == 1250
    assert summary["percentage"] == 62.5
    hydration.reset_daily()
    assert hydration.get_today_intake() == 0


def test_cli_main_and_commands(monkeypatch, capsys):
    import garmin_coach.cli as cli

    monkeypatch.setattr(
        cli,
        "check_for_updates",
        lambda force=False: SimpleNamespace(
            current="0.1.0", latest="0.2.0", url="https://example", is_update_available=True
        ),
    )
    monkeypatch.setattr(cli, "get_update_message", lambda info: "update available")

    monkeypatch.setattr("sys.argv", ["garmin-coach", "--version"])
    assert cli.main() == 0
    assert "garmin-personal-coach" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["garmin-coach", "--check-updates"])
    assert cli.main() == 0
    assert "Update available" in capsys.readouterr().out

    monkeypatch.setattr(
        "garmin_coach.handler.process_message", lambda message: f"handled:{message}"
    )
    monkeypatch.setattr("sys.argv", ["garmin-coach", "status", "--no-update-check"])
    assert cli.main() == 0
    assert "handled:" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["garmin-coach", "unknown", "--no-update-check"])
    assert cli.main() == 1


def test_dispatch_main_and_subcommands(monkeypatch):
    import garmin_coach.dispatch as dispatch

    calls = []
    monkeypatch.setattr(dispatch, "run_precheck", lambda d: calls.append(("precheck", d)) or 0)
    monkeypatch.setattr(dispatch, "run_final_check", lambda d: calls.append(("final", d)) or 0)
    monkeypatch.setattr(dispatch, "run_workout_review", lambda d: calls.append(("workout", d)) or 0)

    for args in [
        SimpleNamespace(precheck=True, final=False, workout=False, message="", date="2026-03-29"),
        SimpleNamespace(precheck=False, final=True, workout=False, message="", date="2026-03-29"),
        SimpleNamespace(precheck=False, final=False, workout=True, message="", date="2026-03-29"),
    ]:
        monkeypatch.setattr(dispatch, "parse_args", lambda args=args: args)
        try:
            dispatch.main()
        except SystemExit as exc:
            assert exc.code == 0

    trigger = SimpleNamespace(trigger_type=SimpleNamespace(WAKE=None))
    monkeypatch.setattr(
        "garmin_coach.triggers.detect_trigger",
        lambda message: SimpleNamespace(
            trigger_type=__import__(
                "garmin_coach.triggers", fromlist=["TriggerType"]
            ).TriggerType.WORKOUT_COMPLETE
        ),
    )
    monkeypatch.setattr(
        dispatch,
        "parse_args",
        lambda: SimpleNamespace(
            precheck=False, final=False, workout=False, message="운동 끝", date="2026-03-29"
        ),
    )
    try:
        dispatch.main()
    except SystemExit as exc:
        assert exc.code == 0

    assert calls[0] == ("precheck", "2026-03-29")
    assert calls[1] == ("final", "2026-03-29")
    assert calls[2] == ("workout", "2026-03-29")
    assert calls[3] == ("workout", "2026-03-29")


def test_weekly_review_flow(monkeypatch, tmp_path, capsys):
    import garmin_coach.weekly_review as weekly_review
    from garmin_coach.profile_manager import ProfileData, UserProfile
    from garmin_coach.training_load import TrainingLoadCalculator, Sport

    calc = TrainingLoadCalculator(sex="male")
    monday = date(2026, 3, 23)
    for i in range(3):
        calc.add_session(monday, 50 + i, Sport.RUNNING, 45, f"run {i}")

    profile = UserProfile(profile=ProfileData(name="Pat", goal_date="2026-04-30"))
    monkeypatch.setattr(weekly_review, "resume_garth", lambda: True)
    monkeypatch.setattr(weekly_review.ProfileManager, "exists", lambda self: True)
    monkeypatch.setattr(weekly_review.ProfileManager, "load", lambda self: profile)
    monkeypatch.setattr(
        weekly_review.ProfileManager, "calculate_all_zones", lambda self, profile: None
    )
    monkeypatch.setattr(
        weekly_review, "fetch_recent_activities", lambda *args, **kwargs: [{"type": "run"}]
    )
    monkeypatch.setattr(
        weekly_review.AICoachEngine,
        "weekly_review_advice",
        lambda self, ctx: SimpleNamespace(source="rule_based", text="weekly ok"),
    )
    monkeypatch.setattr(
        weekly_review.AICoachEngine, "format_message", lambda self, msg: f"fmt:{msg.text}"
    )
    monkeypatch.setattr(weekly_review, "DATA_DIR", tmp_path)
    (tmp_path / "training_load.json").write_text(calc.export_json())

    weekly_review.run_weekly(monday)
    out = capsys.readouterr().out
    assert "Weekly Summary" in out
    assert "fmt:weekly ok" in out
    assert weekly_review.get_week_start(date(2026, 3, 29)) == monday
