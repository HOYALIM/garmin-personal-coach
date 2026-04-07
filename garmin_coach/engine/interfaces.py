from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

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
class CoachingContext:
    recent_activities: list[ActivitySummary] = field(default_factory=list)
    current_metrics: HealthMetrics | None = None
    readiness: ReadinessScore | None = None
    notes: list[str] = field(default_factory=list)


class CoachingEngine(ABC):
    @abstractmethod
    async def generate_daily_coaching(
        self,
        user: UserProfile,
        metrics: HealthMetrics,
        readiness: ReadinessScore,
    ) -> CoachingResponse:
        raise NotImplementedError

    @abstractmethod
    async def generate_workout_analysis(
        self,
        user: UserProfile,
        activity: ActivitySummary,
    ) -> WorkoutAnalysis:
        raise NotImplementedError

    @abstractmethod
    async def generate_weekly_plan(
        self,
        user: UserProfile,
        current_load: TrainingLoad,
        readiness_trend: list[ReadinessScore],
        feedback_history: list[SessionFeedback],
    ) -> WeeklyPlan:
        raise NotImplementedError

    @abstractmethod
    async def answer_question(
        self,
        user: UserProfile,
        question: str,
        context: CoachingContext,
    ) -> CoachingResponse:
        raise NotImplementedError
