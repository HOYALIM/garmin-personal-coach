def test_auth_redaction_recurses_through_nested_collections():
    from garmin_coach.adapters.garmin.auth import redact_sensitive_fields, validate_auth_input

    redacted = redact_sensitive_fields(
        {
            "email": "runner@example.com",
            "items": [{"refresh_token": "tok"}, {"nested": [{"password": "pw"}]}],
        }
    )
    assert redacted["items"][0]["refresh_token"] == "***REDACTED***"
    assert redacted["items"][1]["nested"][0]["password"] == "***REDACTED***"
    assert validate_auth_input({"email": "runner@example.com", "password": "pw"}) == (
        "runner@example.com",
        "pw",
    )


def test_invalid_training_effect_parsing_returns_none():
    from garmin_coach.adapters.garmin.activity import extract_training_effect

    aerobic, anaerobic = extract_training_effect(
        {"aerobicTrainingEffect": "MAINTAINING", "anaerobicTrainingEffect": 8.4}
    )
    assert aerobic is None
    assert anaerobic is None


def test_training_readiness_parser_preserves_extended_fields():
    from garmin_coach.adapters.garmin.health import parse_training_readiness

    parsed = parse_training_readiness(
        {
            "trainingReadinessScore": 81,
            "recoveryHours": 18,
            "acuteLoad": 540,
            "loadBalance": "productive",
            "sleepContribution": 22,
            "hrvContribution": 19,
        }
    )
    assert parsed and parsed.score == 81
    assert parsed.recovery_time_hours == 18
    assert parsed.load_balance == "productive"


def test_engine_interface_uses_typed_feedback_history():
    from garmin_coach.engine.interfaces import CoachingEngine

    annotations = CoachingEngine.generate_weekly_plan.__annotations__
    assert "SessionFeedback" in str(annotations["feedback_history"])
