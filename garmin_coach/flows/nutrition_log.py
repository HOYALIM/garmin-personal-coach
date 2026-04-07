"""Nutrition logging flow — text or photo-based meal recording.

Can be triggered from evening check-in, post-workout, or /nutrition command.
Channel-agnostic: uses CoachingPort only.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from garmin_coach.ports import CoachingPort, Option

logger = logging.getLogger(__name__)


class FoodPhotoAnalyzer(Protocol):
    """Provided by S4 — food photo analysis via Vision LLM."""
    async def analyze(self, user_id: str, photo: bytes) -> dict[str, Any]: ...

class NutritionStorage(Protocol):
    """Provided by S1 storage — save nutrition log entries."""
    async def save_meal(self, user_id: str, meal: dict[str, Any]) -> None: ...

class DailyNutritionProvider(Protocol):
    """Provided by S4 — today's nutrition guide."""
    async def get_daily_guide(self, user_id: str) -> dict[str, Any]: ...


class NutritionLogFlow:
    """Handles meal logging via text or photo.

    Steps:
    1. Ask input method (text / photo / skip)
    2. Text → record directly
    3. Photo → S4 analyzer → show estimated macros → confirm/edit
    4. Save to storage
    """

    def __init__(
        self,
        port: CoachingPort,
        photo_analyzer: FoodPhotoAnalyzer | None = None,
        storage: NutritionStorage | None = None,
        nutrition_guide: DailyNutritionProvider | None = None,
    ) -> None:
        self.port = port
        self.photo_analyzer = photo_analyzer
        self.storage = storage
        self.nutrition_guide = nutrition_guide

    async def execute(self, user_id: str) -> None:
        """Run the nutrition logging flow."""
        method = await self.port.request_select(
            user_id,
            "📝 식사 기록 방법을 선택하세요:",
            [
                Option("📝 텍스트 입력", "text", "📝"),
                Option("📸 사진 촬영", "photo", "📸"),
                Option("⏭️ 건너뛰기", "skip", "⏭️"),
            ],
        )

        if method == "skip":
            await self.port.send_message(user_id, "⏭️ 건너뛰었습니다.")
            return

        meal: dict[str, Any] = {}

        if method == "text":
            meal = await self._log_by_text(user_id)
        elif method == "photo":
            meal = await self._log_by_photo(user_id)

        if meal and self.storage:
            try:
                await self.storage.save_meal(user_id, meal)
                await self.port.send_message(user_id, "✅ 식사 기록이 저장되었습니다!")
            except Exception:
                logger.exception("Failed to save meal for user %s", user_id)
                await self.port.send_message(user_id, "⚠️ 저장 중 오류가 발생했습니다. 다시 시도해주세요.")
        elif meal:
            await self.port.send_message(user_id, "✅ 식사 기록 완료!")

    async def execute_daily_guide(self, user_id: str) -> None:
        """Show today's nutrition guide (/nutrition command)."""
        if not self.nutrition_guide:
            await self.port.send_message(
                user_id, "🍎 영양 가이드가 아직 설정되지 않았습니다."
            )
            return
        try:
            guide = await self.nutrition_guide.get_daily_guide(user_id)
            await self.port.send_message(user_id, self._format_guide(guide))
        except Exception:
            logger.exception("Failed to get nutrition guide for user %s", user_id)
            await self.port.send_message(user_id, "⚠️ 영양 가이드를 불러오지 못했습니다.")

    async def _log_by_text(self, user_id: str) -> dict[str, Any]:
        description = await self.port.request_text(
            user_id,
            '📝 무엇을 먹었는지 입력해주세요.\n예: "닭가슴살 200g, 밥 한 공기, 샐러드"',
        )
        return {"type": "text", "description": description}

    async def _log_by_photo(self, user_id: str) -> dict[str, Any]:
        photo = await self.port.request_photo(
            user_id, "📸 식단 사진을 보내주세요."
        )
        if not photo:
            await self.port.send_message(user_id, "사진을 받지 못했습니다.")
            return {}

        # Analyze with Vision LLM
        if self.photo_analyzer:
            try:
                await self.port.send_message(user_id, "🔍 분석 중...")
                analysis = await self.photo_analyzer.analyze(user_id, photo)
                return await self._confirm_analysis(user_id, analysis, photo)
            except Exception:
                logger.exception("Photo analysis failed for user %s", user_id)
                await self.port.send_message(
                    user_id, "⚠️ 사진 분석에 실패했습니다. 텍스트로 입력해주세요."
                )
                return await self._log_by_text(user_id)
        else:
            await self.port.send_message(
                user_id, "📸 사진이 기록되었습니다. (자동 분석은 아직 준비 중입니다)"
            )
            return {"type": "photo", "has_photo": True}

    async def _confirm_analysis(
        self, user_id: str, analysis: dict[str, Any], photo: bytes
    ) -> dict[str, Any]:
        macros = analysis.get("estimated_macros", {})
        items = analysis.get("items_detected", [])

        lines = ["📊 분석 결과:"]
        if items:
            lines.append(f"감지된 음식: {', '.join(items)}")
        if macros:
            lines.append(f"- 칼로리: ~{macros.get('calories', '?')}kcal")
            lines.append(f"- 단백질: ~{macros.get('protein_g', '?')}g")
            lines.append(f"- 탄수화물: ~{macros.get('carbs_g', '?')}g")
            lines.append(f"- 지방: ~{macros.get('fat_g', '?')}g")
        note = analysis.get("coaching_note")
        if note:
            lines.append(f"\n💬 {note}")

        confirm = await self.port.request_select(
            user_id,
            "\n".join(lines) + "\n\n이 분석이 맞나요?",
            [
                Option("네, 저장", "confirm"),
                Option("수정할게요", "edit"),
            ],
        )

        if confirm == "edit":
            description = await self.port.request_text(
                user_id, "수정할 내용을 입력해주세요:"
            )
            return {"type": "photo_edited", "original_analysis": analysis, "edited": description, "has_photo": True}

        return {"type": "photo_analyzed", "analysis": analysis, "has_photo": True}

    def _format_guide(self, guide: dict[str, Any]) -> str:
        lines = ["🍎 오늘의 영양 가이드\n"]
        session = guide.get("session_type", "")
        if session:
            lines.append(f"오늘 세션: {session}\n")

        macros = guide.get("macros", {})
        if macros:
            lines.append("📊 권장 매크로:")
            carbs = macros.get("carbs_g")
            if carbs:
                lines.append(f"- 탄수화물: {carbs[0]:.0f}-{carbs[1]:.0f}g")
            protein = macros.get("protein_g")
            if protein:
                lines.append(f"- 단백질: {protein[0]:.0f}-{protein[1]:.0f}g")
            fat = macros.get("fat_g")
            if fat:
                lines.append(f"- 지방: {fat[0]:.0f}g+")

        hydration = guide.get("hydration")
        if hydration:
            lines.append(f"\n💧 수분: {hydration}")

        return "\n".join(lines)
