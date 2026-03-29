"""Telegram bot for Garmin Personal Coach with conversation state."""

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

    async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        name = update.effective_user.first_name

        self.states.update(user_id, name=name, welcome_time=datetime.now().isoformat())

        await update.message.reply_text(
            f"안녕하세요, {name}! 🏃\n\n"
            f"당신의 퍼스널 코치입니다!\n\n"
            f"도움말: /help\n"
            f"컨디션: /status\n"
            f"일정: /plan\n"
            f"운동 기록: /log"
        )

    async def cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📚 사용 가능한 명령어:\n\n"
            "/start - 시작\n"
            "/help - 도움말\n"
            "/status - 오늘 컨디션 확인\n"
            "/plan - 오늘的训练 일정\n"
            "/log - 운동 기록하기\n"
            "/profile - 내 프로필\n"
            "/setup - 설정\n\n"
            "💬 또는 그냥 메시지를 보내세요!\n"
            "예: '오늘 컨디션 어때?' '운동 끝' '피곤해'"
        )

    async def cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            response = process_message("컨디션 어때?")
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Status command error: {e}")
            await update.message.reply_text("죄송합니다. 데이터를 불러오는데 문제가 발생했어요.")

    async def cmd_plan(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            response = process_message("오늘的训练")
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Plan command error: {e}")
            await update.message.reply_text("죄송합니다. 일정을 불러오는데 문제가 발생했어요.")

    async def cmd_profile(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            from garmin_coach.wizard import load_config

            config = load_config()

            name = config.get("name", "설정되지 않음")
            age = config.get("age", "?")
            sports = ", ".join(config.get("sports", [])) or "설정되지 않음"
            fitness = config.get("fitness_level", "?")

            response = (
                f"📋 내 프로필\n\n"
                f"이름: {name}\n"
                f"나이: {age}\n"
                f"종목: {sports}\n"
                f"피트니스: {fitness}\n\n"
                f"설정 변경: /setup"
            )
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Profile command error: {e}")
            await update.message.reply_text("프로필을 불러오는데 문제가 발생했어요.")

    async def cmd_setup(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "⚙️ 설정은 터미널에서 진행해주세요:\n\n"
            "pip install garmin-personal-coach\n"
            "garmin-coach setup\n\n"
            "설정이 완료되면 다시 /start 을 눌러주세요."
        )

    async def cmd_log_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.states.update(user_id, log_state="workout_type")

        await update.message.reply_text(
            "🏃 어떤 운동을 했나요?\n\n예: 런닝, 사이클링, 수영, 웨이트 등"
        )
        return self.ASK_WORKOUT_TYPE

    async def ask_workout_type(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        workout_type = update.message.text

        self.states.update(user_id, workout_type=workout_type, log_state="duration")
        await update.message.reply_text(f"✅ {workout_type} - 몇 분 했나요?")
        return self.ASK_DURATION

    async def ask_duration(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        duration = update.message.text

        self.states.update(user_id, duration=duration, log_state="feeling")
        await update.message.reply_text(f"✅ {duration}분 - 컨디션은 어때요? (1-5)")
        return self.ASK_FEELING

    async def ask_feeling(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        state = self.states.get(user_id)
        feeling = update.message.text

        workout_type = state.get("workout_type", "운동")
        duration = state.get("duration", "0")

        self.states.clear(user_id)

        message = f"운동 완료: {workout_type} {duration}분, 컨디션 {feeling}/5"
        try:
            response = process_message(message)
            await update.message.reply_text(f"✅ 기록 완료!\n\n{response}")
        except Exception as e:
            logger.error(f"Log error: {e}")
            await update.message.reply_text("✅ 기록 완료!")

        return ConversationHandler.END

    async def cmd_cancel(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.states.clear(user_id)
        await update.message.reply_text("취소했어요. 다른 명령어를 입력해주세요.")
        return ConversationHandler.END

    async def handle_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_message = update.message.text

        try:
            self.states.update(user_id, last_message=user_message)
            response = process_message(user_message)
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Message handling error: {e}")
            await update.message.reply_text(
                "죄송합니다. 일시적인 문제가 발생했어요. 다시 시도해주세요."
            )

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
