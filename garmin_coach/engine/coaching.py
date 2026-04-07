from __future__ import annotations

from dataclasses import dataclass, field

from garmin_coach.engine.guardrails import CoachingGuardrails
from garmin_coach.engine.interfaces import CoachingContext, CoachingEngine
from garmin_coach.engine.rules import fallback_daily_coaching
from garmin_coach.engine.training_plan import WeeklyTrainingPlanner
from garmin_coach.models import (
    ActivitySummary,
    CoachingResponse,
    HealthMetrics,
    ReadinessScore,
    SessionFeedback,
    TrainingLoad,
    UserProfile,
    WeeklyPlan,
    WorkoutAnalysis,
)


@dataclass
class GarminCoachingEngine(CoachingEngine):
    guardrails: CoachingGuardrails = field(default_factory=CoachingGuardrails)
    planner: WeeklyTrainingPlanner = field(default_factory=WeeklyTrainingPlanner)

    async def generate_daily_coaching(
        self, user: UserProfile, metrics: HealthMetrics, readiness: ReadinessScore
    ) -> CoachingResponse:
        coaching = fallback_daily_coaching(user, metrics, readiness)
        result = self.guardrails.validate(coaching, user, metrics)
        if result.action.value != "pass":
            coaching.text = result.modified_coaching or coaching.text
            coaching.guardrail_applied = True
            coaching.guardrail_reason = result.reason
            coaching.guardrail_reasons = result.reasons
            if result.action.value in {"override", "block"}:
                coaching.intensity = "rest"
                coaching.max_zone = min(coaching.max_zone, 1)
        return coaching

    async def generate_workout_analysis(
        self, user: UserProfile, activity: ActivitySummary
    ) -> WorkoutAnalysis:
        comparison = (
            "최근 세션과 유사한 부하"
            if activity.training_effect_aerobic
            else "기준 비교 데이터 부족"
        )
        notes = []
        if activity.training_effect_aerobic is not None:
            notes.append(f"유산소 TE {activity.training_effect_aerobic}")
        if activity.training_effect_anaerobic is not None:
            notes.append(f"무산소 TE {activity.training_effect_anaerobic}")
        if activity.running_dynamics and activity.running_dynamics.cadence_spm:
            notes.append(f"케이던스 {activity.running_dynamics.cadence_spm}")
        return WorkoutAnalysis(
            summary=f"{activity.type or activity.sport_type or 'activity'} 세션 분석",
            zone_distribution=activity.hr_zones,
            comparison_to_recent=comparison,
            pace_drift=None,
            coaching_notes=notes,
        )

    async def generate_weekly_plan(
        self,
        user: UserProfile,
        current_load: TrainingLoad,
        readiness_trend: list[ReadinessScore],
        feedback_history: list[SessionFeedback],
    ) -> WeeklyPlan:
        return self.planner.generate(user, current_load, readiness_trend, feedback_history)

    async def answer_question(
        self, user: UserProfile, question: str, context: CoachingContext
    ) -> CoachingResponse:
        if context.readiness and context.readiness.level in {"red", "critical"}:
            text = "현재 회복 지표가 좋지 않아 훈련 확대보다 회복 우선이 맞습니다."
        else:
            text = f"질문을 기준으로 보면 현재 목표({user.goal.type})와 최근 컨텍스트에 맞춘 보수적 코칭이 적절합니다: {question}"
        return CoachingResponse(text=text, intensity="easy", max_zone=2)
