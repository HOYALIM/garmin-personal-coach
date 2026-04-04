import json
import importlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    importlib.import_module("telegram")
    importlib.import_module("telegram.ext")
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


@dataclass
class TelegramRuntimeConfig:
    mode: str = "polling"
    webhook_url: Optional[str] = None
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080
    webhook_path: str = "/telegram/webhook"
    webhook_secret: Optional[str] = None

    @classmethod
    def from_env(cls) -> "TelegramRuntimeConfig":
        return cls(
            mode=os.getenv("TELEGRAM_BOT_MODE", "polling").strip().lower() or "polling",
            webhook_url=os.getenv("TELEGRAM_WEBHOOK_URL") or None,
            webhook_host=os.getenv("TELEGRAM_WEBHOOK_HOST", "0.0.0.0"),
            webhook_port=int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8080")),
            webhook_path=os.getenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook"),
            webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET") or None,
        )

    def normalized_webhook_path(self) -> str:
        path = (self.webhook_path or "/telegram/webhook").strip() or "/telegram/webhook"
        return path if path.startswith("/") else f"/{path}"

    def resolved_webhook_url(self) -> Optional[str]:
        if not self.webhook_url:
            return None
        base = self.webhook_url.rstrip("/")
        path = self.normalized_webhook_path()
        if base.endswith(path):
            return base
        return f"{base}{path}"

    def validate(self) -> None:
        if self.mode not in {"polling", "webhook"}:
            raise ValueError(f"Unsupported Telegram bot mode: {self.mode}")
        if self.mode == "webhook" and not self.webhook_url:
            raise ValueError("TELEGRAM_WEBHOOK_URL is required when TELEGRAM_BOT_MODE=webhook")
        if self.mode == "webhook" and not self.webhook_secret:
            raise ValueError("TELEGRAM_WEBHOOK_SECRET is required when TELEGRAM_BOT_MODE=webhook")


def _ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_telegram_modules():
    telegram = importlib.import_module("telegram")
    telegram_ext = importlib.import_module("telegram.ext")
    return telegram, telegram_ext


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
            os.chmod(self.STATE_FILE, 0o600)
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

    def __init__(
        self, token: Optional[str] = None, runtime_config: Optional[TelegramRuntimeConfig] = None
    ):
        if not TELEGRAM_AVAILABLE:
            raise RuntimeError(
                "python-telegram-bot not installed. Run: pip install garmin-personal-coach[telegram]"
            )

        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("Telegram bot token required. Set TELEGRAM_BOT_TOKEN env var.")

        self.runtime_config = runtime_config or TelegramRuntimeConfig.from_env()
        self.runtime_config.validate()

        _ensure_dirs()
        self._telegram, self._telegram_ext = _load_telegram_modules()
        self.states = ConversationState()
        self.app = self._telegram_ext.Application.builder().token(self.token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        filters = self._telegram_ext.filters
        conv_handler = self._telegram_ext.ConversationHandler(
            entry_points=[self._telegram_ext.CommandHandler("log", self.cmd_log_start)],
            states={
                self.ASK_WORKOUT_TYPE: [
                    self._telegram_ext.MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.ask_workout_type
                    )
                ],
                self.ASK_DURATION: [
                    self._telegram_ext.MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.ask_duration
                    )
                ],
                self.ASK_FEELING: [
                    self._telegram_ext.MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.ask_feeling
                    )
                ],
            },
            fallbacks=[self._telegram_ext.CommandHandler("cancel", self.cmd_cancel)],
        )

        self.app.add_handler(self._telegram_ext.CommandHandler("start", self.cmd_start))
        self.app.add_handler(self._telegram_ext.CommandHandler("help", self.cmd_help))
        self.app.add_handler(self._telegram_ext.CommandHandler("status", self.cmd_status))
        self.app.add_handler(self._telegram_ext.CommandHandler("plan", self.cmd_plan))
        self.app.add_handler(self._telegram_ext.CommandHandler("setup", self.cmd_setup))
        self.app.add_handler(self._telegram_ext.CommandHandler("profile", self.cmd_profile))
        self.app.add_handler(conv_handler)
        self.app.add_handler(
            self._telegram_ext.MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    def _get_locale(self, update) -> Locale:
        user = update.effective_user
        if user and user.language_code:
            code = user.language_code.split("-")[0].lower()
            if code in ("ko", "zh"):
                return Locale(code)
        return Locale.EN

    def _reply(self, update, text: str):
        return update.message.reply_text(text)

    async def cmd_start(self, update, ctx):
        user_id = update.effective_user.id
        name = update.effective_user.first_name
        locale = self._get_locale(update)

        self.states.update(
            user_id, name=name, locale=locale.value, welcome_time=datetime.now().isoformat()
        )

        i18n = get_i18n(locale)
        await self._reply(update, i18n.t("start.welcome").format(name=name))
        logger.info(f"Telegram /start handled for user_id={user_id}")

    async def cmd_help(self, update, ctx):
        locale = self._get_locale(update)
        i18n = get_i18n(locale)
        await self._reply(update, i18n.t("help.text"))

    async def cmd_status(self, update, ctx):
        try:
            response = process_message(" 컨디션 어때?")
            await self._reply(update, response)
            user_id = update.effective_user.id if update.effective_user else "unknown"
            logger.info(f"Telegram /status handled for user_id={user_id}")
        except Exception as e:
            logger.error(f"Status command error: {e}")
            locale = self._get_locale(update)
            await self._reply(update, get_i18n(locale).t("error.status"))

    async def cmd_plan(self, update, ctx):
        try:
            response = process_message(" 오늘 일정")
            await self._reply(update, response)
        except Exception as e:
            logger.error(f"Plan command error: {e}")
            locale = self._get_locale(update)
            await self._reply(update, get_i18n(locale).t("error.plan"))

    async def cmd_profile(self, update, ctx):
        try:
            from garmin_coach.wizard import load_config

            config = load_config()
            locale = self._get_locale(update)
            i18n = get_i18n(locale)

            profile = config.get("profile", config)

            name = profile.get("name", i18n.t("profile.not_set"))
            age = profile.get("age", "?")
            sports = ", ".join(profile.get("sports", [])) or i18n.t("profile.not_set")
            fitness = profile.get("fitness_level", "?")

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

    async def cmd_setup(self, update, ctx):
        locale = self._get_locale(update)
        i18n = get_i18n(locale)
        await self._reply(update, i18n.t("setup.prompt"))

    async def cmd_log_start(self, update, ctx):
        user_id = update.effective_user.id
        self.states.update(user_id, log_state="workout_type")

        locale = self._get_locale(update)
        i18n = get_i18n(locale)
        await self._reply(update, i18n.t("log.workout_type"))
        return self.ASK_WORKOUT_TYPE

    async def ask_workout_type(self, update, ctx):
        user_id = update.effective_user.id
        workout_type = update.message.text
        locale = self._get_locale(update)

        self.states.update(user_id, workout_type=workout_type, log_state="duration")
        i18n = get_i18n(locale)
        await self._reply(update, i18n.t("log.duration").format(type=workout_type))
        return self.ASK_DURATION

    async def ask_duration(self, update, ctx):
        user_id = update.effective_user.id
        duration = update.message.text

        self.states.update(user_id, duration=duration, log_state="feeling")
        locale = self._get_locale(update)
        i18n = get_i18n(locale)
        await self._reply(update, i18n.t("log.feeling").format(duration=duration))
        return self.ASK_FEELING

    async def ask_feeling(self, update, ctx):
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

        return self._telegram_ext.ConversationHandler.END

    async def cmd_cancel(self, update, ctx):
        user_id = update.effective_user.id
        self.states.clear(user_id)
        locale = self._get_locale(update)
        await self._reply(update, get_i18n(locale).t("cancel"))
        return self._telegram_ext.ConversationHandler.END

    async def handle_message(self, update, ctx):
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
        logger.info(f"Coach bot starting in {self.runtime_config.mode} mode...")
        if self.runtime_config.mode == "webhook":
            self.app.run_webhook(
                listen=self.runtime_config.webhook_host,
                port=self.runtime_config.webhook_port,
                url_path=self.runtime_config.normalized_webhook_path().lstrip("/"),
                webhook_url=self.runtime_config.resolved_webhook_url(),
                secret_token=self.runtime_config.webhook_secret,
                allowed_updates=self._telegram.Update.ALL_TYPES,
                drop_pending_updates=True,
            )
            return

        self.app.run_polling(
            allowed_updates=self._telegram.Update.ALL_TYPES,
            drop_pending_updates=True,
        )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Garmin Coach Telegram Bot")
    parser.add_argument("--token", help="Telegram bot token")
    parser.add_argument("--mode", choices=["polling", "webhook"], help="Runtime mode override")
    parser.add_argument("--webhook-url", help="Public base URL for webhook mode")
    parser.add_argument("--webhook-host", help="Webhook listen host")
    parser.add_argument("--webhook-port", type=int, help="Webhook listen port")
    parser.add_argument("--webhook-path", help="Webhook path")
    parser.add_argument("--webhook-secret", help="Webhook secret token")
    parser.add_argument("--version", "-v", action="store_true", help="Show version")
    args = parser.parse_args()

    if args.version:
        print(f"garmin-coach-telegram {__version__}")
        return

    try:
        runtime_config = TelegramRuntimeConfig.from_env()
        if args.mode:
            runtime_config.mode = args.mode
        if args.webhook_url:
            runtime_config.webhook_url = args.webhook_url
        if args.webhook_host:
            runtime_config.webhook_host = args.webhook_host
        if args.webhook_port:
            runtime_config.webhook_port = args.webhook_port
        if args.webhook_path:
            runtime_config.webhook_path = args.webhook_path
        if args.webhook_secret:
            runtime_config.webhook_secret = args.webhook_secret

        bot = CoachBot(token=args.token, runtime_config=runtime_config)
        bot.run()
    except Exception as e:
        logger.error(f"Bot error: {e}")
        raise


if __name__ == "__main__":
    main()
