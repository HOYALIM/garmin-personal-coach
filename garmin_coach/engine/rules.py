from __future__ import annotations

from garmin_coach.models import (
    CoachingResponse,
    HealthMetrics,
    ReadinessScore,
    SessionType,
    UserProfile,
)


def fallback_daily_coaching(
    user: UserProfile, metrics: HealthMetrics, readiness: ReadinessScore
) -> CoachingResponse:
    metadata = {
        "readiness_level": readiness.level,
        "readiness_confidence": readiness.confidence,
        "limiting_factors": readiness.limiting_factors,
    }
    if readiness.level == "green":
        return CoachingResponse(
            text="회복 지표가 안정적입니다. 오늘은 계획된 핵심 세션을 소화해도 됩니다.",
            intensity="hard"
            if user.goal.type in {"marathon", "cycling", "triathlon"}
            else "moderate",
            max_zone=4,
            session_type=SessionType.HARD
            if user.goal.type in {"marathon", "cycling", "triathlon"}
            else SessionType.MODERATE,
            metadata=metadata,
        )
    if readiness.level == "yellow":
        return CoachingResponse(
            text="회복 지표가 완전하지 않습니다. 오늘은 계획 강도를 20-40% 낮추고 기술과 리듬 유지에 집중하세요.",
            intensity="tempo",
            max_zone=3,
            session_type=SessionType.MODERATE,
            metadata=metadata,
        )
    if readiness.level == "red":
        return CoachingResponse(
            text="피로 신호가 뚜렷합니다. 오늘은 이지 러닝 또는 20분 이하 Zone 1 회복만 권장합니다.",
            intensity="easy",
            max_zone=1,
            session_type=SessionType.EASY,
            metadata=metadata,
        )
    return CoachingResponse(
        text="회복 지표가 매우 낮습니다. 오늘은 운동을 쉬고 건강 상태를 먼저 확인하세요.",
        intensity="rest",
        max_zone=0,
        uses_hr_zones=False,
        session_type=SessionType.REST,
        metadata=metadata,
    )
