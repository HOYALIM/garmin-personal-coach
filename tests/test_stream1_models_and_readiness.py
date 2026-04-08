from datetime import date, timedelta


def test_readiness_prefers_training_readiness_and_tracks_inputs():
    from garmin_coach.engine.readiness import ReadinessCalculator
    from garmin_coach.models import (
        BodyBatteryData,
        HRVData,
        HealthMetrics,
        RHRData,
        SleepData,
        TrainingLoad,
        TrainingReadinessData,
    )

    metrics = HealthMetrics(
        metric_date=date(2026, 4, 6),
        sleep=SleepData(score=78),
        hrv=HRVData(deviation_pct=-4),
        body_battery=BodyBatteryData(morning_value=72),
        rhr=RHRData(value_bpm=49, baseline_bpm=50, deviation_bpm=-1),
        training_readiness=TrainingReadinessData(score=82, level="green"),
        training_load=TrainingLoad(tsb=4),
    )
    readiness = ReadinessCalculator().calculate(metrics, available_days=10)
    assert readiness.score >= 70
    assert readiness.confidence == "high"
    assert readiness.input_snapshot["garmin_training_readiness"] == 82
    assert "garmin_training_readiness" in readiness.components


def test_readiness_limiting_factors_and_medium_confidence():
    from garmin_coach.engine.readiness import ReadinessCalculator
    from garmin_coach.models import BodyBatteryData, HRVData, HealthMetrics, SleepData, TrainingLoad

    metrics = HealthMetrics(
        metric_date=date(2026, 4, 6),
        sleep=SleepData(score=52),
        hrv=HRVData(deviation_pct=-18),
        body_battery=BodyBatteryData(morning_value=35),
        training_load=TrainingLoad(tsb=-18),
    )
    readiness = ReadinessCalculator().calculate(metrics, available_days=3)
    assert readiness.confidence == "medium"
    assert "sleep" in readiness.limiting_factors
    assert "hrv" in readiness.limiting_factors
    assert "fatigue" in readiness.limiting_factors


def test_coaching_and_weekly_plan_contracts_include_new_fields():
    from garmin_coach.models import DayPlan, SessionType, WeeklyPlan, WorkoutAnalysis

    day = DayPlan(
        date="2026-04-07",
        session_type=SessionType.EASY,
        description="easy run",
        target_tss=42,
        rationale="Recent readiness trend requires conservative load management.",
    )
    plan = WeeklyPlan(days=[day], total_tss=42, notes=["note"], focus="recovery_first")
    analysis = WorkoutAnalysis(
        summary="summary",
        coaching_notes=["note"],
        recovery_recommendation="Recover well.",
    )
    plan_payload = plan.to_dict()
    analysis_payload = analysis.to_dict()
    assert plan_payload["focus"] == "recovery_first"
    assert isinstance(plan_payload["days"], list)
    assert plan_payload["days"][0]["rationale"]
    assert analysis_payload["recovery_recommendation"] == "Recover well."


def test_safe_profile_serialization_excludes_secret_fields():
    from garmin_coach.models import FitnessLevel, GarminAuth, TrainingGoal, UserProfile

    profile = UserProfile(
        garmin_credentials=GarminAuth(email="runner@example.com", connected=True),
        birth_date=date.today() - timedelta(days=30 * 365),
        sex="male",
        height_cm=175,
        weight_kg=70,
        goal=TrainingGoal(type="marathon", weekly_volume_km=60),
        fitness_level=FitnessLevel(level="advanced"),
    )
    payload = profile.to_safe_dict()
    assert "password" not in str(payload)
    assert payload["garmin_credentials"]["connected"] is True


def test_answer_question_is_guardrailed_when_context_metrics_show_risk():
    import asyncio

    from garmin_coach.engine.coaching import GarminCoachingEngine
    from garmin_coach.engine.interfaces import CoachingContext
    from garmin_coach.models import (
        BodyBatteryData,
        FitnessLevel,
        GarminAuth,
        HealthMetrics,
        HRVData,
        ReadinessScore,
        RHRData,
        SleepData,
        TrainingGoal,
        TrainingLoad,
        UserProfile,
    )

    user = UserProfile(
        garmin_credentials=GarminAuth(email="runner@example.com", connected=True),
        birth_date=date.today() - timedelta(days=30 * 365),
        sex="male",
        height_cm=175,
        weight_kg=70,
        goal=TrainingGoal(type="marathon", weekly_volume_km=60),
        fitness_level=FitnessLevel(level="advanced"),
    )
    metrics = HealthMetrics(
        metric_date=date(2026, 4, 6),
        sleep=SleepData(score=45),
        hrv=HRVData(deviation_pct=-18),
        body_battery=BodyBatteryData(morning_value=30),
        rhr=RHRData(value_bpm=68, baseline_bpm=50, deviation_bpm=18),
        training_load=TrainingLoad(ramp_rate=6.0, weekly_volume_km=60, previous_week_volume_km=50),
        recent_sleep_scores=[50, 55, 58],
    )
    response = asyncio.run(
        GarminCoachingEngine().answer_question(
            user,
            "오늘 고강도 해도 돼?",
            CoachingContext(
                current_metrics=metrics,
                readiness=ReadinessScore(score=35, level="red", confidence="medium"),
            ),
        )
    )
    assert response.guardrail_applied is True
    assert response.guardrail_reasons
