from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from garmin_coach.models import (
    DayPlan,
    ReadinessScore,
    SessionFeedback,
    SessionType,
    TrainingLoad,
    UserProfile,
    WeeklyPlan,
)


@dataclass
class WeeklyTrainingPlanner:
    def generate(
        self,
        user: UserProfile,
        current_load: TrainingLoad,
        readiness_trend: list[ReadinessScore],
        feedback_history: list[SessionFeedback],
        start_date: date | None = None,
    ) -> WeeklyPlan:
        start_date = start_date or date.today()
        structure = self._structure_for_goal(user.goal.type)
        conservative = any(item.level in {"red", "critical"} for item in readiness_trend[-3:])
        feedback_penalty = self._feedback_multiplier(feedback_history)
        load_multiplier = 0.85 if conservative else 1.0
        load_multiplier *= feedback_penalty
        base_tss = max(current_load.ctl * 7, 150.0) * load_multiplier
        day_plans: list[DayPlan] = []
        for idx, session_type in enumerate(structure):
            target_tss = self._target_tss(session_type, base_tss)
            day_plans.append(
                DayPlan(
                    date=(start_date + timedelta(days=idx)).isoformat(),
                    session_type=session_type,
                    description=self._describe(session_type, user.goal.type),
                    target_tss=round(target_tss, 1),
                )
            )
        return WeeklyPlan(
            days=day_plans,
            total_tss=round(sum(day.target_tss for day in day_plans), 1),
            notes=[
                "Readiness 하락 시 하드 세션을 이지/회복으로 자동 전환하세요."
                if conservative
                else "현재 회복 추세 기준으로 계획 생성",
                f"피드백 보정 계수: {feedback_penalty:.2f}",
                f"목표 유형: {user.goal.type}",
            ],
        )

    @staticmethod
    def _feedback_multiplier(feedback_history: list[SessionFeedback]) -> float:
        if not feedback_history:
            return 1.0
        multiplier = 1.0
        if any(item.pain_report for item in feedback_history[-5:]):
            multiplier *= 0.85
        if any(item.completion.value == "none" for item in feedback_history[-3:]):
            multiplier *= 0.9
        recent_rpe = [item.rpe for item in feedback_history[-5:] if item.rpe is not None]
        if recent_rpe and (sum(recent_rpe) / len(recent_rpe)) >= 8:
            multiplier *= 0.9
        return multiplier

    @staticmethod
    def _structure_for_goal(goal_type: str) -> list[SessionType]:
        if goal_type == "marathon":
            return [
                SessionType.EASY,
                SessionType.INTERVAL,
                SessionType.REST,
                SessionType.TEMPO,
                SessionType.EASY,
                SessionType.LONG,
                SessionType.REST,
            ]
        if goal_type == "fitness":
            return [
                SessionType.EASY,
                SessionType.MODERATE,
                SessionType.REST,
                SessionType.CROSS,
                SessionType.EASY,
                SessionType.LONG,
                SessionType.REST,
            ]
        return [
            SessionType.EASY,
            SessionType.MODERATE,
            SessionType.REST,
            SessionType.EASY,
            SessionType.MODERATE,
            SessionType.LONG,
            SessionType.REST,
        ]

    @staticmethod
    def _target_tss(session_type: SessionType, weekly_tss: float) -> float:
        weights = {
            SessionType.REST: 0.0,
            SessionType.EASY: 0.12,
            SessionType.MODERATE: 0.15,
            SessionType.HARD: 0.18,
            SessionType.INTERVAL: 0.18,
            SessionType.TEMPO: 0.16,
            SessionType.LONG: 0.22,
            SessionType.CROSS: 0.10,
            SessionType.RACE: 0.20,
        }
        return weekly_tss * weights.get(session_type, 0.12)

    @staticmethod
    def _describe(session_type: SessionType, goal_type: str) -> str:
        descriptions = {
            SessionType.REST: "완전 휴식 또는 가벼운 mobility",
            SessionType.EASY: "Zone 2 이지 세션",
            SessionType.MODERATE: "지속 가능한 중간 강도 세션",
            SessionType.INTERVAL: "고품질 인터벌 세션",
            SessionType.TEMPO: "템포 또는 steady effort",
            SessionType.LONG: "장거리 지구력 세션",
            SessionType.CROSS: "부담이 적은 크로스트레이닝",
            SessionType.RACE: "레이스/시뮬레이션 세션",
        }
        return f"{descriptions.get(session_type, '기본 세션')} · 목표 {goal_type} 기준"
