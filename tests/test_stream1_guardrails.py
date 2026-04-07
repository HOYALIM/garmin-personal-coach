from datetime import date, timedelta


def _user(beta_blocker=False, allergy=None, clearance="full"):
    from garmin_coach.models import (
        CoachingPreferences,
        FitnessLevel,
        GarminAuth,
        InjuryRecord,
        MedicalProfile,
        NutritionProfile,
        TrainingGoal,
        UserProfile,
    )

    return UserProfile(
        garmin_credentials=GarminAuth(email="a@example.com", connected=True),
        birth_date=date.today() - timedelta(days=30 * 365),
        sex="male",
        height_cm=175,
        weight_kg=70,
        goal=TrainingGoal(type="marathon", weekly_volume_km=50),
        fitness_level=FitnessLevel(level="advanced"),
        medical=MedicalProfile(
            beta_blocker=beta_blocker,
            current_injuries=[
                InjuryRecord(
                    body_part="knee",
                    description="pain",
                    medical_clearance=clearance,
                    restrictions=["no_impact"],
                    pain_reports_count=2 if clearance != "full" else 0,
                    restricted_session_types=["interval"],
                )
            ]
            if clearance != "full"
            else [],
        ),
        nutrition=NutritionProfile(allergies=[allergy] if allergy else []),
        preferences=CoachingPreferences(),
    )


def _metrics(tsb=-35, sleep=80, bb=80, hrv=0, rhr_dev=0, ramp_rate=6.2, max_hr=None):
    from garmin_coach.models import (
        ActivitySummary,
        BodyBatteryData,
        EnvironmentMetrics,
        HRVData,
        HealthMetrics,
        RHRData,
        SleepData,
        SpO2Data,
        TrainingLoad,
    )

    return HealthMetrics(
        metric_date=date(2026, 4, 6),
        sleep=SleepData(score=sleep),
        body_battery=BodyBatteryData(morning_value=bb),
        hrv=HRVData(deviation_pct=hrv),
        rhr=RHRData(value_bpm=50 + rhr_dev, baseline_bpm=50, deviation_bpm=rhr_dev),
        spo2=SpO2Data(min_pct=89),
        training_load=TrainingLoad(
            tsb=tsb,
            ramp_rate=ramp_rate,
            monotony=2.3,
            strain=120,
            ctl=40,
            weekly_volume_km=58,
            previous_week_volume_km=50,
        ),
        recent_sleep_scores=[55, 58, 59],
        recent_activities=[ActivitySummary(max_hr=max_hr)] if max_hr is not None else [],
        environment=EnvironmentMetrics(temperature_c=36, wbgt_c=29, air_quality="very_bad"),
    )


def test_guardrail_overrides_hard_session_for_low_tsb():
    from garmin_coach.engine.guardrails import CoachingGuardrails, GuardrailAction
    from garmin_coach.models import CoachingResponse, SessionType

    result = CoachingGuardrails().validate(
        CoachingResponse(
            text="인터벌 6x1000m", intensity="hard", max_zone=4, session_type=SessionType.INTERVAL
        ),
        _user(),
        _metrics(tsb=-35, bb=80, max_hr=None),
    )
    assert result.action == GuardrailAction.OVERRIDE
    assert any("TSB" in reason for reason in result.reasons)


def test_guardrail_composes_multiple_warnings_without_erasing_beta_blocker_change():
    from garmin_coach.engine.guardrails import CoachingGuardrails, GuardrailAction
    from garmin_coach.models import CoachingResponse

    result = CoachingGuardrails().validate(
        CoachingResponse(text="Zone 4로 진행", intensity="hard", max_zone=3, uses_hr_zones=True),
        _user(beta_blocker=True),
        _metrics(tsb=0, rhr_dev=18, bb=70, max_hr=None),
    )
    assert result.action == GuardrailAction.MODIFY
    assert "RPE" in (result.modified_coaching or "")
    assert "안정시 심박" in result.reason
    assert len(result.reasons) >= 2


def test_guardrail_composes_multiple_rewrite_rules():
    from garmin_coach.engine.guardrails import CoachingGuardrails, GuardrailAction
    from garmin_coach.models import CoachingResponse

    result = CoachingGuardrails().validate(
        CoachingResponse(text="Zone 4로 진행", intensity="hard", max_zone=3, uses_hr_zones=True),
        _user(beta_blocker=True),
        _metrics(tsb=0, sleep=45, hrv=-20, bb=70, rhr_dev=0, max_hr=None),
    )
    assert result.action == GuardrailAction.MODIFY
    text = result.modified_coaching or ""
    assert "RPE" in text
    assert "20-40%" in text or "이지 세션" in text


def test_guardrail_removes_allergen_and_blocks_pending_clearance():
    from garmin_coach.engine.guardrails import CoachingGuardrails, GuardrailAction
    from garmin_coach.models import CoachingResponse

    allergy_result = CoachingGuardrails().validate(
        CoachingResponse(text="운동 후 땅콩버터 토스트를 드세요", intensity="easy", max_zone=2),
        _user(allergy="땅콩"),
        _metrics(tsb=0, bb=70, max_hr=None),
    )
    assert allergy_result.action == GuardrailAction.MODIFY
    assert "알레르기 식품" in (allergy_result.modified_coaching or "")

    injury_result = CoachingGuardrails().validate(
        CoachingResponse(text="인터벌 세션", intensity="interval", max_zone=4),
        _user(clearance="pending"),
        _metrics(tsb=0, bb=70, max_hr=None),
    )
    assert injury_result.action == GuardrailAction.OVERRIDE


def test_guardrail_adds_sleep_debt_environment_and_spo2_warnings():
    from garmin_coach.engine.guardrails import CoachingGuardrails
    from garmin_coach.models import CoachingResponse

    result = CoachingGuardrails().validate(
        CoachingResponse(text="오늘 하드 세션을 진행하세요", intensity="moderate", max_zone=3),
        _user(),
        _metrics(tsb=0, bb=70, rhr_dev=0, max_hr=None),
    )
    text = result.modified_coaching or ""
    assert "수면 부채" in text
    assert "SpO2" in text
    assert "기온이 매우 높습니다" in text


def test_guardrail_stops_for_max_hr_anomaly():
    from garmin_coach.engine.guardrails import CoachingGuardrails, GuardrailAction
    from garmin_coach.models import CoachingResponse

    result = CoachingGuardrails().validate(
        CoachingResponse(text="템포런 진행", intensity="tempo", max_zone=3),
        _user(),
        _metrics(tsb=0, bb=70, ramp_rate=0, max_hr=205),
    )
    assert result.action == GuardrailAction.OVERRIDE
    assert "최대 심박" in result.reason


def test_guardrail_blocks_bmr_below_and_handles_empty_metrics():
    from garmin_coach.engine.guardrails import CoachingGuardrails, GuardrailAction
    from garmin_coach.models import CoachingResponse, HealthMetrics, TrainingLoad

    block = CoachingGuardrails().validate(
        CoachingResponse(text="하루 800 kcal만 드세요", intensity="easy", max_zone=1),
        _user(),
        _metrics(tsb=0, bb=70, max_hr=None),
    )
    assert block.action == GuardrailAction.BLOCK_AND_ALERT

    empty = CoachingGuardrails().validate(
        CoachingResponse(text="가벼운 산책", intensity="easy", max_zone=1),
        _user(),
        HealthMetrics(metric_date=date(2026, 4, 6), training_load=TrainingLoad()),
    )
    assert empty.action in {GuardrailAction.PASS, GuardrailAction.MODIFY}
