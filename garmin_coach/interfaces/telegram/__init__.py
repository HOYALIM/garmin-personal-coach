"""Telegram interface adapter for Garmin Personal Coach.

This package implements the Telegram-specific delivery channel:
- adapter.py: TelegramAdapter(CoachingPort) — the bridge
- keyboards.py: Reusable inline keyboard components
- renderer.py: Data → Telegram message formatting
- handlers.py: Command and callback routing
- scheduler.py: Automated message scheduling
"""

from garmin_coach.interfaces.telegram.adapter import TelegramAdapter
from garmin_coach.interfaces.telegram.handlers import TelegramHandlers
from garmin_coach.interfaces.telegram.scheduler import TelegramScheduler

__all__ = ["TelegramAdapter", "TelegramHandlers", "TelegramScheduler"]
