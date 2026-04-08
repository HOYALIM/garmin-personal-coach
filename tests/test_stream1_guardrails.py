import asyncio
from datetime import date, timedelta
from typing import Optional


def _user(
    injured=False,
    beta_blocker=False,
    body_part="knee",
    clearance="pending",
    restrictions=None,
    pain_reports_count=2,
    restricted_session_types=None,
):
    from garmin_coach.models import (
        FitnessLevel,
        GarminAuth,
        InjuryRecord,
        MedicalProfile,
        NutritionProfile,
        TrainingGoal,
        UserProfile,
    )

    return UserProfile(
        garmin_credentials=GarminAuth(email="runner@example.com", connected=True),
        birth_date=date.today() - timedelta(days=30 * 365),
        sex="male",
        height_cm=175,
        weight_kg=70,
        goal=TrainingGoal(type="marathon", weekly_volume_km=60),
        fitness_level=FitnessLevel(level="advanced"),
        medical=MedicalProfile(
            beta_blocker=beta_blocker,
            current_injuries=[
                InjuryRecord(
                    body_part=body_part,
                    description="pain",
                    medical_clearance=clearance,
                    restrictions=list(restrictions or ["no_impact"]),
                    pain_reports_count=pain_reports_count,
                    restricted_session_types=list(restricted_session_types or ["interval"]),
                )
            ]
            if injured
            else [],
        ),
        nutrition=NutritionProfile(allergies=["땅콩"]),
    )


def _metrics(max_hr: Optional[int] = 205):
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
        sleep=SleepData(score=45),
        hrv=HRVData(deviation_pct=-18),
        body_battery=BodyBatteryData(morning_value=32),
        rhr=RHRData(value_bpm=67, baseline_bpm=50, deviation_bpm=17),
        spo2=SpO2Data(min_pct=89),
        training_load=TrainingLoad(
            tsb=-20,
            ramp_rate=6.4,
            monotony=2.1,
            strain=120,
            ctl=40,
            weekly_volume_km=60,
            previous_week_volume_km=50,
        ),
        recent_sleep_scores=[55, 58, 59],
        recent_activities=[ActivitySummary(max_hr=max_hr)] if max_hr is not None else [],
        environment=EnvironmentMetrics(temperature_c=36, wbgt_c=29, air_quality="very_bad"),
    )


def test_guardrails_compose_rewrite_and_warnings():
    from garmin_coach.engine.guardrails import CoachingGuardrails, GuardrailAction
    from garmin_coach.models import CoachingResponse

    result = CoachingGuardrails().validate(
        CoachingResponse(text="Zone 4로 진행", intensity="hard", max_zone=3, uses_hr_zones=True),
        _user(beta_blocker=True),
        _metrics(max_hr=None),
    )
    assert result.action == GuardrailAction.MODIFY
    text = result.modified_coaching or ""
    assert "RPE" in text
    assert "수면 부채" in text
    assert "SpO2" in text


def test_guardrails_block_injury_restricted_session():
    from garmin_coach.engine.guardrails import CoachingGuardrails, GuardrailAction
    from garmin_coach.models import CoachingResponse

    result = CoachingGuardrails().validate(
        CoachingResponse(text="인터벌 세션", intensity="interval", max_zone=4),
        _user(injured=True),
        _metrics(max_hr=None),
    )
    assert result.action == GuardrailAction.OVERRIDE
    assert "의료 허가" in result.reason or "통증" in result.reason


def test_guardrails_block_active_lower_body_injury_without_pending_clearance_or_restrictions():
    from garmin_coach.engine.guardrails import CoachingGuardrails, GuardrailAction
    from garmin_coach.models import CoachingResponse, SessionType

    result = CoachingGuardrails().validate(
        CoachingResponse(
            text="Zone 2 easy run", intensity="easy", max_zone=2, session_type=SessionType.EASY
        ),
        _user(
            injured=True,
            body_part="ankle",
            clearance="full",
            restrictions=[],
            pain_reports_count=0,
            restricted_session_types=[],
        ),
        _metrics(max_hr=None),
    )
    assert result.action == GuardrailAction.OVERRIDE
    assert "활성 부상 부위 'ankle'" in result.reason


def test_guardrails_block_back_loading_session_for_active_back_injury():
    from garmin_coach.engine.guardrails import CoachingGuardrails, GuardrailAction
    from garmin_coach.models import CoachingResponse, SessionType

    result = CoachingGuardrails().validate(
        CoachingResponse(
            text="Long run with strength finisher",
            intensity="moderate",
            max_zone=3,
            session_type=SessionType.LONG,
        ),
        _user(
            injured=True,
            body_part="back",
            clearance="full",
            restrictions=[],
            pain_reports_count=0,
            restricted_session_types=[],
        ),
        _metrics(max_hr=None),
    )
    assert result.action == GuardrailAction.OVERRIDE
    assert "back" in (result.modified_coaching or "")


def test_guardrails_allow_unrelated_session_for_shoulder_injury():
    from garmin_coach.engine.guardrails import CoachingGuardrails
    from garmin_coach.models import CoachingResponse, SessionType

    result = CoachingGuardrails().validate(
        CoachingResponse(
            text="Easy walk and mobility",
            intensity="easy",
            max_zone=1,
            session_type=SessionType.EASY,
        ),
        _user(
            injured=True,
            body_part="shoulder",
            clearance="full",
            restrictions=[],
            pain_reports_count=0,
            restricted_session_types=[],
        ),
        _metrics(max_hr=None),
    )
    assert "injury-active-body-part" not in [result.rule_id]


def test_answer_question_injury_case_is_guardrailed_and_overridden():
    from garmin_coach.engine.coaching import GarminCoachingEngine
    from garmin_coach.engine.interfaces import CoachingContext
    from garmin_coach.models import ReadinessScore

    user = _user(
        injured=True,
        body_part="knee",
        clearance="full",
        restrictions=[],
        pain_reports_count=0,
        restricted_session_types=[],
    )
    response = asyncio.run(
        GarminCoachingEngine().answer_question(
            user,
            "오늘 인터벌 해도 돼?",
            CoachingContext(
                current_metrics=_metrics(max_hr=None),
                readiness=ReadinessScore(score=55, level="yellow", confidence="medium"),
            ),
        )
    )
    assert response.guardrail_applied is True
    assert any("활성 부상" in reason for reason in response.guardrail_reasons)


def test_guardrails_block_bmr_below_and_filter_allergen():
    from garmin_coach.engine.guardrails import CoachingGuardrails, GuardrailAction
    from garmin_coach.models import CoachingResponse

    block = CoachingGuardrails().validate(
        CoachingResponse(text="하루 800 kcal와 땅콩버터 토스트", intensity="easy", max_zone=1),
        _user(),
        _metrics(max_hr=None),
    )
    assert block.action == GuardrailAction.BLOCK_AND_ALERT
