from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_WEIGHT_KG = 70.0
DEFAULT_HEIGHT_CM = 170.0
DEFAULT_AGE = 30
DEFAULT_SEX = "female"


@dataclass(slots=True)
class NutritionContext:
    weight_kg: float = DEFAULT_WEIGHT_KG
    height_cm: float = DEFAULT_HEIGHT_CM
    age: int = DEFAULT_AGE
    sex: str = DEFAULT_SEX
    weight_goal: str = "maintain"
    dietary_style: str = "omnivore"
    food_restrictions: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)
    goal_type: str = "endurance"
    missing_fields: list[str] = field(default_factory=list)


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _collect_list(*values: Any) -> list[str]:
    items: list[str] = []
    for value in values:
        if not value:
            continue
        if isinstance(value, str):
            items.append(value)
            continue
        for item in value:
            if item:
                items.append(str(item))
    return sorted({item.strip() for item in items if item and str(item).strip()})


def nutrition_context_from_user(user: Any, goal: str | None = None) -> NutritionContext:
    nutrition = _get_value(user, "nutrition", {}) or {}
    profile = _get_value(user, "profile", {}) or {}
    medical = _get_value(user, "medical", {}) or {}
    current_injuries = _get_value(medical, "current_injuries", []) or []

    weight = _get_value(user, "weight_kg", _get_value(profile, "weight_kg"))
    height = _get_value(user, "height_cm", _get_value(profile, "height_cm"))
    age = _get_value(user, "age", _get_value(profile, "age"))
    sex = _get_value(user, "sex", _get_value(profile, "sex"))

    missing_fields: list[str] = []
    if weight in (None, 0):
        missing_fields.append("weight_kg")
        weight = DEFAULT_WEIGHT_KG
    if height in (None, 0):
        missing_fields.append("height_cm")
        height = DEFAULT_HEIGHT_CM
    if age in (None, 0):
        missing_fields.append("age")
        age = DEFAULT_AGE
    if not sex:
        missing_fields.append("sex")
        sex = DEFAULT_SEX

    allergies = _collect_list(_get_value(nutrition, "allergies", []))
    restrictions = _collect_list(
        _get_value(nutrition, "food_restrictions", []),
        _get_value(nutrition, "dietary_restrictions", []),
    )
    weight_goal = str(_get_value(nutrition, "weight_goal", "maintain") or "maintain").lower()
    dietary_style = str(_get_value(nutrition, "dietary_style", "omnivore") or "omnivore").lower()

    inferred_goal = goal
    if not inferred_goal and current_injuries:
        inferred_goal = "rehab"
    if not inferred_goal and weight_goal == "lose":
        inferred_goal = "weight_loss"
    if not inferred_goal:
        inferred_goal = "endurance"

    return NutritionContext(
        weight_kg=float(weight),
        height_cm=float(height),
        age=int(age),
        sex=str(sex).lower(),
        weight_goal=weight_goal,
        dietary_style=dietary_style,
        food_restrictions=restrictions,
        allergies=allergies,
        goal_type=inferred_goal,
        missing_fields=missing_fields,
    )


FILTER_TOKENS: dict[str, tuple[str, ...]] = {
    "dairy": ("milk", "yogurt", "cheese", "cream", "초코우유", "우유", "그릭 요거트"),
    "gluten": ("toast", "bread", "bagel", "granola", "bar", "pasta", "밀"),
    "nuts": ("peanut", "almond", "nut", "peanut butter"),
    "soy": ("soy", "tofu", "tempeh", "두유", "두부", "템페"),
    "egg": ("egg", "eggs", "계란"),
    "shellfish": ("shrimp", "prawn", "shellfish", "새우"),
}

DIETARY_STYLE_FILTERS: dict[str, tuple[str, ...]] = {
    "vegan": (
        "honey",
        "egg",
        "milk",
        "yogurt",
        "cheese",
        "chicken",
        "beef",
        "pork",
        "fish",
        "greek yogurt",
        "초코우유",
        "우유",
        "닭",
    ),
    "vegetarian": ("chicken", "beef", "pork", "fish", "닭", "참치"),
}

SAFE_FALLBACK_EXAMPLES: tuple[str, ...] = (
    "바나나",
    "쌀밥 소량",
    "찐고구마",
    "잼 바른 글루텐프리 토스트",
    "두부 + 밥",
    "식물성 프로틴 쉐이크",
)


def filter_food_examples(
    examples: list[str], context: NutritionContext
) -> tuple[list[str], list[str]]:
    banned_tokens: list[str] = []
    for label in context.food_restrictions + context.allergies:
        lowered = label.lower()
        banned_tokens.extend(FILTER_TOKENS.get(lowered, (lowered,)))
    banned_tokens.extend(DIETARY_STYLE_FILTERS.get(context.dietary_style, ()))

    filtered: list[str] = []
    removed: list[str] = []
    seen: set[str] = set()
    for example in examples:
        lowered = example.lower()
        if any(token in lowered for token in banned_tokens):
            removed.append(example)
            continue
        if example not in seen:
            filtered.append(example)
            seen.add(example)

    if filtered:
        return filtered, removed

    fallback = []
    for example in SAFE_FALLBACK_EXAMPLES:
        lowered = example.lower()
        if any(token in lowered for token in banned_tokens):
            continue
        if example not in seen:
            fallback.append(example)
            seen.add(example)
    return fallback, removed


def detect_allergen_conflicts(items: list[str], context: NutritionContext) -> list[str]:
    conflicts: list[str] = []
    labels = context.food_restrictions + context.allergies
    for item in items:
        lowered = item.lower()
        for label in labels:
            label_lower = label.lower()
            tokens = FILTER_TOKENS.get(label_lower, (label_lower,))
            if any(token in lowered for token in tokens):
                conflicts.append(f"{item} ({label})")
                break
    return conflicts
