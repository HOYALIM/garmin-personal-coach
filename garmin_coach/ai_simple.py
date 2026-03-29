"""Simple AI coach wrapper with API key support."""

import json
import os
from typing import Optional


class AICoach:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.provider = self._detect_provider()

    def _detect_provider(self) -> str:
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        return "none"

    def generate_response(self, message: str, context: dict) -> Optional[str]:
        if not self.api_key:
            return None

        system_prompt = self._build_system_prompt(context)
        user_prompt = self._build_user_prompt(message, context)

        if self.provider == "openai":
            return self._call_openai(system_prompt, user_prompt)
        elif self.provider == "anthropic":
            return self._call_anthropic(system_prompt, user_prompt)

        return None

    def _build_system_prompt(self, context: dict) -> str:
        name = context.get("name", "")
        name_str = f"User's name: {name}" if name else ""

        ctl = context.get("ctl", 0)
        atl = context.get("atl", 0)
        tsb = context.get("tsb", 0)
        activities = context.get("activities_today", 0)

        return f"""You are a knowledgeable, supportive endurance sports coach.

{name_str}
Current training metrics:
- CTL (42-day fitness): {ctl:.1f}
- ATL (7-day fatigue): {atl:.1f}
- TSB (form): {tsb:.1f}
- Activities today: {activities}

Coach the user in a warm, encouraging tone. Be specific with numbers and recommendations.
Keep responses concise (2-3 sentences for quick questions, up to 1 paragraph for detailed advice."""

    def _build_user_prompt(self, message: str, context: dict) -> str:
        tsb = context.get("tsb", 0)

        prompt = f"User said: {message}\n\n"

        if tsb < -25:
            prompt += (
                "Context: User is very fatigued (TSB < -25). Recommend rest or easy recovery.\n"
            )
        elif tsb < -10:
            prompt += "Context: User is accumulating fatigue. Suggest light training.\n"
        elif tsb > 25:
            prompt += "Context: User is fresh (TSB > +25). Can handle high intensity.\n"

        return prompt

    def _call_openai(self, system: str, user: str) -> Optional[str]:
        try:
            import openai

            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=500,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception:
            return None

    def _call_anthropic(self, system: str, user: str) -> Optional[str]:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text
        except Exception:
            return None
