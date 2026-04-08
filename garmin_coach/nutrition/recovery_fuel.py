from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from garmin_coach.models import SessionType

from ._profile import filter_food_examples, nutrition_context_from_user


@dataclass(slots=True)
class RecoveryAdvice:
    priority: str
    timing: str
    macros: dict[str, tuple[float, float] | tuple[float, float]]
    food_examples: list[str]
    hydration: str
    restrictions_applied: list[str] = field(default_factory=list)
    rationale: str = ""


def _resolve_session_type(activity: Any) -> SessionType:
    session_type = (
        getattr(activity, "session_type", None) or getattr(activity, "type", None) or "easy"
    )
    if isinstance(session_type, SessionType):
        return session_type
    value = str(session_type).lower()
    if value == "interval":
        return SessionType.INTERVAL
    if value == "tempo":
        return SessionType.TEMPO
    if value == "long":
        return SessionType.LONG
    if value == "race":
        return SessionType.RACE
    if value == "hard":
        return SessionType.HARD
    return SessionType.EASY


def get_recovery_advice(activity: Any, user: Any) -> RecoveryAdvice:
    context = nutrition_context_from_user(user)
    weight = context.weight_kg
    session = _resolve_session_type(activity)

    if session in {SessionType.INTERVAL, SessionType.TEMPO, SessionType.HARD}:
        priority = "carb_repletion"
        examples = ["밥 + 두부", "프로틴 쉐이크 + 바나나", "김밥 + 두유", "떡 + 식물성 프로틴"]
        hydration = "전해질 포함 수분 보충"
        rationale = "고강도 세션은 글리코겐 회복이 우선입니다."
    elif session in {SessionType.LONG, SessionType.RACE}:
        priority = "carbs_electrolytes"
        examples = ["밥 + 닭가슴살", "김밥 + 우유", "떡 + 프로틴 쉐이크", "바나나 + 스포츠 드링크"]
        hydration = "전해질 500-1000mg/L 포함 수분 보충"
        rationale = "장거리 세션은 탄수화물과 나트륨 보충을 함께 챙겨야 합니다."
    elif context.goal_type == "rehab":
        priority = "protein_support"
        examples = ["두부 + 밥", "그릭 요거트 + 과일", "템페 + 감자", "프로틴 쉐이크"]
        hydration = "평소 수준 + 회복 중 수분 유지"
        rationale = "재활 중에는 회복 촉진을 위해 단백질 비중을 높입니다."
    else:
        priority = "protein_repair"
        examples = ["두부 + 밥", "그릭 요거트 + 그래놀라", "바나나 + 프로틴 쉐이크"]
        hydration = "일반 수분 보충"
        rationale = "쉬운 세션은 근회복을 위한 단백질 우선 전략이면 충분합니다."

    filtered_examples, removed = filter_food_examples(examples, context)
    carbs = (round(weight * 0.8, 1), round(weight * 1.2, 1))
    protein = (max(20.0, round(weight * 0.3, 1)), min(40.0, round(weight * 0.4, 1)))
    if context.goal_type == "weight_loss":
        rationale += " 체중 감량 중에도 회복을 위해 단백질과 최소 에너지는 유지합니다."
    return RecoveryAdvice(
        priority=priority,
        timing="운동 후 30-60분 이내",
        macros={"carbs_g": carbs, "protein_g": protein},
        food_examples=filtered_examples,
        hydration=hydration,
        restrictions_applied=sorted(set(removed + context.food_restrictions + context.allergies)),
        rationale=rationale,
    )
