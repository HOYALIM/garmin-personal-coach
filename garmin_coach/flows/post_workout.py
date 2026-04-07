"""Post-workout flow — auto analysis + feedback collection.

Triggered when S1 sync detects a new activity.
Channel-agnostic: uses CoachingPort only.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

from garmin_coach.ports import Button, CoachingPort, Option

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class WorkoutAnalyzer(Protocol):
    """Provided by S5 — workout auto-analysis."""

    async def analyze(self, user_id: str, activity: dict[str, Any]) -> dict[str, Any]: ...


class RecoveryFuelProvider(Protocol):
    """Provided by S4 — post-workout nutrition advice."""

    async def get_advice(self, user_id: str, activity: dict[str, Any]) -> dict[str, Any]: ...


class FeedbackAggregator(Protocol):
    """Provided by S5 — feedback collection and aggregation."""

    async def save_feedback(
        self, user_id: str, activity_id: str, feedback: dict[str, Any]
    ) -> None: ...


class PostWorkoutFlow:
    """Handles the post-workout analysis and feedback collection.

    Steps:
    1. Auto-analyze the activity (S5)
    2. Get recovery nutrition advice (S4)
    3. Send analysis + nutrition to user
    4. Collect subjective feedback (RPE, feeling, conditional questions)
    5. Forward feedback to S5 aggregator
    """

    def __init__(
        self,
        port: CoachingPort,
        analyzer: WorkoutAnalyzer,
        recovery_fuel: RecoveryFuelProvider | None = None,
        feedback_agg: FeedbackAggregator | None = None,
    ) -> None:
        self.port = port
        self.analyzer = analyzer
        self.recovery_fuel = recovery_fuel
        self.feedback_agg = feedback_agg

    async def execute(self, user_id: str, activity: dict[str, Any] | Any) -> None:
        """Run the full post-workout flow."""
        activity = self._normalize_activity(activity)
        activity_id = activity.get("activity_id", "unknown")

        # 1. Auto-analysis
        try:
            analysis = await self.analyzer.analyze(user_id, activity)
        except Exception:
            logger.exception("Workout analysis failed for user %s", user_id)
            analysis = {}

        # 2. Recovery nutrition
        nutrition_text = ""
        if self.recovery_fuel:
            try:
                nutrition = await self.recovery_fuel.get_advice(user_id, activity)
                nutrition_text = self._format_nutrition(nutrition)
            except Exception:
                logger.debug("Recovery fuel advice unavailable for user %s", user_id)

        # 3. Send analysis
        message = self._format_analysis(activity, analysis)
        if nutrition_text:
            message += nutrition_text

        buttons = [
            Button(label="👍 먹었어요", callback_data="postworkout:ate"),
            Button(label="⏰ 나중에 먹을게요", callback_data="postworkout:later"),
            Button(label="📝 뭘 먹었는지 기록", callback_data="postworkout:log_food"),
        ]
        await self.port.send_message(user_id, message, buttons=buttons)

        # 4. Collect subjective feedback
        feedback = await self._collect_feedback(user_id, activity)

        # 5. Save feedback
        if self.feedback_agg and feedback:
            try:
                await self.feedback_agg.save_feedback(user_id, activity_id, feedback)
            except Exception:
                logger.exception("Failed to save feedback for user %s", user_id)

    async def _collect_feedback(self, user_id: str, activity: dict[str, Any]) -> dict[str, Any]:
        """Collect RPE, feeling, and conditional questions."""
        feedback: dict[str, Any] = {}

        # RPE
        rpe = await self.port.request_select(
            user_id,
            "📋 체감 강도 (RPE):",
            [
                Option("1-2 매우 쉬움", "1-2"),
                Option("3-4 쉬움", "3-4"),
                Option("5-6 보통", "5-6"),
                Option("7-8 힘듦", "7-8"),
                Option("9-10 극한", "9-10"),
            ],
        )
        feedback["rpe"] = rpe

        # Feeling
        feeling = await self.port.request_select(
            user_id,
            "전체적인 느낌:",
            [
                Option("좋았어요", "good", "😀"),
                Option("보통", "neutral", "😐"),
                Option("힘들었어요", "bad", "😫"),
                Option("어딘가 아파요", "pain", "🤕"),
            ],
        )
        feedback["feeling"] = feeling

        # Pain follow-up
        if feeling == "pain":
            feedback["pain_detail"] = await self._collect_pain_detail(user_id)

        # Conditional: interval/tempo completion
        activity_type = activity.get("type", "").lower()
        if activity_type in ("interval", "tempo"):
            completion = await self.port.request_select(
                user_id,
                "목표 세트를 모두 완료했나요?",
                [
                    Option("전부 완료", "full"),
                    Option("일부만", "partial"),
                    Option("못 했어요", "none"),
                ],
            )
            feedback["completion"] = completion

        # Conditional: long session (>90 min) nutrition
        duration = activity.get("duration_min", 0) or 0
        if duration > 90:
            nutrition_ok = await self.port.request_select(
                user_id,
                "운동 중 보급은 잘 했나요?",
                [
                    Option("잘 했어요", "good"),
                    Option("부족했어요", "insufficient"),
                    Option("위장 문제 있었어요", "gi_issue"),
                ],
            )
            feedback["during_nutrition"] = nutrition_ok

        # Optional free text
        await self.port.send_message(
            user_id,
            "💬 추가로 남기고 싶은 메모가 있으면 입력해주세요. (없으면 '없음')",
        )
        note = await self.port.request_text(user_id, "")
        if note and note.strip().lower() not in ("없음", "no", "skip", ""):
            feedback["note"] = note

        await self.port.send_message(user_id, "✅ 피드백 저장 완료! 수고하셨어요 💪")
        return feedback

    async def _collect_pain_detail(self, user_id: str) -> dict[str, Any]:
        body_part = await self.port.request_select(
            user_id,
            "⚠️ 어디가 불편한가요?",
            [
                Option("무릎", "knee"),
                Option("발목", "ankle"),
                Option("아킬레스", "achilles"),
                Option("허리", "back"),
                Option("햄스트링", "hamstring"),
                Option("기타", "other"),
            ],
        )
        severity = await self.port.request_select(
            user_id,
            "통증 정도:",
            [
                Option("약간 불편", "mild"),
                Option("꽤 아픔", "moderate"),
                Option("많이 아픔", "severe"),
            ],
        )

        await self.port.send_message(
            user_id,
            "💡 통증이 2일 이상 지속되면 전문의 상담을 권합니다.\n"
            "   다음 세션은 해당 부위에 부담이 가지 않는 운동으로 조정됩니다.",
        )

        return {"body_part": body_part, "severity": severity}

    def _format_analysis(self, activity: dict[str, Any], analysis: dict[str, Any]) -> str:
        act_type = activity.get("type", "운동")
        distance = activity.get("distance_km")
        duration = activity.get("duration_min")
        avg_hr = activity.get("avg_hr")

        lines = [f"🏃‍♂️ {act_type} 완료! 수고했어요.\n"]
        lines.append("📊 세션 분석:")

        parts = []
        if distance:
            parts.append(f"거리: {distance:.1f}km")
        if duration:
            h, m = divmod(int(duration), 60)
            parts.append(f"시간: {h}:{m:02d}" if h else f"시간: {m}분")
        if avg_hr:
            parts.append(f"평균 심박: {avg_hr}bpm")
        if parts:
            lines.append("- " + " | ".join(parts))

        # Analysis details from S5
        tss = analysis.get("tss")
        if tss:
            lines.append(f"- TSS: {tss}")
        te_aer = analysis.get("training_effect_aerobic")
        te_ana = analysis.get("training_effect_anaerobic")
        if te_aer or te_ana:
            lines.append(f"- Training Effect: 유산소 {te_aer or '?'} / 무산소 {te_ana or '?'}")

        coaching_notes = analysis.get("coaching_notes", "")
        if coaching_notes:
            lines.append(f"\n💬 {coaching_notes}")

        return "\n".join(lines)

    def _format_nutrition(self, nutrition: dict[str, Any]) -> str:
        lines = ["\n\n🍽️ 회복 영양 권장:"]
        timing = nutrition.get("timing", "지금부터 30분 이내")
        lines.append(f"{timing}에 아래 중 하나를 섭취하세요:")
        examples = nutrition.get("examples", [])
        for ex in examples[:4]:
            lines.append(f"- {ex}")
        rationale = nutrition.get("rationale")
        if rationale:
            lines.append(f"\n> {rationale}")
        return "\n".join(lines)

    def _normalize_activity(self, activity: dict[str, Any] | Any) -> dict[str, Any]:
        if isinstance(activity, dict):
            return activity
        if hasattr(activity, "to_dict"):
            result = activity.to_dict()
            if isinstance(result, dict):
                return result
        if hasattr(activity, "__dict__"):
            return {key: value for key, value in vars(activity).items() if not key.startswith("_")}
        return {}
