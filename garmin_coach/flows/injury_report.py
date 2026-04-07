"""Injury report flow — user reports pain/injury.

Triggered by /injury command or from post-workout pain feedback.
Channel-agnostic: uses CoachingPort only.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from garmin_coach.ports import CoachingPort, Option

logger = logging.getLogger(__name__)


class InjuryStorage(Protocol):
    """Provided by S3 profile manager — save injury to user profile."""
    async def save_injury(self, user_id: str, injury: dict[str, Any]) -> None: ...

class GuardrailNotifier(Protocol):
    """Provided by S1 — notify guardrails of new injury."""
    async def on_injury_reported(self, user_id: str, injury: dict[str, Any]) -> None: ...


class InjuryReportFlow:
    """Handles injury/pain reporting.

    Steps:
    1. Select body part
    2. Select severity
    3. Optional: additional description
    4. Save to user profile (S3)
    5. Notify guardrails (S1)
    6. Show safety message
    """

    def __init__(
        self,
        port: CoachingPort,
        injury_storage: InjuryStorage | None = None,
        guardrail_notifier: GuardrailNotifier | None = None,
    ) -> None:
        self.port = port
        self.injury_storage = injury_storage
        self.guardrail_notifier = guardrail_notifier

    async def execute(self, user_id: str) -> None:
        """Run the full injury report flow."""
        # 1. Body part
        body_part = await self.port.request_select(
            user_id,
            "🤕 어디가 불편한가요?",
            [
                Option("무릎", "knee"),
                Option("발목", "ankle"),
                Option("아킬레스", "achilles"),
                Option("허리", "back"),
                Option("햄스트링", "hamstring"),
                Option("종아리", "calf"),
                Option("발바닥(족저근막)", "plantar"),
                Option("어깨", "shoulder"),
                Option("기타", "other"),
            ],
        )

        if body_part == "other":
            body_part = await self.port.request_text(
                user_id, "부위를 입력해주세요:"
            )

        # 2. Severity
        severity = await self.port.request_select(
            user_id,
            "통증 정도:",
            [
                Option("약간 불편", "mild"),
                Option("꽤 아픔", "moderate"),
                Option("많이 아픔", "severe"),
            ],
        )

        # 3. Optional description
        description = await self.port.request_text(
            user_id,
            "추가 설명이 있으면 입력해주세요. (없으면 '없음')",
        )
        if description.strip().lower() in ("없음", "no", "skip", ""):
            description = ""

        injury = {
            "body_part": body_part,
            "severity": severity,
            "description": description,
        }

        # 4. Save to profile
        if self.injury_storage:
            try:
                await self.injury_storage.save_injury(user_id, injury)
            except Exception:
                logger.exception("Failed to save injury for user %s", user_id)

        # 5. Notify guardrails
        if self.guardrail_notifier:
            try:
                await self.guardrail_notifier.on_injury_reported(user_id, injury)
            except Exception:
                logger.exception("Failed to notify guardrails for user %s", user_id)

        # 6. Safety message
        severity_msg = {
            "mild": "가벼운 불편감이 기록되었습니다.",
            "moderate": "통증이 기록되었습니다. 주의가 필요합니다.",
            "severe": "심한 통증이 기록되었습니다. 운동을 중단하세요.",
        }.get(severity, "기록되었습니다.")

        await self.port.send_message(
            user_id,
            f"✅ 부상 보고가 저장되었습니다.\n"
            f"{severity_msg}\n\n"
            f"💡 통증이 2일 이상 지속되면 전문의 상담을 권합니다.\n"
            f"   다음 세션은 '{body_part}' 부위에 부담이 가지 않는 운동으로 조정됩니다.\n\n"
            f"⚠️ 이 서비스는 의학적 조언을 대체하지 않습니다.",
        )
