import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import telegram
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        filters,
        ContextTypes,
        ConversationHandler,
    )

    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

from garmin_coach.handler import process_message
from garmin_coach._version import __version__
from garmin_coach.i18n import Locale, detect_locale, get_i18n


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DATA_DIR = Path.home() / ".config" / "garmin_coach"
STATE_DIR = DATA_DIR / "telegram_states"


def _ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)


class ConversationState:
    STATE_FILE = STATE_DIR / "conversations.json"

    def __init__(self):
        _ensure_dirs()
        self._states = self._load()

    def _load(self) -> dict:
        if self.STATE_FILE.exists():
            try:
                with open(self.STATE_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        try:
            with open(self.STATE_FILE, "w") as f:
                json.dump(self._states, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save conversation state: {e}")

    def get(self, user_id: int) -> dict:
        return self._states.get(str(user_id), {})

    def set(self, user_id: int, state: dict):
        self._states[str(user_id)] = state
        self._save()

    def update(self, user_id: int, **kwargs):
        state = self.get(user_id)
        state.update(kwargs)
        state["last_interaction"] = datetime.now().isoformat()
        self.set(user_id, state)

    def clear(self, user_id: int):
        if str(user_id) in self._states:
            del self._states[str(user_id)]
            self._save()


class CoachBot:
    (ASK_WORKOUT_TYPE, ASK_DURATION, ASK_FEELING) = range(100, 103)

    def __init__(self, token: Optional[str] = None):
        if not TELEGRAM_AVAILABLE:
            raise RuntimeError(
                "python-telegram-bot not installed. Run: pip install garmin-personal-coach[telegram]"
            )

        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("Telegram bot token required. Set TELEGRAM_BOT_TOKEN env var.")

        self._ensure_dirs()
        self.states = ConversationState()
        self.app = Application.builder().token(self.token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("log", self.cmd_log_start)],
            states={
                self.ASK_WORKOUT_TYPE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_workout_type)
                ],
                self.ASK_DURATION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_duration)
                ],
                self.ASK_FEELING: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_feeling)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cmd_cancel)],
        )

        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("plan", self.cmd_plan))
        self.app.add_handler(CommandHandler("setup", self.cmd_setup))
        self.app.add_handler(CommandHandler("profile", self.cmd_profile))
        self.app.add_handler(conv_handler)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    def _get_locale(self, update: Update) -> Locale:
        user = update.effective_user
        if user and user.language_code:
            code = user.language_code.split("-")[0].lower()
            if code in ("ko", "zh"):
                return Locale(code)
        return Locale.EN

    def _reply(self, update: Update, text: str):
        return update.message.reply_text(text)

    async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        name = update.effective_user.first_name
        locale = self._get_locale(update)

        self.states.update(
            user_id, name=name, locale=locale.value, welcome_time=datetime.now().isoformat()
        )

        i18n = get_i18n(locale)
        await self._reply(update, i18n.t("start.welcome").format(name=name))

    async def cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        locale = self._get_locale(update)
        i18n = get_i18n(locale)
        await self._reply(update, i18n.t("help.text"))

    async def cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            response = process_message(" 컨디션 어때?")
            await self._reply(update, response)
        except Exception as e:
            logger.error(f"Status command error: {e}")
            locale = self._get_locale(update)
            await self._reply(update, get_i18n(locale).t("error.status"))

    async def cmd_plan(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            response = process_message(" 오늘 일정")
            await self._reply(update, response)
        except Exception as e:
            logger.error(f"Plan command error: {e}")
            locale = self._get_locale(update)
            await self._reply(update, get_i18n(locale).t("error.plan"))

    async def cmd_profile(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            from garmin_coach.wizard import load_config

            config = load_config()
            locale = self._get_locale(update)
            i18n = get_i18n(locale)

            name = config.get("name", i18n.t("profile.not_set"))
            age = config.get("age", "?")
            sports = ", ".join(config.get("sports", [])) or i18n.t("profile.not_set")
            fitness = config.get("fitness_level", "?")

            response = (
                f"{i18n.t('profile.title')}\n\n"
                f"{i18n.t('profile.name')}: {name}\n"
                f"{i18n.t('profile.age')}: {age} {i18n.t('profile.years')}\n"
                f"{i18n.t('profile.sports')}: {sports}\n"
                f"{i18n.t('profile.fitness')}: {fitness}\n\n"
                f"설정 변경: /setup"
            )
            await self._reply(update, response)
        except Exception as e:
            logger.error(f"Profile command error: {e}")
            locale = self._get_locale(update)
            await self._reply(update, get_i18n(locale).t("error.profile"))

    async def cmd_setup(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        locale = self._get_locale(update)
        i18n = get_i18n(locale)
        await self._reply(update, i18n.t("setup.prompt"))

    async def cmd_log_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.states.update(user_id, log_state="workout_type")

        locale = self._get_locale(update)
        i18n = get_i18n(locale)
        await self._reply(update, i18n.t("log.workout_type"))
        return self.ASK_WORKOUT_TYPE

    async def ask_workout_type(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        workout_type = update.message.text
        locale = self._get_locale(update)

        self.states.update(user_id, workout_type=workout_type, log_state="duration")
        i18n = get_i18n(locale)
        await self._reply(update, i18n.t("log.duration").format(type=workout_type))
        return self.ASK_DURATION

    async def ask_duration(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        duration = update.message.text

        self.states.update(user_id, duration=duration, log_state="feeling")
        locale = self._get_locale(update)
        i18n = get_i18n(locale)
        await self._reply(update, i18n.t("log.feeling").format(duration=duration))
        return self.ASK_FEELING

    async def ask_feeling(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        state = self.states.get(user_id)
        feeling = update.message.text

        workout_type = state.get("workout_type", "Workout")
        duration = state.get("duration", "0")

        self.states.clear(user_id)

        message = f"Workout complete: {workout_type} {duration} min, feeling {feeling}/5"
        try:
            response = process_message(message)
            locale = self._get_locale(update)
            i18n = get_i18n(locale)
            await self._reply(
                update, i18n.t("log.complete_with_response").format(response=response)
            )
        except Exception as e:
            logger.error(f"Log error: {e}")
            locale = self._get_locale(update)
            await self._reply(update, get_i18n(locale).t("log.complete"))

        return ConversationHandler.END

    async def cmd_cancel(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.states.clear(user_id)
        locale = self._get_locale(update)
        await self._reply(update, get_i18n(locale).t("cancel"))
        return ConversationHandler.END

    async def handle_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_message = update.message.text

        try:
            self.states.update(user_id, last_message=user_message)
            response = process_message(user_message)
            await self._reply(update, response)
        except Exception as e:
            logger.error(f"Message handling error: {e}")
            locale = self._get_locale(update)
            await self._reply(update, get_i18n(locale).t("error.generic"))

    def run(self):
        logger.info("Coach bot starting...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Garmin Coach Telegram Bot")
    parser.add_argument("--token", help="Telegram bot token")
    parser.add_argument("--version", "-v", action="store_true", help="Show version")
    args = parser.parse_args()

    if args.version:
        print(f"garmin-coach-telegram {__version__}")
        return

    try:
        bot = CoachBot(token=args.token)
        bot.run()
    except Exception as e:
        logger.error(f"Bot error: {e}")
        raise


if __name__ == "__main__":
    main()
