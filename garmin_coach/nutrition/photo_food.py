from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from ._profile import detect_allergen_conflicts, nutrition_context_from_user


@dataclass(slots=True)
class EstimatedMacros:
    calories: int | None = None
    protein_g: int | None = None
    carbs_g: int | None = None
    fat_g: int | None = None


@dataclass(slots=True)
class FoodAnalysis:
    items_detected: list[str]
    estimated_macros: EstimatedMacros
    confidence: str
    coaching_note: str
    allergen_warning: str | None = None
    structured_only: bool = True
    requires_confirmation: bool = False
    authoritative: bool = False


AnalyzerClient = Callable[[bytes, Any], Awaitable[dict[str, Any]] | dict[str, Any]]


class FoodPhotoAnalyzer:
    def __init__(self, client: AnalyzerClient):
        self.client = client

    async def analyze(self, photo: bytes, user: Any) -> FoodAnalysis:
        raw = self.client(photo, user)
        if inspect.isawaitable(raw):
            raw = await raw

        items = [str(item) for item in raw.get("items", raw.get("items_detected", []))]
        macros = raw.get("estimated_macros", {}) or {}
        confidence = str(raw.get("confidence", "low") or "low").lower()
        context = nutrition_context_from_user(user)
        conflicts = detect_allergen_conflicts(items, context)
        warning = None
        if conflicts:
            warning = f"Possible restriction conflict detected: {', '.join(conflicts)}"

        requires_confirmation = confidence == "low"
        note = str(raw.get("coaching_note", "") or "")
        if requires_confirmation:
            note = (note + " 정확하지 않을 수 있으니 확인이 필요합니다.").strip()

        return FoodAnalysis(
            items_detected=items,
            estimated_macros=EstimatedMacros(
                calories=macros.get("calories"),
                protein_g=macros.get("protein_g"),
                carbs_g=macros.get("carbs_g"),
                fat_g=macros.get("fat_g"),
            ),
            confidence=confidence,
            coaching_note=note,
            allergen_warning=warning,
            requires_confirmation=requires_confirmation,
            authoritative=confidence in {"medium", "high"},
        )
