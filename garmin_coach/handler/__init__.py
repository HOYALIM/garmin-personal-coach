"""Natural language message handler with real data and AI."""

import os
from typing import Optional

from garmin_coach.handler.intent import Intent, detect_intent
from garmin_coach.handler.templates import ResponseTemplate
from garmin_coach.training_load_manager import get_training_load_manager


def _load_config() -> dict:
    try:
        import yaml

        config_path = os.path.expanduser("~/.config/garmin_coach/config.yaml")
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
                return _normalize_config(config)
    except Exception:
        pass
    return {}


def _normalize_config(config: dict) -> dict:
    """Normalize config to unified format (support both legacy and ProfileManager format)."""
    if "profile" in config:
        return {
            "name": config["profile"].get("name", ""),
            "age": config["profile"].get("age", 30),
            "setup_complete": True,
            "garmin_connected": config.get("garmin", {}).get("connected", False),
            "ai": {
                "enabled": config.get("ai_coach", {}).get("enabled", False),
                "api_key": config.get("ai_coach", {}).get("api_key"),
                "tone": config.get("ai_coach", {}).get("tone", "encouraging"),
                "flexibility": config.get("ai_coach", {}).get("flexibility", "moderate"),
            },
            "profile": config.get("profile", {}),
        }
    return config


def _get_real_context() -> dict:
    context = {}

    config = _load_config()
    context["name"] = config.get("name", "Athlete")
    context["setup_complete"] = config.get("setup_complete", False)
    context["garmin_connected"] = config.get("garmin_connected", False)

    try:
        manager = get_training_load_manager()
        load_context = manager.get_context()
        context.update(load_context)

        if context.get("ctl", 0) == 0 and context.get("atl", 0) == 0:
            context["has_data"] = False
        else:
            context["has_data"] = True
    except Exception:
        context["ctl"] = 0
        context["atl"] = 0
        context["tsb"] = 0
        context["has_data"] = False

    return context


class MessageHandler:
    def __init__(self, config: dict = None, user_context: dict = None):
        self.config = config or _load_config()
        self.user_context = user_context or {}
        self.tone = self.config.get("ai", {}).get("tone", "encouraging")
        self.template = ResponseTemplate(self.tone)
        self._ai_coach = None

    def _init_ai_coach(self):
        if self._ai_coach is None:
            api_key = (
                self.config.get("ai", {}).get("api_key")
                or os.getenv("OPENAI_API_KEY")
                or os.getenv("ANTHROPIC_API_KEY")
            )
            if api_key:
                try:
                    from garmin_coach.ai_simple import AICoach

                    self._ai_coach = AICoach(api_key=api_key)
                except Exception:
                    self._ai_coach = None

    def handle(self, message: str) -> str:
        context = _get_real_context()
        context.update(self.user_context)
        intent = detect_intent(message)

        self._init_ai_coach()

        if self._ai_coach:
            return self._handle_with_ai(message, intent, context)

        return self._handle_with_rules(intent, message, context)

    def _handle_with_ai(self, message: str, intent: Intent, context: dict) -> str:
        try:
            response = self._ai_coach.generate_response(message, context)
            if response:
                return response
        except Exception:
            pass
        return self._handle_with_rules(intent, message, context)

    def _handle_with_rules(self, intent: Intent, message: str, context: dict) -> str:
        handlers = {
            Intent.WAKE_UP: lambda: self._handle_wake_up(context),
            Intent.WORKOUT_COMPLETE: lambda: self._handle_workout_complete(context),
            Intent.ASK_STATUS: lambda: self._handle_ask_status(context),
            Intent.ASK_PLAN: lambda: self._handle_ask_plan(context),
            Intent.ASK_HELP: lambda: self._handle_ask_help(context),
            Intent.ASK_NUTRITION: lambda: self._handle_ask_nutrition(context),
            Intent.SYMPTOM_REPORT: lambda: self._handle_symptom_report(message, context),
        }

        if intent in handlers:
            return handlers[intent]()

        return self._handle_unknown(context)

    def _handle_wake_up(self, context: dict) -> str:
        name = context.get("name", "")
        tsb = context.get("tsb", 0)
        has_data = context.get("has_data", False)

        if not has_data:
            return (
                f"Good morning{name and f', {name}'}! "
                "Welcome! Run 'garmin-coach setup' to get started, "
                "then connect your Garmin account."
            )

        status = self._get_form_status(tsb)
        greeting = f"Good morning{name and f', {name}'}!"

        return f"{greeting} Your TSB is {tsb:.1f}. {status}"

    def _handle_workout_complete(self, context: dict) -> str:
        tsb = context.get("tsb", 0)

        msg = "Great work today!"

        if tsb < -25:
            msg += " Recovery is crucial - take it easy tomorrow."
        elif tsb < -10:
            msg += " Good session. Listen to your body tomorrow."
        else:
            msg += " Keep building!"

        return msg

    def _handle_ask_status(self, context: dict) -> str:
        ctl = context.get("ctl", 0)
        atl = context.get("atl", 0)
        tsb = context.get("tsb", 0)
        has_data = context.get("has_data", False)

        if not has_data:
            return (
                "No training data yet. "
                "Connect your Garmin account or log workouts manually with 'garmin-coach log'."
            )

        form_desc = self._get_form_status(tsb)

        return f"📊 CTL: {ctl:.1f} | ATL: {atl:.1f} | TSB: {tsb:.1f}\n{form_desc}"

    def _handle_ask_plan(self, context: dict) -> str:
        tsb = context.get("tsb", 0)
        has_data = context.get("has_data", False)

        if not has_data:
            return "Set up your profile first with 'garmin-coach setup'."

        if tsb < -25:
            return "🛌 Rest day recommended. Your body needs recovery."
        elif tsb < -10:
            return "🚶 Easy day - active recovery or light Zone 2."
        elif tsb > 25:
            return "💪 Great day for high intensity training!"
        else:
            return "🏃 Steady training day. Zone 2 or moderate effort."

    def _handle_ask_help(self, context: dict) -> str:
        return (
            "I'm your coach! Try:\n"
            "• '컨디션 어때?' - Check your status\n"
            "• '오늘 일정' - See today's plan\n"
            "• '운동 끝' - Log a workout\n"
            "• '피곤해' - Report how you feel"
        )

    def _handle_ask_nutrition(self, context: dict) -> str:
        ctl = context.get("ctl", 0)

        if ctl > 50:
            return "High training load. Focus on protein (1.6-2g/kg) and carbs for recovery."
        elif ctl > 30:
            return "Moderate training. Balanced nutrition with carbs before workouts."
        else:
            return "Building base fitness. Focus on adequate protein and overall calories."

    def _handle_symptom_report(self, message: str, context: dict) -> str:
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["피곤", "tired", "fatigue", "졸리"]):
            return "Rest is training too. Consider a light day or active recovery."
        if any(w in msg_lower for w in ["아픔", "pain", "hurt", "ache"]):
            return "If pain persists, take it easy. Don't push through pain."
        return "How are you feeling? Tell me more so I can help."

    def _handle_unknown(self, context: dict) -> str:
        name = context.get("name", "")
        greeting = f"{name}, " if name else ""
        return f"{greeting}I'm your coach! Try '컨디션 어때?' or '오늘 일정' or '/help'"

    def _get_form_status(self, tsb: float) -> str:
        if tsb > 25:
            return "You're fresh and ready for high intensity! 💪"
        elif tsb > 10:
            return "You're in great training form! 🎯"
        elif tsb > -10:
            return "You're in the training sweet spot. ✅"
        elif tsb > -25:
            return "You're accumulating some fatigue. Consider recovery. ⚠️"
        else:
            return "High fatigue detected. Rest recommended! 🛑"


def process_message(message: str, user_context: dict = None) -> str:
    handler = MessageHandler(user_context=user_context)
    return handler.handle(message)
