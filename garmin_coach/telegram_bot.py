import asyncio
import importlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    importlib.import_module("telegram")
    importlib.import_module("telegram.ext")
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

from garmin_coach._version import __version__
from garmin_coach.activity_fetch import fetch_morning_metrics, fetch_recent_activities
from garmin_coach.flows import (
    EveningCheckinFlow,
    InjuryReportFlow,
    MorningBriefingFlow,
    NutritionLogFlow,
    PostWorkoutFlow,
)
from garmin_coach.integrations.sync import SyncEventBus
from garmin_coach.interfaces.telegram.adapter import TelegramAdapter
from garmin_coach.interfaces.telegram.handlers import TelegramHandlers
from garmin_coach.interfaces.telegram.scheduler import TelegramScheduler
from garmin_coach.training_load_manager import get_training_load_manager
from garmin_coach.wizard import load_config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DATA_DIR = Path.home() / ".config" / "garmin_coach"
STATE_DIR = DATA_DIR / "telegram_states"
USER_FILE = STATE_DIR / "telegram_users.json"


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


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_telegram_modules():
    telegram = importlib.import_module("telegram")
    telegram_ext = importlib.import_module("telegram.ext")
    return telegram, telegram_ext


class TelegramUserRegistry:
    def __init__(self, file_path: Path = USER_FILE) -> None:
        _ensure_dirs()
        self.file_path = file_path
        self._user_ids = self._load()

    def _load(self) -> list[str]:
        if not self.file_path.exists():
            return []
        try:
            return [str(item) for item in json.loads(self.file_path.read_text())]
        except Exception:
            logger.exception("Failed to load Telegram user registry")
            return []

    def _save(self) -> None:
        self.file_path.write_text(json.dumps(sorted(set(self._user_ids)), indent=2))
        os.chmod(self.file_path, 0o600)

    async def register_user(self, user_id: str) -> None:
        user_id = str(user_id)
        if user_id not in self._user_ids:
            self._user_ids.append(user_id)
            self._save()

    async def get_all_user_ids(self) -> list[str]:
        return list(self._user_ids)


class _ScheduleConfigProvider:
    def __init__(self, registry: TelegramUserRegistry) -> None:
        self.registry = registry

    async def get_schedule_config(self, user_id: str) -> dict[str, Any]:
        config = load_config()
        schedule = config.get("schedule", {})
        return {
            "morning_time": schedule.get("morning_checkin", {}).get("time", "07:00"),
            "evening_time": schedule.get("evening_checkin", {}).get("time", "21:00"),
        }

    async def get_all_user_ids(self) -> list[str]:
        return await self.registry.get_all_user_ids()


class _MessageOnlyFlow:
    def __init__(self, adapter: TelegramAdapter, text: str) -> None:
        self.adapter = adapter
        self.text = text

    async def execute(self, user_id: str) -> None:
        await self.adapter.send_message(user_id, self.text)


class _RuntimeEngineProxy:
    async def generate_weekly_plan(self, user_id: str) -> dict[str, Any]:
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        calc = get_training_load_manager().calculator
        sessions = calc.get_sessions_in_range(monday, monday + timedelta(days=6))
        by_day = {session.date.isoformat(): session for session in sessions}
        days: list[dict[str, Any]] = []
        for offset in range(7):
            current = monday + timedelta(days=offset)
            session = by_day.get(current.isoformat())
            description = session.description if session else "회복 중심 또는 짧은 이지 세션"
            session_type = (
                getattr(getattr(session, "sport", None), "value", "easy") if session else "easy"
            )
            days.append(
                {
                    "date": current.isoformat(),
                    "description": description,
                    "session_type": session_type,
                }
            )
        context = get_training_load_manager().get_context()
        return {
            "days": days,
            "total_tss": context.get("ctl", 0) + context.get("atl", 0),
            "notes": "몸 상태에 따라 강도를 조절하세요.",
        }

    async def answer_question(self, user_id: str, question: str) -> str:
        context = get_training_load_manager().get_context()
        lowered = question.lower()
        if "ctl" in lowered or "atl" in lowered or "tsb" in lowered:
            return (
                f"현재 CTL {context.get('ctl', 0):.1f}, ATL {context.get('atl', 0):.1f}, "
                f"TSB {context.get('tsb', 0):.1f} 기준으로 보면 오늘은 회복과 강도 균형을 먼저 보시는 게 좋아요."
            )
        return "지금은 Telegram 코칭 경로가 새 스택으로 전환된 상태예요. /today, /week, /report, /nutrition, /injury 명령으로 바로 필요한 정보를 받으실 수 있어요."


class _RuntimeReportService:
    async def generate_weekly(self, user_id: str) -> dict[str, Any]:
        return self._generate_report(window_days=7, label="최근 7일")

    async def generate_monthly(self, user_id: str) -> dict[str, Any]:
        return self._generate_report(window_days=30, label="최근 30일")

    def _generate_report(self, window_days: int, label: str) -> dict[str, Any]:
        calc = get_training_load_manager().calculator
        end_date = date.today()
        start_date = end_date - timedelta(days=window_days - 1)
        sessions = calc.get_sessions_in_range(start_date, end_date)
        total_distance = 0.0
        total_hours = 0.0
        total_trimp = 0.0
        for session in sessions:
            total_hours += float(getattr(session, "duration_min", 0.0) or 0.0) / 60.0
            total_trimp += float(getattr(session, "trimp", 0.0) or 0.0)
        snapshot = calc.get_snapshot(end_date)
        coach_comment = (
            "회복 여유가 있어 계획을 소화할 수 있는 주간 흐름이에요."
            if snapshot.tsb > -10
            else "피로가 쌓여 있어 다음 주 초반 강도는 보수적으로 가져가세요."
        )
        return {
            "period": label,
            "summary": {
                "sessions": len(sessions),
                "total_distance_km": round(total_distance, 1),
                "total_time": f"{total_hours:.1f}h",
            },
            "training_load": {
                "ctl": snapshot.ctl,
                "atl": snapshot.atl,
                "tsb": snapshot.tsb,
                "ramp_rate": 0.0,
            },
            "recovery": {
                "avg_sleep": None,
                "avg_sleep_score": None,
                "hrv_trend": None,
                "avg_body_battery": None,
            },
            "coach_comment": coach_comment,
            "metadata": {"total_trimp": total_trimp},
        }


class _ReadinessProvider:
    async def get_readiness(self, user_id: str) -> dict[str, Any]:
        metrics = fetch_morning_metrics(date.today().isoformat())
        context = get_training_load_manager().get_context()
        score = metrics.get("training_readiness")
        if score is None:
            body_battery = metrics.get("body_battery") or 50
            sleep_hours = metrics.get("sleep_hours") or 6
            score = int(min(100, max(0, body_battery * 0.6 + sleep_hours * 5)))
        level = "green" if score >= 75 else "yellow" if score >= 55 else "red"
        return {
            "score": score,
            "level": level,
            "components": {
                "body_battery": metrics.get("body_battery"),
                "rhr": metrics.get("resting_hr"),
                "tsb": round(context.get("tsb", 0.0), 1),
                "sleep_score": int((metrics.get("sleep_hours") or 0) / 8 * 100)
                if metrics.get("sleep_hours")
                else None,
            },
        }


class _DailyCoachingProvider:
    async def generate_daily_coaching(
        self, user_id: str, readiness: dict[str, Any]
    ) -> dict[str, Any]:
        score = readiness.get("score", 50)
        tsb = readiness.get("components", {}).get("tsb", 0)
        if score < 45 or tsb < -20:
            return {
                "text": "회복 우선으로 짧은 조깅이나 휴식을 권장해요.",
                "session_type": "rest",
                "guardrail_reason": "피로 지표가 높습니다.",
            }
        if score < 70:
            return {
                "text": "계획은 유지하되 초반 10분은 아주 가볍게 시작하세요.",
                "session_type": "easy",
            }
        return {
            "text": "오늘은 계획한 세션을 진행해도 괜찮아요. 몸이 무겁다면 강도를 한 단계 낮추세요.",
            "session_type": "moderate",
        }


class _DailySummaryProvider:
    async def get_daily_summary(self, user_id: str) -> dict[str, Any]:
        today = date.today()
        activities = fetch_recent_activities(today)
        latest = activities[-1] if activities else None
        return {
            "workout": (latest.get("activity_name") or latest.get("type")) if latest else None,
            "active_calories": latest.get("calories") if latest else None,
            "steps": None,
            "stress_avg": None,
        }


class _TomorrowPlanProvider:
    async def get_tomorrow_plan(self, user_id: str) -> dict[str, Any]:
        tsb = get_training_load_manager().get_context().get("tsb", 0.0)
        session = "이지런" if tsb > -15 else "회복 세션"
        return {"session": session, "recommended_bedtime": "22:30"}


class _NutritionGuideProvider:
    async def get_daily_guide(self, user_id: str) -> dict[str, Any]:
        return {
            "session_type": "훈련일",
            "macros": {"carbs_g": (220, 320), "protein_g": (110, 140), "fat_g": (50,)},
            "hydration": "하루 전체로 2L 이상, 운동 전후 추가 보충",
        }


class _WorkoutAnalyzer:
    async def analyze(self, user_id: str, activity: dict[str, Any]) -> dict[str, Any]:
        return {
            "tss": round(float(activity.get("duration_min", 0) or 0) * 0.9, 1),
            "training_effect_aerobic": activity.get("training_effect_aerobic"),
            "training_effect_anaerobic": activity.get("training_effect_anaerobic"),
            "coaching_notes": "수분과 회복 영양을 먼저 챙기고, 통증이 있으면 /injury 로 바로 기록하세요.",
        }


class _RecoveryFuelProvider:
    async def get_advice(self, user_id: str, activity: dict[str, Any]) -> dict[str, Any]:
        duration = float(activity.get("duration_min", 0) or 0)
        examples = ["초코우유 + 바나나", "그릭요거트 + 그래놀라", "닭가슴살 샌드위치"]
        timing = "운동 후 30분 이내" if duration >= 45 else "운동 후 1시간 이내"
        return {
            "timing": timing,
            "examples": examples,
            "rationale": "탄수화물과 단백질을 함께 보충하면 회복에 유리합니다.",
        }


class _ManualFeedbackCollector:
    def __init__(self, adapter: TelegramAdapter) -> None:
        self.adapter = adapter

    async def collect_manual(self, user_id: str) -> None:
        note = await self.adapter.request_text(
            user_id, "📝 오늘 세션에 대한 한 줄 피드백을 남겨주세요."
        )
        if note:
            await self.adapter.send_message(user_id, "✅ 피드백을 기록했어요.")


class _PhotoRouter:
    async def auto_detect_type(self, photo: bytes) -> str | None:
        return None

    async def analyze_workout(self, user_id: str, photo: bytes) -> dict[str, Any]:
        return {
            "summary": "운동 캡쳐를 받았어요.",
            "comparison_to_recent": "최근 세션과 함께 비교해볼 수 있어요.",
            "coaching_notes": "기록을 확인하고 필요하면 /feedback 으로 주관적 피드백도 남겨주세요.",
        }

    async def analyze_food(self, user_id: str, photo: bytes) -> dict[str, Any]:
        return {
            "timing": "식사 기록으로 반영했어요.",
            "examples": ["탄수화물과 단백질 균형을 맞춰보세요."],
        }


class _InjuryStorage:
    async def save_injury(self, user_id: str, injury: dict[str, Any]) -> None:
        return None


class _GuardrailNotifier:
    async def on_injury_reported(self, user_id: str, injury: dict[str, Any]) -> None:
        return None


@dataclass
class _FlowRegistry:
    morning_briefing: Any
    post_workout: Any
    evening_checkin: Any
    nutrition_log: Any
    injury_report: Any
    onboarding: Any
    settings: Any
    goals: Any


def _build_flow_registry(adapter: TelegramAdapter) -> _FlowRegistry:
    nutrition_flow = NutritionLogFlow(
        port=adapter,
        storage=None,
        nutrition_guide=_NutritionGuideProvider(),
    )
    return _FlowRegistry(
        morning_briefing=MorningBriefingFlow(
            port=adapter,
            readiness=_ReadinessProvider(),
            coaching=_DailyCoachingProvider(),
            nutrition=None,
        ),
        post_workout=PostWorkoutFlow(
            port=adapter,
            analyzer=_WorkoutAnalyzer(),
            recovery_fuel=_RecoveryFuelProvider(),
            feedback_agg=None,
        ),
        evening_checkin=EveningCheckinFlow(
            port=adapter,
            summary_provider=_DailySummaryProvider(),
            tomorrow_plan=_TomorrowPlanProvider(),
        ),
        nutrition_log=nutrition_flow,
        injury_report=InjuryReportFlow(
            port=adapter,
            injury_storage=_InjuryStorage(),
            guardrail_notifier=_GuardrailNotifier(),
        ),
        onboarding=_MessageOnlyFlow(
            adapter,
            "👋 Telegram에서는 현재 설정 안내만 제공해요. 초기 설정은 CLI에서 `garmin-coach`를 실행한 뒤 다시 /today 로 시작해주세요.",
        ),
        settings=_MessageOnlyFlow(
            adapter,
            "⚙️ 설정 변경 UI는 아직 다른 스트림에서 마무리 중이에요. 현재는 `garmin-coach` CLI로 설정을 수정한 뒤 Telegram에서 다시 사용해주세요.",
        ),
        goals=_MessageOnlyFlow(
            adapter,
            "🎯 목표 수정 UI는 아직 다른 스트림과 통합 중이에요. 현재는 CLI 설정을 이용해주세요.",
        ),
    )


def _set_bot_commands(app: Any) -> None:
    async def _post_init(application: Any) -> None:
        telegram, _ = _load_telegram_modules()
        commands = [
            telegram.BotCommand("start", "온보딩 시작"),
            telegram.BotCommand("today", "오늘의 컨디션 + 계획"),
            telegram.BotCommand("week", "이번 주 계획 보기"),
            telegram.BotCommand("report", "즉시 주간 리포트 생성"),
            telegram.BotCommand("feedback", "수동 피드백 입력"),
            telegram.BotCommand("nutrition", "오늘의 영양 가이드"),
            telegram.BotCommand("settings", "프로필/설정 수정"),
            telegram.BotCommand("goals", "목표 확인/수정"),
            telegram.BotCommand("injury", "부상 보고"),
            telegram.BotCommand("help", "도움말"),
        ]
        await application.bot.set_my_commands(commands)

    app.post_init = _post_init


def _bind_sync_bus(app: Any, scheduler: TelegramScheduler, sync_bus: SyncEventBus) -> None:
    def _forward_activity(event: Any) -> None:
        create_task = getattr(app, "create_task", None)
        payload = getattr(event, "activity", event)
        user_id = getattr(event, "user_id", None)
        coroutine = scheduler.on_new_activity(payload, user_id=user_id)
        if callable(create_task):
            create_task(coroutine)
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        loop.create_task(coroutine)

    sync_bus.on_new_activity(_forward_activity)


def build_telegram_application(
    token: Optional[str] = None,
    runtime_config: Optional[TelegramRuntimeConfig] = None,
    *,
    sync_bus: SyncEventBus | None = None,
    adapter: TelegramAdapter | None = None,
    handlers: TelegramHandlers | None = None,
    scheduler: TelegramScheduler | None = None,
) -> Any:
    if not TELEGRAM_AVAILABLE:
        raise RuntimeError(
            "python-telegram-bot not installed. Run: pip install garmin-personal-coach[telegram]"
        )

    actual_token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not actual_token:
        raise ValueError("Telegram bot token required. Set TELEGRAM_BOT_TOKEN env var.")

    actual_runtime_config = runtime_config or TelegramRuntimeConfig.from_env()
    actual_runtime_config.validate()

    _ensure_dirs()
    _, telegram_ext = _load_telegram_modules()
    app = telegram_ext.Application.builder().token(actual_token).build()

    runtime_adapter = adapter or TelegramAdapter(app.bot)
    registry = TelegramUserRegistry()
    flow_registry = _build_flow_registry(runtime_adapter)
    report_service = _RuntimeReportService()
    runtime_handlers = handlers or TelegramHandlers(
        runtime_adapter,
        flows=flow_registry,
        engine=_RuntimeEngineProxy(),
        reports=report_service,
        feedback=_ManualFeedbackCollector(runtime_adapter),
        photo_router=_PhotoRouter(),
        user_registry=registry,
    )
    runtime_scheduler = scheduler or TelegramScheduler(
        flow_registry,
        user_config=_ScheduleConfigProvider(registry),
        delivery=runtime_adapter,
        reports=report_service,
    )

    runtime_handlers.register(app)
    runtime_scheduler.setup(app.job_queue)
    _set_bot_commands(app)
    _bind_sync_bus(app, runtime_scheduler, sync_bus or SyncEventBus())

    app.bot_data["stream2_adapter"] = runtime_adapter
    app.bot_data["stream2_handlers"] = runtime_handlers
    app.bot_data["stream2_scheduler"] = runtime_scheduler
    return app


def main() -> None:
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

    app = build_telegram_application(token=args.token, runtime_config=runtime_config)

    logger.info("Coach bot starting in %s mode...", runtime_config.mode)
    if runtime_config.mode == "webhook":
        telegram, _ = _load_telegram_modules()
        app.run_webhook(
            listen=runtime_config.webhook_host,
            port=runtime_config.webhook_port,
            url_path=runtime_config.normalized_webhook_path().lstrip("/"),
            webhook_url=runtime_config.resolved_webhook_url(),
            secret_token=runtime_config.webhook_secret,
            allowed_updates=telegram.Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        return

    telegram, _ = _load_telegram_modules()
    app.run_polling(
        allowed_updates=telegram.Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
