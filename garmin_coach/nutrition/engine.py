from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from garmin_coach.models import SessionType

from .hydration import HydrationPlan, get_hydration_plan
from .macros import DailyMacros, calculate_daily_macros
from .photo_food import FoodAnalysis
from .recovery_fuel import RecoveryAdvice, get_recovery_advice
from .timing import (
    DuringWorkoutAdvice,
    PostWorkoutAdvice,
    PreWorkoutAdvice,
    get_during_advice,
    get_post_workout_advice,
    get_pre_workout_advice,
)


@dataclass(slots=True)
class DailyNutritionGuide:
    session_type: str
    macros: DailyMacros
    hydration: HydrationPlan
    pre_workout: PreWorkoutAdvice | None
    during_workout: DuringWorkoutAdvice
    post_workout: PostWorkoutAdvice

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_type": self.session_type,
            "macros": self.macros.to_dict(),
            "hydration": asdict(self.hydration),
            "pre_workout": asdict(self.pre_workout) if self.pre_workout else None,
            "during_workout": asdict(self.during_workout),
            "post_workout": asdict(self.post_workout),
        }


class NutritionEngine:
    def __init__(
        self,
        storage: Any | None = None,
        photo_analyzer: Any | None = None,
    ) -> None:
        self.storage = storage
        self.photo_analyzer = photo_analyzer

    async def get_today_guide(
        self,
        user: Any,
        today_session: SessionType | str,
        hours_until: float = 2.0,
        temp_celsius: float | None = None,
        duration_min: int = 75,
    ) -> DailyNutritionGuide:
        session = (
            today_session.value if isinstance(today_session, SessionType) else str(today_session)
        )
        session_enum = SessionType(session)
        macros = calculate_daily_macros(user, session_enum)
        hydration = get_hydration_plan(
            session_enum, duration_min=duration_min, temp_celsius=temp_celsius
        )
        pre = get_pre_workout_advice(hours_until, session_enum, user)
        during = get_during_advice(duration_min, session_enum)
        post = get_post_workout_advice(session_enum, user)
        return DailyNutritionGuide(
            session_type=session,
            macros=macros,
            hydration=hydration,
            pre_workout=pre,
            during_workout=during,
            post_workout=post,
        )

    async def get_pre_workout(
        self, user: Any, session: SessionType | str, hours_until: float
    ) -> PreWorkoutAdvice:
        return get_pre_workout_advice(hours_until, session, user)

    async def get_post_workout(self, user: Any, activity: Any) -> RecoveryAdvice:
        return get_recovery_advice(activity, user)

    async def analyze_food_photo(self, photo: bytes, user: Any) -> FoodAnalysis:
        if self.photo_analyzer is None:
            raise RuntimeError("photo_analyzer is required")
        return await self.photo_analyzer.analyze(photo, user)

    async def log_meal(self, user_id: str, meal_data: dict[str, Any]) -> str | None:
        status = str(meal_data.get("status", "confirmed"))
        if status in {"timeout", "cancelled"}:
            return None

        payload = dict(meal_data)
        analysis = payload.get("analysis")
        if analysis and isinstance(analysis, dict):
            confidence = str(analysis.get("confidence", "")).lower()
            if confidence == "low":
                payload["authoritative"] = False

        payload.setdefault("entry_date", date.today().isoformat())
        entry_id = str(
            payload.get("entry_id") or payload.get("meal_id") or self._build_entry_id(payload)
        )
        payload["entry_id"] = entry_id

        if self.storage is None:
            return entry_id
        if hasattr(self.storage, "save_nutrition_log"):
            self.storage.save_nutrition_log(user_id, entry_id, payload["entry_date"], payload)
            return entry_id
        save_meal = getattr(self.storage, "save_meal", None)
        if save_meal is None:
            raise RuntimeError("storage must provide save_nutrition_log or save_meal")
        result = save_meal(user_id, payload)
        if hasattr(result, "__await__"):
            await result
        return entry_id

    def _build_entry_id(self, payload: dict[str, Any]) -> str:
        canonical = dict(payload)
        canonical.pop("entry_id", None)
        canonical.pop("saved_at", None)
        encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, default=str).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()[:16]
