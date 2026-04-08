from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from garmin_coach.models import SessionType

from ._profile import NutritionContext, nutrition_context_from_user


CARB_PERIODIZATION: dict[SessionType, tuple[float, float]] = {
    SessionType.REST: (3.0, 5.0),
    SessionType.EASY: (4.0, 6.0),
    SessionType.MODERATE: (5.0, 7.0),
    SessionType.CROSS: (5.0, 7.0),
    SessionType.HARD: (6.0, 8.0),
    SessionType.INTERVAL: (6.0, 8.0),
    SessionType.TEMPO: (6.0, 8.0),
    SessionType.LONG: (7.0, 10.0),
    SessionType.RACE: (8.0, 12.0),
}

PROTEIN_TARGETS: dict[str, tuple[float, float]] = {
    "endurance": (1.2, 1.6),
    "strength": (1.6, 2.2),
    "weight_loss": (1.6, 2.4),
    "rehab": (1.6, 2.0),
}

ACTIVITY_FACTORS: dict[SessionType, float] = {
    SessionType.REST: 1.2,
    SessionType.EASY: 1.375,
    SessionType.MODERATE: 1.55,
    SessionType.CROSS: 1.55,
    SessionType.HARD: 1.725,
    SessionType.INTERVAL: 1.725,
    SessionType.TEMPO: 1.725,
    SessionType.LONG: 1.9,
    SessionType.RACE: 1.95,
}

SESSION_DURATION_MIN: dict[SessionType, int] = {
    SessionType.REST: 0,
    SessionType.EASY: 50,
    SessionType.MODERATE: 75,
    SessionType.CROSS: 60,
    SessionType.HARD: 75,
    SessionType.INTERVAL: 70,
    SessionType.TEMPO: 75,
    SessionType.LONG: 150,
    SessionType.RACE: 180,
}

FAT_MINIMUM_G_PER_KG = 1.0


@dataclass(slots=True)
class DailyMacros:
    carbs_g: tuple[float, float]
    protein_g: tuple[float, float]
    fat_g: tuple[float, float]
    total_kcal: tuple[float, float]
    session_type: SessionType
    rationale: str
    bmr_kcal: float
    goal_type: str
    degraded_safely: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "carbs_g": self.carbs_g,
            "protein_g": self.protein_g,
            "fat_g": self.fat_g,
            "total_kcal": self.total_kcal,
            "session_type": self.session_type.value,
            "rationale": self.rationale,
            "bmr_kcal": self.bmr_kcal,
            "goal_type": self.goal_type,
            "degraded_safely": self.degraded_safely,
        }


def estimate_bmr(context: NutritionContext) -> float:
    sex_adjustment = 5 if context.sex == "male" else -161
    mifflin = 10 * context.weight_kg + 6.25 * context.height_cm - 5 * context.age + sex_adjustment
    fallback_floor = 24 * context.weight_kg
    return max(mifflin, fallback_floor)


def _resolve_session_type(today_session: SessionType | str) -> SessionType:
    if isinstance(today_session, SessionType):
        return today_session
    return SessionType(str(today_session).lower())


def calculate_daily_macros(
    user: Any,
    today_session: SessionType | str,
    goal: str | None = None,
) -> DailyMacros:
    session_type = _resolve_session_type(today_session)
    context = nutrition_context_from_user(user, goal=goal)
    carb_range = CARB_PERIODIZATION[session_type]
    protein_range = PROTEIN_TARGETS.get(context.goal_type, PROTEIN_TARGETS["endurance"])
    weight = context.weight_kg
    bmr = estimate_bmr(context)
    duration_min = SESSION_DURATION_MIN[session_type]
    activity_factor = ACTIVITY_FACTORS[session_type]
    activity_kcal = weight * duration_min * 0.09
    tdee = bmr * activity_factor + activity_kcal

    if context.goal_type == "weight_loss":
        kcal_target = (max(bmr, tdee - 500), max(bmr, tdee - 300))
        rationale = "Weight-loss branch uses a modest deficit while respecting the BMR floor."
    elif context.goal_type == "rehab":
        kcal_target = (max(bmr, tdee), max(bmr, tdee + 150))
        rationale = (
            "Rehab branch protects recovery with higher protein and no calorie drop below BMR."
        )
    else:
        kcal_target = (max(bmr, tdee - 100), max(bmr, tdee + 150))
        rationale = "Fuel is scaled to session demand using periodized carbohydrate targets."

    carbs = (round(carb_range[0] * weight, 1), round(carb_range[1] * weight, 1))
    protein = (round(protein_range[0] * weight, 1), round(protein_range[1] * weight, 1))
    fat_min = round(FAT_MINIMUM_G_PER_KG * weight, 1)
    fat_max_from_energy = max(fat_min, round(kcal_target[1] * 0.3 / 9, 1))
    fat = (fat_min, fat_max_from_energy)

    if context.missing_fields:
        rationale += (
            f" Missing profile fields {', '.join(context.missing_fields)} triggered safe defaults."
        )

    return DailyMacros(
        carbs_g=carbs,
        protein_g=protein,
        fat_g=fat,
        total_kcal=(round(kcal_target[0], 1), round(kcal_target[1], 1)),
        session_type=session_type,
        rationale=rationale,
        bmr_kcal=round(bmr, 1),
        goal_type=context.goal_type,
        degraded_safely=bool(context.missing_fields),
    )
