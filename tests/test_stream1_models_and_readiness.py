from datetime import date, timedelta


def test_models_package_compatibility_imports_and_safe_auth_serialization():
    import garmin_coach.models as models

    profile = models.UserProfile(
        garmin_credentials=models.GarminAuth(email="runner@example.com", connected=True),
        birth_date=date(1990, 1, 1),
        sex="male",
        height_cm=175,
        weight_kg=70,
        goal=models.TrainingGoal(type="marathon", weekly_volume_km=50),
        fitness_level=models.FitnessLevel(level="advanced"),
        strava_auth=models.StravaAuth(athlete_id="123", connected=True, scopes=["read"]),
    )

    safe = profile.to_safe_dict()
    assert models.MorningMetrics
    assert models.SessionFeedback
    assert "password" not in str(safe)
    assert "access_token" not in str(safe)
    assert safe["garmin_credentials"]["connected"] is True


def test_readiness_reweights_missing_components_and_uses_stable_keys():
    from garmin_coach.engine.readiness import ReadinessCalculator
    from garmin_coach.models import BodyBatteryData, HealthMetrics, RHRData, SleepData, TrainingLoad

    metrics = HealthMetrics(
        metric_date=date(2026, 4, 6),
        sleep=SleepData(score=80),
        body_battery=BodyBatteryData(morning_value=70),
        rhr=RHRData(value_bpm=48, baseline_bpm=50, deviation_bpm=-2),
        training_load=TrainingLoad(tsb=5),
    )
    readiness = ReadinessCalculator().calculate(metrics, available_days=7)
    assert readiness.confidence == "low"
    assert readiness.score > 0
    assert abs(sum(readiness.component_weights.values()) - 1.0) < 0.01
    assert "hrv_deviation_pct" not in readiness.components or isinstance(
        readiness.components.get("hrv_deviation_pct"), float
    )
    assert "rhr" in readiness.component_weights


def test_typed_feedback_contract_round_trip_and_planner_uses_feedback():
    from garmin_coach.engine.training_plan import WeeklyTrainingPlanner
    from garmin_coach.models import (
        FeedbackCompletion,
        FitnessLevel,
        GarminAuth,
        PainReport,
        ReadinessScore,
        SessionFeedback,
        TrainingGoal,
        TrainingLoad,
        UserProfile,
    )

    feedback = SessionFeedback(
        session_date="2026-04-06",
        completion=FeedbackCompletion.NONE,
        rpe=9,
        pain_report=PainReport(body_part="knee", severity="moderate"),
        flagged_for_review=True,
    )
    rebuilt = SessionFeedback.from_dict(feedback.to_dict())
    assert rebuilt.completion == FeedbackCompletion.NONE
    assert rebuilt.pain_report and rebuilt.pain_report.body_part == "knee"

    user = UserProfile(
        garmin_credentials=GarminAuth(email="runner@example.com", connected=True),
        birth_date=date.today() - timedelta(days=30 * 365),
        sex="male",
        height_cm=175,
        weight_kg=70,
        goal=TrainingGoal(type="marathon", weekly_volume_km=60),
        fitness_level=FitnessLevel(level="advanced"),
    )
    conservative = WeeklyTrainingPlanner().generate(
        user,
        TrainingLoad(ctl=40),
        [ReadinessScore(score=60, level="yellow")],
        [feedback],
        start_date=date(2026, 4, 7),
    )
    neutral = WeeklyTrainingPlanner().generate(
        user,
        TrainingLoad(ctl=40),
        [ReadinessScore(score=60, level="yellow")],
        [],
        start_date=date(2026, 4, 7),
    )
    assert conservative.total_tss < neutral.total_tss
