from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from garmin_coach.models import SessionType

from ._profile import filter_food_examples, nutrition_context_from_user


@dataclass(slots=True)
class PreWorkoutAdvice:
    description: str
    carbs_g: tuple[float, float]
    examples: list[str]
    restrictions_applied: list[str] = field(default_factory=list)
    protein: str = "소량"
    fat: str = "최소화"
    fiber: str = "최소화"


@dataclass(slots=True)
class DuringWorkoutAdvice:
    description: str
    carbs_per_hour_g: tuple[int, int]
    hydration: str
    sodium: str
    requires_electrolytes: bool


@dataclass(slots=True)
class PostWorkoutAdvice:
    timing: str
    carbs_g: tuple[float, float]
    protein_g: tuple[float, float]
    examples: list[str]
    restrictions_applied: list[str] = field(default_factory=list)
    rationale: str = ""


def _session_type(value: SessionType | str) -> SessionType:
    if isinstance(value, SessionType):
        return value
    return SessionType(str(value).lower())


def get_pre_workout_advice(
    hours_until: float,
    session_type: SessionType | str,
    user: Any,
) -> PreWorkoutAdvice:
    context = nutrition_context_from_user(user)
    weight = context.weight_kg
    session = _session_type(session_type)
    if hours_until >= 3:
        examples = ["밥 + 두부", "오트밀 + 과일", "토스트 + 잼", "바나나 + 요거트"]
        description = "정상 식사 가능"
        carbs = (round(weight * 1.0, 1), round(weight * 2.0, 1))
        protein = "포함"
        fat = "적당히 OK"
        fiber = "적당히 OK"
    elif hours_until >= 1:
        examples = ["바나나 + 꿀", "흰쌀밥 소량", "에너지바", "토스트 + 잼"]
        description = "가벼운 간식"
        carbs = (round(weight * 0.5, 1), round(weight * 1.0, 1))
        protein = "소량"
        fat = "최소화"
        fiber = "최소화"
    else:
        examples = ["젤 1개", "스포츠 드링크", "바나나 반개", "떡 1-2개"]
        description = "빠른 에너지만"
        carbs = (round(weight * 0.3, 1), round(weight * 0.5, 1))
        protein = "불필요"
        fat = "없음"
        fiber = "없음"

    if session in {SessionType.LONG, SessionType.RACE} and "떡 1-2개" not in examples:
        examples.append("떡 1-2개")
    filtered_examples, removed = filter_food_examples(examples, context)
    restrictions_applied = removed + context.food_restrictions + context.allergies
    return PreWorkoutAdvice(
        description=description,
        carbs_g=carbs,
        examples=filtered_examples,
        restrictions_applied=sorted(set(restrictions_applied)),
        protein=protein,
        fat=fat,
        fiber=fiber,
    )


def get_during_advice(duration_min: int, session_type: SessionType | str) -> DuringWorkoutAdvice:
    _session_type(session_type)
    if duration_min < 60:
        return DuringWorkoutAdvice(
            description="수분만",
            carbs_per_hour_g=(0, 0),
            hydration="물 또는 전해질 위주",
            sodium="선택 사항",
            requires_electrolytes=False,
        )
    if duration_min <= 90:
        return DuringWorkoutAdvice(
            description="30-60g 탄수화물/시간",
            carbs_per_hour_g=(30, 60),
            hydration="15-20분마다 150-250ml",
            sodium="고온이거나 땀이 많으면 500-700mg/L",
            requires_electrolytes=True,
        )
    if duration_min <= 180:
        return DuringWorkoutAdvice(
            description="60-90g 탄수화물/시간 (혼합 탄수화물)",
            carbs_per_hour_g=(60, 90),
            hydration="15-20분마다 150-250ml, 더우면 상향",
            sodium="500-1000mg/L 권장",
            requires_electrolytes=True,
        )
    return DuringWorkoutAdvice(
        description="60-90g 탄수화물/시간 + 소금 보충 필수",
        carbs_per_hour_g=(60, 90),
        hydration="15-20분마다 200-300ml, 더우면 250-350ml",
        sodium="소금/전해질 필수, 700-1000mg/L",
        requires_electrolytes=True,
    )


def get_post_workout_advice(session_type: SessionType | str, user: Any) -> PostWorkoutAdvice:
    context = nutrition_context_from_user(user)
    weight = context.weight_kg
    session = _session_type(session_type)
    examples = [
        "초코우유 500ml",
        "프로틴 쉐이크 + 바나나",
        "밥 + 닭가슴살",
        "그릭 요거트 + 그래놀라 + 과일",
        "김밥 + 우유",
        "떡 + 프로틴 쉐이크",
    ]
    filtered_examples, removed = filter_food_examples(examples, context)
    rationale = "운동 후 30분 이내 골든 윈도우 회복 전략입니다."
    if session in {
        SessionType.INTERVAL,
        SessionType.TEMPO,
        SessionType.HARD,
        SessionType.LONG,
        SessionType.RACE,
    }:
        rationale = "고강도/장거리 세션 회복을 위해 탄수화물과 단백질을 함께 보충합니다."
    return PostWorkoutAdvice(
        timing="운동 후 30분 이내 이상적, 60분 이내 권장",
        carbs_g=(round(weight * 1.0, 1), round(weight * 1.2, 1)),
        protein_g=(max(20.0, round(weight * 0.3, 1)), min(40.0, round(weight * 0.4, 1))),
        examples=filtered_examples,
        restrictions_applied=sorted(set(removed + context.food_restrictions + context.allergies)),
        rationale=rationale,
    )
