"""Telegram command and callback handlers.

Wires Telegram events to the appropriate flow or service.
This module is the ONLY place that knows about both Telegram and flows.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Protocol

from garmin_coach.interfaces.telegram.adapter import TelegramAdapter
from garmin_coach.interfaces.telegram import keyboards, renderer
from garmin_coach.ports import InputAbortReason, InputAborted, Option

logger = logging.getLogger(__name__)


def _load_telegram():
    telegram = importlib.import_module("telegram")
    telegram_ext = importlib.import_module("telegram.ext")
    return telegram, telegram_ext


class FlowRegistry(Protocol):
    """Registry providing access to all flow instances."""

    @property
    def morning_briefing(self) -> Any: ...
    @property
    def post_workout(self) -> Any: ...
    @property
    def evening_checkin(self) -> Any: ...
    @property
    def nutrition_log(self) -> Any: ...
    @property
    def injury_report(self) -> Any: ...
    @property
    def onboarding(self) -> Any: ...
    @property
    def settings(self) -> Any: ...
    @property
    def goals(self) -> Any: ...


class EngineProxy(Protocol):
    """Proxy to S1 engine for direct queries."""

    async def generate_weekly_plan(self, user_id: str) -> Any: ...
    async def answer_question(self, user_id: str, question: str) -> str: ...


class ReportGenerator(Protocol):
    """S5 report generation."""

    async def generate_weekly(self, user_id: str) -> Any: ...


class FeedbackCollector(Protocol):
    """S5 manual feedback."""

    async def collect_manual(self, user_id: str) -> None: ...


class PhotoRouter(Protocol):
    """Route photos to appropriate analyzer."""

    async def auto_detect_type(self, photo: bytes) -> str | None: ...
    async def analyze_workout(self, user_id: str, photo: bytes) -> dict[str, Any]: ...
    async def analyze_food(self, user_id: str, photo: bytes) -> dict[str, Any]: ...


class UserRegistry(Protocol):
    async def register_user(self, user_id: str) -> None: ...


class TelegramHandlers:
    """Registers all Telegram command and callback handlers.

    Usage:
        handlers = TelegramHandlers(adapter, flows, engine, ...)
        handlers.register(application)
    """

    def __init__(
        self,
        adapter: TelegramAdapter,
        flows: FlowRegistry | None = None,
        engine: EngineProxy | None = None,
        reports: ReportGenerator | None = None,
        feedback: FeedbackCollector | None = None,
        photo_router: PhotoRouter | None = None,
        user_registry: UserRegistry | None = None,
    ) -> None:
        self.adapter = adapter
        self.flows = flows
        self.engine = engine
        self.reports = reports
        self.feedback = feedback
        self.photo_router = photo_router
        self.user_registry = user_registry

    async def _run_locked(self, user_id: str, action: Any) -> None:
        lock = self.adapter.get_user_lock(user_id)
        async with lock:
            await action()

    def register(self, app: Any) -> None:
        """Register all handlers on the telegram Application."""
        _, telegram_ext = _load_telegram()

        # Command handlers
        commands = {
            "start": self._cmd_start,
            "today": self._cmd_today,
            "week": self._cmd_week,
            "report": self._cmd_report,
            "feedback": self._cmd_feedback,
            "nutrition": self._cmd_nutrition,
            "settings": self._cmd_settings,
            "goals": self._cmd_goals,
            "injury": self._cmd_injury,
            "help": self._cmd_help,
        }
        for cmd, handler in commands.items():
            app.add_handler(telegram_ext.CommandHandler(cmd, handler))

        # Callback query handler (inline keyboard responses)
        app.add_handler(telegram_ext.CallbackQueryHandler(self._on_callback))

        # Photo handler
        filters = telegram_ext.filters
        app.add_handler(telegram_ext.MessageHandler(filters.PHOTO, self._on_photo))

        # Free text handler (must be last)
        app.add_handler(telegram_ext.MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))

    async def _user_id(self, update: Any) -> str:
        user_id = str(update.effective_user.id)
        if self.user_registry:
            await self.user_registry.register_user(user_id)
        return user_id

    # -- Command handlers -----------------------------------------------

    async def _cmd_start(self, update: Any, ctx: Any) -> None:
        """Handle /start — trigger onboarding."""
        user_id = await self._user_id(update)
        scheduler = None
        if ctx and hasattr(ctx, "application") and ctx.application:
            scheduler = ctx.application.bot_data.get("stream2_scheduler")
        flows = self.flows
        if flows and flows.onboarding:
            try:
                await self._run_locked(user_id, lambda: flows.onboarding.execute(user_id))
            except Exception:
                logger.exception("/start failed for user %s", user_id)
                await update.message.reply_text(
                    "⚠️ 온보딩 시작 중 오류가 발생했습니다. 다시 시도해주세요."
                )
        else:
            await update.message.reply_text(
                "🏃 Garmin Personal Coach에 오신 것을 환영합니다!\n"
                "설정을 시작하려면 잠시만 기다려주세요."
            )
        if scheduler:
            await scheduler.schedule_for_user(user_id)

    async def _cmd_today(self, update: Any, ctx: Any) -> None:
        """Handle /today — show today's readiness + plan."""
        user_id = await self._user_id(update)
        flows = self.flows
        if flows and flows.morning_briefing:
            try:
                await self._run_locked(user_id, lambda: flows.morning_briefing.execute(user_id))
            except Exception:
                logger.exception("/today failed for user %s", user_id)
                await update.message.reply_text("⚠️ 오늘의 브리핑을 불러오지 못했습니다.")
        else:
            await update.message.reply_text("⚠️ 코칭 엔진이 아직 준비되지 않았습니다.")

    async def _cmd_week(self, update: Any, ctx: Any) -> None:
        """Handle /week — show weekly plan."""
        user_id = await self._user_id(update)
        engine = self.engine
        if engine:
            try:

                async def run_week() -> None:
                    plan = await engine.generate_weekly_plan(user_id)
                    text = renderer.render_weekly_plan(plan)
                    await self.adapter.send_message(user_id, text)

                await self._run_locked(user_id, run_week)
            except Exception:
                logger.exception("/week failed for user %s", user_id)
                await update.message.reply_text("⚠️ 주간 계획을 불러오지 못했습니다.")
        else:
            await update.message.reply_text("⚠️ 코칭 엔진이 아직 준비되지 않았습니다.")

    async def _cmd_report(self, update: Any, ctx: Any) -> None:
        """Handle /report — generate weekly report."""
        user_id = await self._user_id(update)
        reports = self.reports
        if reports:
            try:

                async def run_report() -> None:
                    report_data = await reports.generate_weekly(user_id)
                    for msg in renderer.render_weekly_report(report_data):
                        await self.adapter.send_message(user_id, msg)

                await self._run_locked(user_id, run_report)
            except Exception:
                logger.exception("/report failed for user %s", user_id)
                await update.message.reply_text("⚠️ 리포트 생성에 실패했습니다.")
        else:
            await update.message.reply_text("⚠️ 리포트 기능이 아직 준비되지 않았습니다.")

    async def _cmd_feedback(self, update: Any, ctx: Any) -> None:
        """Handle /feedback — manual feedback entry."""
        user_id = await self._user_id(update)
        feedback = self.feedback
        if feedback:
            try:
                await self._run_locked(user_id, lambda: feedback.collect_manual(user_id))
            except Exception:
                logger.exception("/feedback failed for user %s", user_id)
                await update.message.reply_text("⚠️ 피드백 입력에 실패했습니다.")
        else:
            await update.message.reply_text("⚠️ 피드백 기능이 아직 준비되지 않았습니다.")

    async def _cmd_nutrition(self, update: Any, ctx: Any) -> None:
        """Handle /nutrition — today's nutrition guide."""
        user_id = await self._user_id(update)
        flows = self.flows
        if flows and flows.nutrition_log:
            try:
                await self._run_locked(
                    user_id, lambda: flows.nutrition_log.execute_daily_guide(user_id)
                )
            except Exception:
                logger.exception("/nutrition failed for user %s", user_id)
                await update.message.reply_text("⚠️ 영양 가이드를 불러오지 못했습니다.")
        else:
            await update.message.reply_text("⚠️ 영양 기능이 아직 준비되지 않았습니다.")

    async def _cmd_settings(self, update: Any, ctx: Any) -> None:
        """Handle /settings — modify profile/settings."""
        user_id = await self._user_id(update)
        flows = self.flows
        if flows and flows.settings:
            try:
                await self._run_locked(user_id, lambda: flows.settings.execute(user_id))
            except Exception:
                logger.exception("/settings failed for user %s", user_id)
                await update.message.reply_text("⚠️ 설정 변경에 실패했습니다.")
        else:
            await update.message.reply_text("⚠️ 설정 기능이 아직 준비되지 않았습니다.")

    async def _cmd_goals(self, update: Any, ctx: Any) -> None:
        """Handle /goals — view/edit goals."""
        user_id = await self._user_id(update)
        flows = self.flows
        if flows and flows.goals:
            try:
                await self._run_locked(user_id, lambda: flows.goals.execute(user_id))
            except Exception:
                logger.exception("/goals failed for user %s", user_id)
                await update.message.reply_text("⚠️ 목표 설정에 실패했습니다.")
        else:
            await update.message.reply_text("⚠️ 목표 기능이 아직 준비되지 않았습니다.")

    async def _cmd_injury(self, update: Any, ctx: Any) -> None:
        """Handle /injury — report injury/pain."""
        user_id = await self._user_id(update)
        flows = self.flows
        if flows and flows.injury_report:
            try:
                await self._run_locked(user_id, lambda: flows.injury_report.execute(user_id))
            except Exception:
                logger.exception("/injury failed for user %s", user_id)
                await update.message.reply_text("⚠️ 부상 보고에 실패했습니다.")
        else:
            await update.message.reply_text("⚠️ 부상 보고 기능이 아직 준비되지 않았습니다.")

    async def _cmd_help(self, update: Any, ctx: Any) -> None:
        """Handle /help."""
        await update.message.reply_text(renderer.render_help())

    # -- Callback query handler -----------------------------------------

    async def _on_callback(self, update: Any, ctx: Any) -> None:
        """Handle inline keyboard button presses."""
        query = update.callback_query
        await query.answer()

        user_id = await self._user_id(update)
        raw_data = query.data or ""
        data = self.adapter.resolve_callback(raw_data)
        flows = self.flows

        # Route to appropriate flow based on prefix
        if data.startswith("morning:"):
            if flows and flows.morning_briefing:
                await self._run_locked(
                    user_id, lambda: flows.morning_briefing.handle_response(user_id, data)
                )
            return

        if data.startswith("evening:"):
            if data == "evening:log_meal" and flows and flows.nutrition_log:
                await self._run_locked(user_id, lambda: flows.nutrition_log.execute(user_id))
            return

        if data.startswith("postworkout:"):
            if data == "postworkout:ate":
                await self.adapter.send_message(user_id, "좋아요! 회복 영양까지 챙기셨네요 👏")
                return
            if data == "postworkout:later":
                await self.adapter.send_message(user_id, "알겠어요. 30분 안에는 꼭 보충해보세요 ⏰")
                return
            if data == "postworkout:log_food" and flows and flows.nutrition_log:
                await self._run_locked(user_id, lambda: flows.nutrition_log.execute(user_id))
            return

        if data.startswith("photo_type:"):
            # Photo type classification callback — deliver to pending input
            self.adapter.deliver_input(user_id, data)
            return

        # Generic: deliver to adapter's pending input
        self.adapter.deliver_input(user_id, data)

    # -- Photo handler --------------------------------------------------

    async def _on_photo(self, update: Any, ctx: Any) -> None:
        """Handle photo messages — auto-detect type or ask."""
        user_id = await self._user_id(update)
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        photo_data = bytes(photo_bytes)

        # Check if there's a pending photo request from a flow
        if self.adapter.deliver_input(user_id, photo_data):
            return

        await self._run_locked(
            user_id,
            lambda: self._route_unsolicited_photo(user_id, photo_data, update),
        )

    async def _route_unsolicited_photo(self, user_id: str, photo_data: bytes, update: Any) -> None:
        # Auto-detect photo type
        photo_type = None
        if self.photo_router:
            try:
                photo_type = await self.photo_router.auto_detect_type(photo_data)
            except Exception:
                logger.debug("Auto photo detection failed for user %s", user_id)

        if photo_type == "workout":
            await self._handle_workout_photo(user_id, photo_data, update)
        elif photo_type == "food":
            await self._handle_food_photo(user_id, photo_data, update)
        else:
            try:
                classification = await self.adapter.request_select(
                    user_id,
                    "📸 사진을 받았어요! 어떤 종류인가요?",
                    [
                        Option("📊 운동 캡쳐", "photo_type:workout"),
                        Option("🍽️ 식단 사진", "photo_type:food"),
                        Option("📸 기타", "photo_type:other"),
                    ],
                )
                if classification == "photo_type:workout":
                    await self._handle_workout_photo(user_id, photo_data, update)
                elif classification == "photo_type:food":
                    await self._handle_food_photo(user_id, photo_data, update)
                else:
                    await self.adapter.send_message(user_id, "📸 사진 분류를 건너뛰었어요.")
            except InputAborted as exc:
                if exc.reason == InputAbortReason.TIMEOUT:
                    await self.adapter.send_message(
                        user_id, "⏱️ 사진 분류 입력 시간이 초과되어 취소했어요."
                    )
                else:
                    await self.adapter.send_message(user_id, "⏹️ 사진 분류를 취소했어요.")

    async def _handle_workout_photo(self, user_id: str, photo: bytes, update: Any) -> None:
        if self.photo_router:
            try:
                await update.message.reply_text("🔍 운동 캡쳐 분석 중...")
                analysis = await self.photo_router.analyze_workout(user_id, photo)
                text = renderer.render_workout_analysis(analysis)
                await self.adapter.send_message(user_id, text)
            except Exception:
                logger.exception("Workout photo analysis failed for user %s", user_id)
                await update.message.reply_text("⚠️ 분석에 실패했습니다.")
        else:
            await update.message.reply_text("📊 운동 캡쳐가 기록되었습니다.")

    async def _handle_food_photo(self, user_id: str, photo: bytes, update: Any) -> None:
        if self.photo_router:
            try:
                await update.message.reply_text("🔍 식단 사진 분석 중...")
                analysis = await self.photo_router.analyze_food(user_id, photo)
                text = renderer.render_nutrition_advice(analysis)
                await self.adapter.send_message(user_id, text)
            except Exception:
                logger.exception("Food photo analysis failed for user %s", user_id)
                await update.message.reply_text("⚠️ 분석에 실패했습니다.")
        else:
            await update.message.reply_text("🍽️ 식단 사진이 기록되었습니다.")

    # -- Free text handler ----------------------------------------------

    async def _on_text(self, update: Any, ctx: Any) -> None:
        """Handle free text messages — deliver to pending input or engine."""
        user_id = await self._user_id(update)
        text = update.message.text or ""

        # Check if there's a pending text input request
        if self.adapter.deliver_input(user_id, text):
            return

        # Otherwise, treat as natural language query to engine
        engine = self.engine
        if engine:
            try:

                async def run_answer() -> None:
                    answer = await engine.answer_question(user_id, text)
                    await self.adapter.send_message(user_id, answer)

                await self._run_locked(user_id, run_answer)
            except Exception:
                logger.exception("Engine query failed for user %s", user_id)
                await update.message.reply_text("⚠️ 답변을 생성하지 못했습니다. 다시 시도해주세요.")
        else:
            await update.message.reply_text(
                "💬 자연어 질의 기능이 아직 준비 중입니다.\n명령어 목록은 /help 를 참조해주세요."
            )
