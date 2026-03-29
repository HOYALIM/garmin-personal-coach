from typing import Dict, Any


TEMPLATES = {
    "encouraging": {
        "morning_greeting": "Good morning, {name}! Ready to crush today? Let's check how you're feeling.",
        "workout_complete": "Great work! You crushed it! Duration: {duration}min, Distance: {distance}km, Avg HR: {hr} bpm. Rest up!",
        "status": "Your form is {tsb:.1f}. CTL: {ctl:.1f}, ATL: {atl:.1f}. {form_description}",
        "plan": "Today's plan: {plan}. Let's do this!",
        "help": "You can tell me about your workout, ask about your status, or ask for help. Try saying '운동 끝' or '컨디션 어때?'",
        "nutrition": "For your activity today, focus on {carbs}g carbs and {protein}g protein. Hydrate with {water}ml water.",
        "symptom_fatigue": "Rest is training too. Consider a light day or active recovery. Listen to your body!",
        "symptom_pain": "If pain persists, take it easy. Don't push through pain — smart training beats hard training.",
        "symptom_generic": "How are you feeling? Tell me more so I can help you train smarter.",
        "default": "I'm here to help! Try telling me about your workout or ask '컨디션 어때?'",
    },
    "direct": {
        "morning_greeting": "Morning, {name}. Time to check in.",
        "workout_complete": "Done. {duration}min, {distance}km, {hr} bpm avg.",
        "status": "TSB: {tsb:.1f}. CTL: {ctl:.1f}, ATL: {atl:.1f}. {form_description}",
        "plan": "Today: {plan}.",
        "help": "Commands: '운동 끝' (workout done), '컨디션' (status), '오늘 일정' (plan).",
        "nutrition": "Target: {carbs}g carbs, {protein}g protein, {water}ml water.",
        "symptom_fatigue": "Reduce intensity today. Recovery matters.",
        "symptom_pain": "Stop if it hurts. Pain is a signal.",
        "symptom_generic": "What's wrong?",
        "default": "Say '운동 끝', '컨디션', or '오늘 일정'.",
    },
    "analytical": {
        "morning_greeting": "Good morning, {name}. Running diagnostics...",
        "workout_complete": "Workout logged. Duration: {duration}min, Distance: {distance}km, Avg HR: {hr} bpm. Load: {load}.",
        "status": "Training Stress Balance: {tsb:.1f}. Chronic Load: {ctl:.1f}, Acute Load: {atl:.1f}. {form_description}",
        "plan": "Plan: {plan}. Adjustments needed based on current TSB.",
        "help": "Available commands: '운동 끝', '컨디션', '오늘 일정', '영양'. Metrics tracked: CTL, ATL, TSB, TRIMP.",
        "nutrition": "Macronutrient targets for today: {carbs}g carbohydrates, {protein}g protein, {water}ml hydration.",
        "symptom_fatigue": "ATL elevated. Recommend recovery session or rest day to prevent overtraining.",
        "symptom_pain": "Injury risk detected. Suggest immediate rest and assessment.",
        "symptom_generic": "Please provide more detail about your symptoms for analysis.",
        "default": "Awaiting input. State your intent or ask for status.",
    },
}


FORM_DESCRIPTIONS = {
    "fresh": "You're fresh and ready for high intensity.",
    "optimal": "You're in the training sweet spot.",
    "tired": "You're accumulating fatigue. Consider recovery.",
    "overreaching": "High stress. Risk of overtraining.",
}


def get_form_description(tsb: float) -> str:
    if tsb > 25:
        return FORM_DESCRIPTIONS["fresh"]
    elif tsb > 10:
        return FORM_DESCRIPTIONS["optimal"]
    elif tsb > -10:
        return FORM_DESCRIPTIONS["optimal"]
    elif tsb > -25:
        return FORM_DESCRIPTIONS["tired"]
    else:
        return FORM_DESCRIPTIONS["overreaching"]


class ResponseTemplate:
    def __init__(self, tone: str = "encouraging"):
        self.tone = tone
        self._templates = TEMPLATES.get(tone, TEMPLATES["encouraging"])

    def get(self, key: str, **kwargs) -> str:
        template = self._templates.get(key, self._templates.get("default"))

        if "tsb" in kwargs or "ctl" in kwargs or "atl" in kwargs:
            tsb = kwargs.get("tsb", 0)
            kwargs["form_description"] = get_form_description(tsb)

        if "duration" not in kwargs:
            kwargs["duration"] = 0
        if "distance" not in kwargs:
            kwargs["distance"] = 0
        if "hr" not in kwargs:
            kwargs["hr"] = 0
        if "carbs" not in kwargs:
            kwargs["carbs"] = 0
        if "protein" not in kwargs:
            kwargs["protein"] = 0
        if "water" not in kwargs:
            kwargs["water"] = 0

        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
