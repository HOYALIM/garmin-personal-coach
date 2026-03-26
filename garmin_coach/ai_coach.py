"""AI coach engine — OpenCode OMO integration + rule-based fallback."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from garmin_coach.profile_manager import (
    AICoachConfig,
    ProfileManager,
    TrainingZones,
    UserProfile,
)
from garmin_coach.training_load import FormCategory, LoadSnapshot


@dataclass
class CoachMessage:
    text: str
    timestamp: str
    source: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "timestamp": self.timestamp,
            "source": self.source,
            "context": self.context,
        }


@dataclass
class CoachContext:
    date: str
    user_profile: UserProfile
    load_snapshot: LoadSnapshot | None = None
    zones: TrainingZones | None = None
    recent_activities: list[dict[str, Any]] = field(default_factory=list)
    self_reported: dict[str, Any] = field(default_factory=dict)
    week_number: int = 1
    phase: str = "base"
    last_session: dict[str, Any] | None = None
    upcoming_session: dict[str, Any] | None = None


class AICoachEngine:
    """OMO subprocess with rule-based fallback."""

    def __init__(self, config: AICoachConfig | None = None) -> None:
        self._pm = ProfileManager()
        profile = self._pm.load()
        self._config = config or (profile.ai_coach if profile else AICoachConfig())
        self._omo_path = os.getenv("OMO_PATH", "omo")
        self._conversation_history: list[CoachMessage] = []

    @property
    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                [self._omo_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def ask(
        self, ctx: CoachContext, question: str, mode: str = "advice"
    ) -> CoachMessage:
        if self._config.enabled and self.is_available:
            return self._omo_ask(ctx, question, mode)
        return self._rule_based_ask(ctx, question, mode)

    def daily_evening_advice(self, ctx: CoachContext) -> CoachMessage:
        prompt = self._build_evening_prompt(ctx)
        return self.ask(ctx, prompt, mode="evening_advice")

    def weekly_review_advice(self, ctx: CoachContext) -> CoachMessage:
        prompt = self._build_weekly_prompt(ctx)
        return self.ask(ctx, prompt, mode="weekly_review")

    def plan_adjustment_advice(self, ctx: CoachContext, reason: str) -> CoachMessage:
        prompt = (
            f"The user's data suggests a plan adjustment is needed.\n"
            f"Reason: {reason}\n"
            f"Current form: {ctx.load_snapshot.form.value if ctx.load_snapshot else 'unknown'}\n"
            f"Should I adjust the training plan? Provide specific recommendations."
        )
        return self.ask(ctx, prompt, mode="plan_adjustment")

    def _omo_ask(self, ctx: CoachContext, question: str, mode: str) -> CoachMessage:
        """Ask AI coach a question with full context."""
        if self._config.enabled and self.is_available:
            return self._omo_ask(ctx, question, mode)
        return self._rule_based_ask(ctx, question, mode)

    def daily_evening_advice(self, ctx: CoachContext) -> CoachMessage:
        """Generate personalized evening advice based on today's training + data."""
        prompt = self._build_evening_prompt(ctx)
        return self.ask(ctx, prompt, mode="evening_advice")

    def weekly_review_advice(self, ctx: CoachContext) -> CoachMessage:
        """Generate weekly review + next week preview."""
        prompt = self._build_weekly_prompt(ctx)
        return self.ask(ctx, prompt, mode="weekly_review")

    def plan_adjustment_advice(self, ctx: CoachContext, reason: str) -> CoachMessage:
        """Suggest plan adjustment based on user data."""
        prompt = (
            f"The user's data suggests a plan adjustment is needed.\n"
            f"Reason: {reason}\n"
            f"Current form: {ctx.load_snapshot.form.value if ctx.load_snapshot else 'unknown'}\n"
            f"Should I adjust the training plan? Provide specific recommendations."
        )
        return self.ask(ctx, prompt, mode="plan_adjustment")

    def _omo_ask(self, ctx: CoachContext, question: str, mode: str) -> CoachMessage:
        system_prompt = self._build_system_prompt(ctx, mode)
        context_json = self._context_to_json(ctx)

        full_prompt = f"""{system_prompt}

USER CONTEXT (JSON):
{context_json}

USER QUESTION:
{question}

Respond in the user's language (detect from context). Be specific and actionable."""

        try:
            result = subprocess.run(
                [
                    self._omo_path,
                    "--role",
                    "coach",
                    "--profile",
                    self._pm.config_path,
                    "--context",
                    context_json,
                ],
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=30,
            )
            response_text = (
                result.stdout.strip()
                if result.returncode == 0
                else self._fallback_text(question, ctx)
            )
        except (subprocess.TimeoutExpired, Exception):
            response_text = self._fallback_text(question, ctx)

        msg = CoachMessage(
            text=response_text,
            timestamp=datetime.now().isoformat(),
            source="omo",
            context={"mode": mode, "ctx_date": ctx.date},
        )
        self._conversation_history.append(msg)
        return msg

    def _rule_based_ask(
        self, ctx: CoachContext, question: str, mode: str
    ) -> CoachMessage:
        text = self._fallback_text(question, ctx)
        msg = CoachMessage(
            text=text,
            timestamp=datetime.now().isoformat(),
            source="rule_based",
            context={"mode": mode},
        )
        self._conversation_history.append(msg)
        return msg

    def _build_system_prompt(self, ctx: CoachContext, mode: str) -> str:
        tones = {
            "encouraging": "Warm, supportive, celebrate progress.",
            "direct": "Straightforward, no fluff, clear instructions.",
            "analytical": "Data-driven, explain the 'why' behind recommendations.",
            "motivational": "High energy, push the user to exceed expectations.",
        }
        tone_instruction = tones.get(self._config.tone.value, tones["encouraging"])

        flexibility_rules = {
            "conservative": "Only suggest minor adjustments (≤10% volume change). Never change planned sessions.",
            "moderate": "You may adjust session intensity, swap similar sessions, and modify volume by up to 20%.",
            "flexible": "You may restructure entire weeks, change session types, and modify volume by up to 40%.",
        }
        flex = flexibility_rules.get(
            self._config.flexibility.value, flexibility_rules["moderate"]
        )

        return f"""You are a knowledgeable, science-based endurance sports coach.

Your coaching style: {tone_instruction}
Your flexibility: {flex}

Context: {mode} mode.
User profile, training zones, and recent data are provided below.
Answer the user's question directly. Be specific with numbers, paces, and times.
If you recommend a plan change, say exactly what to change."""

    def _build_evening_prompt(self, ctx: CoachContext) -> str:
        parts = [
            f"Generate personalized evening coaching advice for today ({ctx.date}).",
        ]

        if ctx.load_snapshot:
            form = ctx.load_snapshot.form.value
            tsb = ctx.load_snapshot.tsb
            parts.append(f"Current form: {form} (TSB={tsb:+.0f}).")

        if ctx.last_session:
            s = ctx.last_session
            parts.append(
                f"Today's session: {s.get('type', '?')} — "
                f"{s.get('distance_km', s.get('duration_min', '?'))} "
                f"{s.get('sport', '')}."
            )

        if ctx.self_reported:
            sr = ctx.self_reported
            parts.append(
                f"User reported: energy={sr.get('energy', '?')}/5, "
                f"legs={sr.get('legs', '?')}/5, sleep={sr.get('sleep_hours', '?')}h."
            )

        parts.append(
            "Provide: (1) tonight's recovery tips, "
            "(2) tomorrow's training preview, "
            "(3) any adjustments to the plan."
        )
        return "\n".join(parts)

    def _build_weekly_prompt(self, ctx: CoachContext) -> str:
        parts = [
            f"Generate a weekly review and next-week preview for week {ctx.week_number}.",
        ]

        if ctx.load_snapshot:
            parts.append(
                f"Load snapshot — CTL={ctx.load_snapshot.ctl:.0f}, "
                f"ATL={ctx.load_snapshot.atl:.0f}, "
                f"TSB={ctx.load_snapshot.tsb:.0f} ({ctx.load_snapshot.form.value})."
            )

        parts.append(
            "Provide: (1) this week's performance summary, "
            "(2) strengths and areas to improve, "
            "(3) recommended adjustments for next week, "
            "(4) nutrition and recovery tips for the coming week."
        )
        return "\n".join(parts)

    def _context_to_json(self, ctx: CoachContext) -> str:
        data = {
            "date": ctx.date,
            "user": ctx.user_profile.profile.name or "Athlete",
            "age": ctx.user_profile.profile.age,
            "sports": [s.value for s in ctx.user_profile.profile.sports],
            "primary_sport": ctx.user_profile.profile.primary_sport.value,
            "goal_event": ctx.user_profile.profile.goal_event,
            "fitness_level": ctx.user_profile.profile.fitness_level.value,
            "week_number": ctx.week_number,
            "phase": ctx.phase,
            "load_snapshot": ctx.load_snapshot.to_dict() if ctx.load_snapshot else None,
            "zones": ctx.zones.to_dict() if ctx.zones else None,
            "recent_activities": ctx.recent_activities[-5:],
            "self_reported": ctx.self_reported,
            "last_session": ctx.last_session,
            "ai_flexibility": self._config.flexibility.value,
            "ai_tone": self._config.tone.value,
        }
        return json.dumps(data, indent=2, default=str)

    def _fallback_text(self, question: str, ctx: CoachContext) -> str:
        if ctx.load_snapshot:
            form = ctx.load_snapshot.form
            tsb = ctx.load_snapshot.tsb
        else:
            form, tsb = FormCategory.PREPARED, 0.0

        form_messages = {
            FormCategory.FRESH: "You're well-rested and ready for a quality session.",
            FormCategory.PREPARED: "You're in good shape for training.",
            FormCategory.TIRED: "You're accumulating fatigue. Keep intensity low today.",
            FormCategory.EXCESSIVE: "High fatigue detected. Consider an easy day or rest.",
            FormCategory.FRESHNESS_RISK: "You've been resting too much. Time to build volume.",
        }

        lines = [
            f"📊 Form: {form.value} (TSB {tsb:+.0f})",
            form_messages.get(form, ""),
            "",
            "🔧 Rule-based advice (OMO AI unavailable):",
            self._rule_advice(ctx),
        ]
        return "\n".join(lines)

    def _rule_advice(self, ctx: CoachContext) -> str:
        lines = []
        if ctx.load_snapshot and ctx.load_snapshot.tsb < -25:
            lines.append("⚠️ High fatigue — avoid high-intensity sessions today.")
        if ctx.self_reported.get("energy", 3) <= 2:
            lines.append("⚠️ Low energy reported — consider an easy day.")
        if ctx.self_reported.get("sleep_hours", 8) < 6:
            lines.append("⚠️ Low sleep — prioritize recovery today.")
        if not lines:
            lines.append("✅ All metrics look good. Train as planned.")
        if ctx.upcoming_session:
            s = ctx.upcoming_session
            lines.append(f"📅 Tomorrow: {s.get('type', '?')} — {s.get('sport', '?')}")
        return "\n".join(lines)

    def format_message(self, msg: CoachMessage) -> str:
        icon = "🤖" if msg.source == "omo" else "⚙️"
        return f"{icon} AI Coach [{msg.source}]\n{msg.text}"
