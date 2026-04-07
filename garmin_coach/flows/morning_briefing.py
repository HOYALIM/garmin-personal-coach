"""Morning briefing flow — daily readiness + coaching plan.

Triggered by scheduler at user-configured time (default 07:00).
Channel-agnostic: uses CoachingPort only.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

from garmin_coach.ports import Button, CoachingPort, Option

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ReadinessProvider(Protocol):
    """Provided by S1 engine — readiness score + health metrics."""
    async def get_readiness(self, user_id: str) -> dict[str, Any]: ...

class DailyCoachingProvider(Protocol):
    """Provided by S1 engine — daily coaching recommendation."""
    async def generate_daily_coaching(self, user_id: str, readiness: dict[str, Any]) -> dict[str, Any]: ...

class NutritionTimingProvider(Protocol):
    """Provided by S4 — pre-workout nutrition advice."""
    async def get_pre_workout_advice(self, user_id: str, session_type: str) -> dict[str, Any] | None: ...


class MorningBriefingFlow:
    """Delivers the daily morning briefing to the user.

    Steps:
    1. Fetch readiness score + health metrics from S1
    2. Generate daily coaching recommendation from S1
    3. Get pre-workout nutrition advice from S4 (if workout planned)
    4. Format and send briefing
    5. Handle user response (proceed / change / postpone)
    """

    def __init__(
        self,
        port: CoachingPort,
        readiness: ReadinessProvider,
        coaching: DailyCoachingProvider,
        nutrition: NutritionTimingProvider | None = None,
    ) -> None:
        self.port = port
        self.readiness = readiness
        self.coaching = coaching
        self.nutrition = nutrition

    async def execute(self, user_id: str) -> None:
        """Run the full morning briefing flow."""
        # 1. Fetch readiness
        try:
            readiness_data = await self.readiness.get_readiness(user_id)
        except Exception:
            logger.exception("Failed to fetch readiness for user %s", user_id)
            await self.port.send_message(
                user_id,
                "☀️ 좋은 아침이에요! 오늘 워치 데이터를 가져오지 못했어요.\n"
                "제한된 정보로 코칭을 제공합니다.",
            )
            readiness_data = {}

        # 2. Generate daily coaching
        try:
            coaching_data = await self.coaching.generate_daily_coaching(user_id, readiness_data)
        except Exception:
            logger.exception("Failed to generate coaching for user %s", user_id)
            coaching_data = {"text": "오늘 계획을 불러오지 못했습니다. /today 로 다시 시도해주세요."}

        # 3. Build briefing message
        message = self._format_briefing(readiness_data, coaching_data)

        # 4. Nutrition advice (if workout planned)
        session_type = coaching_data.get("session_type", "")
        if session_type and session_type.lower() not in ("rest", "off") and self.nutrition:
            try:
                nutrition_advice = await self.nutrition.get_pre_workout_advice(user_id, session_type)
                if nutrition_advice:
                    message += self._format_nutrition(nutrition_advice)
            except Exception:
                logger.debug("Nutrition advice unavailable for user %s", user_id)

        # 5. Send with action buttons
        buttons = [
            Button(label="✅ 계획대로", callback_data="morning:proceed"),
            Button(label="🔄 변경", callback_data="morning:change"),
            Button(label="⏭️ 내일로 미루기", callback_data="morning:postpone"),
        ]
        await self.port.send_message(user_id, message, buttons=buttons)

    async def handle_response(self, user_id: str, action: str) -> None:
        """Handle user's response to the morning briefing."""
        if action == "morning:proceed":
            await self.port.send_message(user_id, "👍 화이팅! 오늘도 좋은 훈련 되세요.")

        elif action == "morning:change":
            selected = await self.port.request_select(
                user_id,
                "오늘 어떤 세션으로 변경할까요?",
                [
                    Option("🏃 이지런", "easy", "🏃"),
                    Option("⚡ 인터벌", "interval", "⚡"),
                    Option("🏋️ 템포런", "tempo", "🏋️"),
                    Option("🛣️ 장거리", "long", "🛣️"),
                    Option("🧘 크로스트레이닝", "cross", "🧘"),
                    Option("😴 휴식", "rest", "😴"),
                ],
            )
            await self.port.send_message(
                user_id,
                f"✅ 오늘 세션을 '{selected}'으로 변경했습니다.",
            )

        elif action == "morning:postpone":
            await self.port.send_message(
                user_id,
                "⏭️ 오늘은 휴식일로 변경했습니다. 내일 다시 안내드릴게요.",
            )

    def _format_briefing(
        self, readiness: dict[str, Any], coaching: dict[str, Any]
    ) -> str:
        score = readiness.get("score", "?")
        level = readiness.get("level", "")
        level_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴", "critical": "🚨"}.get(
            level.lower(), "⚪"
        )

        lines = [f"☀️ 좋은 아침이에요! 오늘의 컨디션 브리핑:\n"]
        lines.append(f"🔋 Readiness Score: {score}/100 {level_emoji}")

        # Health component details
        components = readiness.get("components", {})
        if components:
            if "sleep_score" in components:
                v = components["sleep_score"]
                lines.append(f"- 수면: {v} {'✅' if v and v >= 70 else '⚠️'}")
            if "hrv_deviation_pct" in components:
                v = components["hrv_deviation_pct"]
                sign = "+" if v and v > 0 else ""
                lines.append(f"- HRV: {sign}{v}% {'✅' if v and v >= -10 else '⚠️'}")
            if "body_battery" in components:
                v = components["body_battery"]
                lines.append(f"- Body Battery: {v} {'✅' if v and v >= 50 else '⚠️'}")
            if "rhr" in components:
                v = components["rhr"]
                lines.append(f"- RHR: {v}bpm {'✅' if v else ''}")
            if "tsb" in components:
                v = components["tsb"]
                lines.append(f"- TSB: {v} {level_emoji}")

        # Coaching plan
        coaching_text = coaching.get("text", "")
        session = coaching.get("session_type", "")
        if session:
            lines.append(f"\n🏃 오늘 계획: {session}")
        if coaching_text:
            lines.append(f"→ {coaching_text}")

        # Guardrail notice
        guardrail_reason = coaching.get("guardrail_reason")
        if guardrail_reason:
            lines.append(f"\n⚠️ 코치가 계획을 조정했습니다:\n{guardrail_reason}")

        return "\n".join(lines)

    def _format_nutrition(self, advice: dict[str, Any]) -> str:
        lines = ["\n\n🍽️ 운동 전 식사 리마인더:"]
        desc = advice.get("description", "")
        if desc:
            lines.append(desc)
        examples = advice.get("examples", [])
        if examples:
            lines.append(f"(예: {', '.join(examples[:3])})")
        return "\n".join(lines)
