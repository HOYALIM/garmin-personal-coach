"""Evening check-in flow — daily summary + meal logging prompt.

Triggered by scheduler at user-configured time (default 21:00).
Channel-agnostic: uses CoachingPort only.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from garmin_coach.ports import Button, CoachingPort

logger = logging.getLogger(__name__)


class DailySummaryProvider(Protocol):
    """Provided by S1 — daily activity/health summary."""
    async def get_daily_summary(self, user_id: str) -> dict[str, Any]: ...

class TomorrowPlanProvider(Protocol):
    """Provided by S1 — tomorrow's session plan."""
    async def get_tomorrow_plan(self, user_id: str) -> dict[str, Any] | None: ...


class EveningCheckinFlow:
    """Delivers the evening check-in summary.

    Steps:
    1. Fetch today's activity/health summary
    2. Send summary to user
    3. Prompt for meal logging
    4. Suggest bedtime based on tomorrow's plan
    """

    def __init__(
        self,
        port: CoachingPort,
        summary_provider: DailySummaryProvider,
        tomorrow_plan: TomorrowPlanProvider | None = None,
    ) -> None:
        self.port = port
        self.summary_provider = summary_provider
        self.tomorrow_plan = tomorrow_plan

    async def execute(self, user_id: str) -> None:
        # 1. Daily summary
        try:
            summary = await self.summary_provider.get_daily_summary(user_id)
        except Exception:
            logger.exception("Failed to get daily summary for user %s", user_id)
            summary = {}

        # 2. Send summary
        message = self._format_summary(summary)

        # 3. Tomorrow plan + bedtime suggestion
        tomorrow_text = ""
        if self.tomorrow_plan:
            try:
                plan = await self.tomorrow_plan.get_tomorrow_plan(user_id)
                if plan:
                    tomorrow_text = self._format_tomorrow(plan)
            except Exception:
                logger.debug("Tomorrow plan unavailable for user %s", user_id)

        if tomorrow_text:
            message += tomorrow_text

        # 4. Send with meal-log prompt
        buttons = [
            Button(label="📝 기록하기", callback_data="evening:log_meal"),
            Button(label="⏭️ 건너뛰기", callback_data="evening:skip"),
        ]
        await self.port.send_message(user_id, message, buttons=buttons)

    def _format_summary(self, summary: dict[str, Any]) -> str:
        lines = ["🌙 오늘 하루 수고했어요!\n", "📊 오늘 요약:"]

        workout = summary.get("workout")
        if workout:
            lines.append(f"- 운동: {workout} ✅")
        else:
            lines.append("- 운동: 없음 (휴식일)")

        cal = summary.get("active_calories")
        if cal:
            lines.append(f"- 활동 칼로리: {cal}kcal")
        steps = summary.get("steps")
        if steps:
            lines.append(f"- 걸음: {steps:,}보")
        stress = summary.get("stress_avg")
        if stress is not None:
            level = "낮음 ✅" if stress < 40 else ("보통" if stress < 60 else "높음 ⚠️")
            lines.append(f"- 스트레스: 평균 {stress} ({level})")

        lines.append("\n🍽️ 오늘 식사 기록하셨나요?")
        return "\n".join(lines)

    def _format_tomorrow(self, plan: dict[str, Any]) -> str:
        session = plan.get("session", "")
        bedtime = plan.get("recommended_bedtime", "")
        lines = []
        if session:
            lines.append(f"\n😴 내일 {session} 대비:")
        if bedtime:
            lines.append(f"취침 시간을 {bedtime} 이전으로 권장합니다.")
        return "\n".join(lines)
