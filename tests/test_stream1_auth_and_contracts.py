from datetime import date, timedelta


def test_auth_redaction_and_transient_login_input():
    from garmin_coach.adapters.garmin.auth import redact_sensitive_fields, validate_auth_input

    redacted = redact_sensitive_fields(
        {"email": "runner@example.com", "password": "pw", "nested": {"refresh_token": "tok"}}
    )
    assert redacted["password"] == "***REDACTED***"
    assert redacted["nested"]["refresh_token"] == "***REDACTED***"
    assert validate_auth_input({"email": "runner@example.com", "password": "pw"}) == (
        "runner@example.com",
        "pw",
    )


def test_auth_redaction_recurses_into_lists():
    from garmin_coach.adapters.garmin.auth import redact_sensitive_fields

    redacted = redact_sensitive_fields(
        {
            "items": [
                {"refresh_token": "tok"},
                {"nested": [{"password": "pw"}]},
            ]
        }
    )
    assert redacted["items"][0]["refresh_token"] == "***REDACTED***"
    assert redacted["items"][1]["nested"][0]["password"] == "***REDACTED***"


def test_invalid_training_effect_parsing_returns_none():
    from garmin_coach.adapters.garmin.activity import extract_training_effect

    aerobic, anaerobic = extract_training_effect(
        {"aerobicTrainingEffect": "MAINTAINING", "anaerobicTrainingEffect": 7.4}
    )
    assert aerobic is None
    assert anaerobic is None


def test_engine_interfaces_expose_typed_feedback_history():
    from garmin_coach.engine.interfaces import CoachingEngine

    annotations = CoachingEngine.generate_weekly_plan.__annotations__
    assert "SessionFeedback" in str(annotations["feedback_history"])


def test_reporting_contracts_serialize_cleanly():
    from garmin_coach.models import (
        WeeklyRecoverySummary,
        WeeklyReport,
        WeeklyReportSummary,
        WeeklyTrainingLoadSummary,
    )

    report = WeeklyReport(
        period="2026-04-01~2026-04-07",
        summary=WeeklyReportSummary(sessions=5, total_distance_km=42.2),
        training_load=WeeklyTrainingLoadSummary(ctl=40, atl=38, tsb=2, ramp_rate=3),
        recovery=WeeklyRecoverySummary(avg_sleep="7h 20m", avg_sleep_score=78),
        coach_comment="좋은 주였습니다.",
    )
    payload = report.to_dict()
    assert payload["summary"]["sessions"] == 5
    assert payload["training_load"]["ctl"] == 40


def test_safe_profile_serialization_has_no_secret_fields():
    from garmin_coach.models import FitnessLevel, GarminAuth, TrainingGoal, UserProfile

    profile = UserProfile(
        garmin_credentials=GarminAuth(email="runner@example.com", connected=True),
        birth_date=date.today() - timedelta(days=30 * 365),
        sex="male",
        height_cm=175,
        weight_kg=70,
        goal=TrainingGoal(type="marathon", weekly_volume_km=50),
        fitness_level=FitnessLevel(level="advanced"),
    )
    payload = profile.to_safe_dict()
    assert "password" not in str(payload)
    assert payload["garmin_credentials"]["email"] == "runner@example.com"
