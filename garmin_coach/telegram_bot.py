import asyncio
import importlib
import json
import logging
import os
import uuid
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
from garmin_coach.activity_fetch import (
    safe_get_daily_summary,
)
from garmin_coach.adapters.garmin import GarminAdapter
from garmin_coach.engine.coaching import GarminCoachingEngine
from garmin_coach.engine.interfaces import CoachingContext
from garmin_coach.engine.readiness import ReadinessCalculator
from garmin_coach.feedback import FeedbackAggregatorService
from garmin_coach.flows import (
    EveningCheckinFlow,
    GoalsFlow,
    InjuryReportFlow,
    MorningBriefingFlow,
    NutritionLogFlow,
    OnboardingFlow,
    PostWorkoutFlow,
    SettingsFlow,
)
from garmin_coach.integrations.sync import GarminSyncService, SyncEventBus
from garmin_coach.interfaces.telegram.adapter import TelegramAdapter
from garmin_coach.interfaces.telegram.handlers import TelegramHandlers
from garmin_coach.interfaces.telegram.scheduler import TelegramScheduler
from garmin_coach.models import (
    ActivitySummary,
    BodyBatteryData,
    CoachingPreferences,
    GarminAuth,
    HealthMetrics,
    InjuryRecord,
    MedicalProfile,
    NutritionProfile,
    RHRData,
    SleepData,
    StravaAuth,
    TrainingGoal,
    TrainingLoad,
    TrainingReadinessData,
)
from garmin_coach.models import (
    FitnessLevel as EngineFitnessLevel,
)
from garmin_coach.models import (
    UserProfile as EngineUserProfile,
)
from garmin_coach.models.coaching import (
    CoachingResponse,
    SessionType,
    WeeklyPlan,
    WorkoutAnalysis,
)
from garmin_coach.models.feedback import (
    FeedbackCompletion,
    SessionFeedback,
)
from garmin_coach.models.health_metrics import ReadinessScore
from garmin_coach.models.reporting import (
    WeeklyRecoverySummary,
    WeeklyReport,
)
from garmin_coach.nutrition import (
    calculate_nutrition_targets,
    recommend_post_workout,
    recommend_pre_workout,
)
from garmin_coach.ports import InputAborted, InputAbortReason, Option
from garmin_coach.reports import MonthlyReportGenerator, WeeklyReportGenerator
from garmin_coach.services.user_profile import (
    GARTH_USER_DIR,
    ONBOARDING_PROGRESS_DIR,
    PROFILE_DIR,
)
from garmin_coach.services.user_profile import (
    UserProfileService as _UserProfileService,
)
from garmin_coach.services.user_profile import (
    scoped_garth_home as _scoped_garth_home,
)
from garmin_coach.storage.database import GarminCoachDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DATA_DIR = Path.home() / ".config" / "garmin_coach"
STATE_DIR = DATA_DIR / "telegram_states"
USER_FILE = STATE_DIR / "telegram_users.json"
INJURY_DIR = STATE_DIR / "injuries"
GUARDRAIL_DIR = STATE_DIR / "guardrails"
MORNING_PLAN_DIR = STATE_DIR / "morning_plans"
RUNTIME_DB = DATA_DIR / "telegram_runtime.db"


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
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    INJURY_DIR.mkdir(parents=True, exist_ok=True)
    GUARDRAIL_DIR.mkdir(parents=True, exist_ok=True)
    MORNING_PLAN_DIR.mkdir(parents=True, exist_ok=True)
    ONBOARDING_PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    GARTH_USER_DIR.mkdir(parents=True, exist_ok=True)


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
    def __init__(
        self, registry: TelegramUserRegistry, profile_service: "_UserProfileService"
    ) -> None:
        self.registry = registry
        self.profile_service = profile_service

    async def get_schedule_config(self, user_id: str) -> dict[str, Any]:
        return await self.profile_service.get_schedule_config(user_id)

    async def get_all_user_ids(self) -> list[str]:
        return await self.registry.get_all_user_ids()


class _RuntimeDataBridge:
    def __init__(self, profile_service: Any, database: GarminCoachDatabase) -> None:
        self.profile_service = profile_service
        self.database = database
        self.engine = GarminCoachingEngine()
        self.readiness_calc = ReadinessCalculator()
        self.feedback_service = FeedbackAggregatorService(database, GUARDRAIL_DIR)

    def load_engine_user(self, user_id: str) -> EngineUserProfile:
        profile = self.profile_service._load(user_id)
        if not profile:
            raise RuntimeError(f"Missing profile for user {user_id}")
        goal_date = profile.profile.goal_date or None
        target_date = date.fromisoformat(goal_date) if goal_date else None
        return EngineUserProfile(
            garmin_credentials=GarminAuth(
                email=profile.garmin.email or f"{user_id}@telegram.local",
                connected=profile.garmin.connected,
            ),
            birth_date=date.today() - timedelta(days=max(profile.profile.age, 18) * 365),
            sex=profile.profile.sex.value,
            height_cm=profile.profile.height_cm,
            weight_kg=profile.profile.weight_kg,
            goal=TrainingGoal(
                type=profile.profile.primary_sport.value,
                target_event=profile.profile.goal_event or None,
                target_date=target_date,
                weekly_volume_km=0.0,
            ),
            fitness_level=EngineFitnessLevel(
                level=profile.profile.fitness_level.value,
                weekly_avg_sessions=float(profile.profile.available_days),
            ),
            medical=MedicalProfile(
                cardiac_conditions=list(profile.medical.cardiac_conditions),
                hypertension=profile.medical.hypertension,
                diabetes=profile.medical.diabetes,
                respiratory=list(profile.medical.respiratory),
                current_injuries=self._merged_injuries(user_id, profile),
                beta_blocker=profile.medical.beta_blocker,
                notes=profile.medical.notes,
            ),
            nutrition=NutritionProfile(
                dietary_restrictions=list(profile.nutrition.food_restrictions),
                allergies=list(profile.nutrition.allergies),
                meal_pattern=profile.nutrition.meal_pattern,
                supplements=list(profile.nutrition.supplements),
                alcohol_frequency=profile.nutrition.alcohol_frequency,
            ),
            preferences=CoachingPreferences(
                tone=profile.ai_coach.tone.value,
                preferred_training_time=profile.preferences.preferred_training_time,
                cross_training_preferences=list(profile.preferences.cross_training_preferences),
                notification_frequency=profile.preferences.notification_frequency,
                units=profile.preferences.units,
                timezone=profile.preferences.timezone,
            ),
            sleep=None,
            strava_auth=StravaAuth(connected=profile.preferences.strava_connected),
        )

    def build_health_metrics(self, user_id: str, target_date: date | None = None) -> HealthMetrics:
        metric_date = target_date or date.today()
        payload = self.database.load_daily_health(user_id, metric_date.isoformat())
        if payload is None:
            self.refresh_user(user_id, metric_date)
            payload = self.database.load_daily_health(user_id, metric_date.isoformat()) or {}
        recent_activities = [
            self.to_activity_model(item)
            for item in self.database.list_recent_activities(user_id, limit=7)
        ]
        training_load_payload = payload.get("training_load") if isinstance(payload, dict) else None
        readiness_payload = payload.get("readiness") if isinstance(payload, dict) else None
        metrics = HealthMetrics(
            metric_date=metric_date,
            sleep=SleepData(score=self._sleep_score(payload)),
            body_battery=BodyBatteryData(morning_value=self._body_battery(payload)),
            rhr=RHRData(value_bpm=self._rhr(payload)),
            training_readiness=TrainingReadinessData(
                score=self._training_readiness(payload), level=None
            ),
            training_load=TrainingLoad(
                ctl=float((training_load_payload or {}).get("ctl", 0.0)),
                atl=float((training_load_payload or {}).get("atl", 0.0)),
                tsb=float((training_load_payload or {}).get("tsb", 0.0)),
                ramp_rate=float((training_load_payload or {}).get("ramp_rate", 0.0)),
                weekly_volume_km=sum(activity.distance_km or 0.0 for activity in recent_activities),
            ),
            recent_activities=recent_activities,
        )
        metrics.readiness = (
            ReadinessScore(
                score=int(readiness_payload.get("score", 50)),
                level=str(readiness_payload.get("level", "yellow")),
                components=readiness_payload.get("components", {}),
                component_weights=readiness_payload.get("component_weights", {}),
                confidence=str(readiness_payload.get("confidence", "medium")),
                reason=str(readiness_payload.get("reason", "")),
                input_snapshot=readiness_payload.get("input_snapshot", {}),
                limiting_factors=readiness_payload.get("limiting_factors", []),
            )
            if isinstance(readiness_payload, dict) and readiness_payload
            else self.readiness_calc.calculate(metrics)
        )
        return metrics

    def refresh_user(self, user_id: str, metric_date: date | None = None) -> None:
        target = metric_date or date.today()
        with _scoped_garth_home(user_id):
            service = GarminSyncService(GarminAdapter(), self.database, user_id=user_id)
            service.sync_recent_activities()
            service.sync_daily_health(target)

    def load_feedback_history(self, user_id: str, limit: int = 8) -> list[SessionFeedback]:
        return [
            SessionFeedback.from_dict(item)
            for item in self.database.list_feedback(user_id, limit=limit)
        ]

    def load_recovery_summary(self, user_id: str) -> WeeklyRecoverySummary:
        rows = self.database.list_recent_daily_health(user_id, limit=7)
        sleep_scores = [
            float(row["sleep_score"]) for row in rows if row.get("sleep_score") is not None
        ]
        body_battery = [
            float(row["body_battery"]) for row in rows if row.get("body_battery") is not None
        ]
        avg_sleep = None
        if sleep_scores:
            avg_sleep = f"{sum(sleep_scores) / len(sleep_scores):.0f}/100"
        return WeeklyRecoverySummary(
            avg_sleep=avg_sleep,
            avg_sleep_score=(sum(sleep_scores) / len(sleep_scores)) if sleep_scores else None,
            avg_body_battery=(sum(body_battery) / len(body_battery)) if body_battery else None,
        )

    async def create_readiness(self, user_id: str) -> ReadinessScore:
        metrics = self.build_health_metrics(user_id)
        return metrics.readiness or self.readiness_calc.calculate(metrics)

    async def create_daily_coaching(
        self, user_id: str, readiness: dict[str, Any] | ReadinessScore
    ) -> CoachingResponse:
        metrics = self.build_health_metrics(user_id)
        actual = (
            readiness
            if isinstance(readiness, ReadinessScore)
            else (metrics.readiness or self.readiness_calc.calculate(metrics))
        )
        return await self.engine.generate_daily_coaching(
            self.load_engine_user(user_id), metrics, actual
        )

    async def create_weekly_plan(self, user_id: str) -> WeeklyPlan:
        metrics = self.build_health_metrics(user_id)
        return await self.engine.generate_weekly_plan(
            self.load_engine_user(user_id),
            metrics.training_load,
            [metrics.readiness] if metrics.readiness else [],
            self.load_feedback_history(user_id),
        )

    async def create_answer(self, user_id: str, question: str) -> str:
        metrics = self.build_health_metrics(user_id)
        context = CoachingContext(
            recent_activities=metrics.recent_activities,
            current_metrics=metrics,
            readiness=metrics.readiness,
            notes=["telegram"],
        )
        response = await self.engine.answer_question(
            self.load_engine_user(user_id), question, context
        )
        return response.text

    async def create_workout_analysis(
        self, user_id: str, activity: dict[str, Any]
    ) -> WorkoutAnalysis:
        return await self.engine.generate_workout_analysis(
            self.load_engine_user(user_id), self.to_activity_model(activity)
        )

    async def create_report(self, user_id: str, window_days: int, label: str) -> WeeklyReport:
        end_date = date.today()
        weekly_plan = await self.create_weekly_plan(user_id)
        notes = weekly_plan.notes[0] if weekly_plan.notes else ""
        generator = WeeklyReportGenerator(self.database, self.feedback_service)
        if window_days >= 30:
            return await MonthlyReportGenerator(self.database, self.feedback_service).generate(
                user_id,
                end_date=end_date,
                label=label,
                coach_comment=notes,
            )
        return await generator.generate(
            user_id,
            end_date=end_date,
            window_days=window_days,
            label=label,
            coach_comment=notes,
        )

    async def create_daily_guide(self, user_id: str) -> dict[str, Any]:
        profile = self.profile_service._load(user_id)
        if not profile:
            return {
                "session_type": "일반일",
                "macros": {},
                "hydration": "기본 수분 섭취를 유지하세요.",
            }
        targets = calculate_nutrition_targets(
            weight_kg=profile.profile.weight_kg,
            height_cm=int(profile.profile.height_cm),
            age=profile.profile.age,
            sex=profile.profile.sex.value,
            sport=profile.profile.primary_sport.value,
            duration_minutes=60,
            intensity="moderate",
        )
        return {
            "session_type": profile.profile.primary_sport.value,
            "macros": {
                "carbs_g": (targets.carbs_grams * 0.8, targets.carbs_grams * 1.1),
                "protein_g": (targets.protein_grams * 0.9, targets.protein_grams * 1.1),
                "fat_g": (max(20, targets.fat_grams * 0.8),),
            },
            "hydration": f"하루 총 {targets.water_ml}ml + 운동 중 추가 보충",
        }

    async def create_pre_workout_advice(
        self, user_id: str, session_type: str
    ) -> dict[str, Any] | None:
        profile = self.profile_service._load(user_id)
        if not profile:
            return None
        duration_map = {"easy": 45, "moderate": 60, "tempo": 75, "interval": 75, "long": 120}
        duration = duration_map.get(session_type.lower(), 60)
        advice = recommend_pre_workout(profile.profile.primary_sport.value, duration)
        return {
            "description": f"{session_type} 세션 기준 · {advice['timing']} · 탄수화물 {advice['carbs']}",
            "examples": advice["examples"],
        }

    async def create_recovery_advice(
        self, user_id: str, activity: dict[str, Any]
    ) -> dict[str, Any]:
        profile = self.profile_service._load(user_id)
        duration = int(float(activity.get("duration_min", 0) or 0))
        sport = activity.get("type") or (
            profile.profile.primary_sport.value if profile else "running"
        )
        advice = recommend_post_workout(str(sport), duration)
        return {
            "timing": advice["timing"],
            "examples": advice["examples"],
            "rationale": advice["ratio"],
        }

    def to_activity_model(self, payload: dict[str, Any]) -> ActivitySummary:
        return ActivitySummary(
            activity_id=payload.get("activity_id"),
            type=payload.get("type"),
            start_time=payload.get("start_time"),
            distance_km=payload.get("distance_km"),
            duration_min=payload.get("duration_min"),
            avg_pace=payload.get("avg_pace"),
            avg_hr=payload.get("avg_hr"),
            calories=payload.get("calories"),
            raw=payload,
        )

    def latest_activity_payload(self, user_id: str) -> dict[str, Any] | None:
        activities = self.database.list_recent_activities(user_id, limit=1)
        if activities:
            return activities[0]
        self.refresh_user(user_id)
        activities = self.database.list_recent_activities(user_id, limit=1)
        return activities[0] if activities else None

    def _sleep_score(self, payload: dict[str, Any]) -> int | None:
        sleep = payload.get("sleep") if isinstance(payload, dict) else None
        if isinstance(sleep, dict):
            value = sleep.get("overallScore") or sleep.get("sleepScore")
            return int(value) if isinstance(value, (int, float)) else None
        return None

    def _body_battery(self, payload: dict[str, Any]) -> int | None:
        body = payload.get("body_battery") if isinstance(payload, dict) else None
        if isinstance(body, dict):
            value = body.get("current_value") or body.get("morning_value")
            return int(value) if isinstance(value, (int, float)) else None
        return None

    def _rhr(self, payload: dict[str, Any]) -> int | None:
        rhr = payload.get("rhr") if isinstance(payload, dict) else None
        if isinstance(rhr, dict):
            value = rhr.get("value_bpm")
            return int(value) if isinstance(value, (int, float)) else None
        return None

    def _training_readiness(self, payload: dict[str, Any]) -> int | None:
        tr = payload.get("training_readiness") if isinstance(payload, dict) else None
        if isinstance(tr, dict):
            value = tr.get("score")
            return int(value) if isinstance(value, (int, float)) else None
        return None

    def _load_current_injuries(self, user_id: str) -> list[InjuryRecord]:
        path = GUARDRAIL_DIR / f"{user_id}.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text())
        return [
            InjuryRecord(
                body_part=payload.get("body_part", "unknown"),
                description=payload.get("severity", "reported via telegram"),
                restrictions=list(payload.get("restricted_session_types", [])),
                pain_reports_count=int(payload.get("pain_reports_count", 0) or 0),
                restricted_session_types=list(payload.get("restricted_session_types", [])),
            )
        ]

    def _merged_injuries(self, user_id: str, profile: Any) -> list[InjuryRecord]:
        combined: list[InjuryRecord] = []
        seen: set[str] = set()
        for injury in self._load_current_injuries(user_id):
            key = (injury.body_part or "").strip().lower()
            if key and key not in seen:
                combined.append(injury)
                seen.add(key)
        for injury_name in list(getattr(profile.medical, "current_injuries", [])):
            key = injury_name.strip().lower()
            if key and key not in seen:
                combined.append(
                    InjuryRecord(
                        body_part=injury_name.strip(),
                        description="reported during onboarding/settings",
                        medical_clearance="pending",
                        restrictions=["avoid high intensity"],
                        restricted_session_types=["hard", "interval", "tempo"],
                    )
                )
                seen.add(key)
        return combined


class _RuntimeEngineProxy:
    def __init__(self, bridge: _RuntimeDataBridge) -> None:
        self.bridge = bridge

    async def generate_weekly_plan(self, user_id: str) -> WeeklyPlan:
        return await self.bridge.create_weekly_plan(user_id)

    async def answer_question(self, user_id: str, question: str) -> str:
        return await self.bridge.create_answer(user_id, question)


class _RuntimeReportService:
    def __init__(self, bridge: _RuntimeDataBridge) -> None:
        self.bridge = bridge

    async def generate_weekly(self, user_id: str) -> WeeklyReport:
        return await self.bridge.create_report(user_id, 7, "최근 7일")

    async def generate_monthly(self, user_id: str) -> WeeklyReport:
        return await self.bridge.create_report(user_id, 30, "최근 30일")


class _ReadinessProvider:
    def __init__(self, bridge: _RuntimeDataBridge) -> None:
        self.bridge = bridge

    async def get_readiness(self, user_id: str) -> ReadinessScore:
        return await self.bridge.create_readiness(user_id)


class _DailyCoachingProvider:
    def __init__(self, bridge: Any, plan_state: "_MorningPlanStateStore") -> None:
        self.bridge = bridge
        self.plan_state = plan_state

    async def generate_daily_coaching(
        self, user_id: str, readiness: dict[str, Any] | ReadinessScore
    ) -> CoachingResponse:
        state = self.plan_state.get_today_state(user_id)
        if state.get("action") == "postpone":
            return CoachingResponse(
                text="오늘 세션은 내일로 미뤘어요. 오늘은 회복 우선으로 전환합니다.",
                intensity="rest",
                session_type=SessionType.REST,
            )
        if state.get("action") == "change":
            selected = str(state.get("session_type") or "easy")
            session = (
                SessionType(selected)
                if selected in {s.value for s in SessionType}
                else SessionType.EASY
            )
            return CoachingResponse(
                text=f"사용자 요청으로 오늘 세션을 {selected}로 변경해 적용했어요.",
                intensity=selected,
                session_type=session,
            )
        return await self.bridge.create_daily_coaching(user_id, readiness)


class _DailySummaryProvider:
    def __init__(self, bridge: Any) -> None:
        self.bridge = bridge

    async def get_daily_summary(self, user_id: str) -> dict[str, Any]:
        metrics = self.bridge.build_health_metrics(user_id)
        today_iso = date.today().isoformat()
        todays = [
            activity
            for activity in metrics.recent_activities
            if str(getattr(activity, "start_time", "") or "").startswith(today_iso)
        ]
        latest = todays[-1] if todays else None
        with _scoped_garth_home(user_id):
            summary = safe_get_daily_summary(date.today().isoformat())
        return {
            "workout": (latest.raw.get("activity_name") or latest.type) if latest else None,
            "active_calories": getattr(summary, "active_calories", None)
            or getattr(summary, "total_calories", None)
            or (latest.calories if latest else None),
            "steps": getattr(summary, "steps", None) or getattr(summary, "total_steps", None),
            "stress_avg": getattr(summary, "average_stress_level", None)
            or getattr(summary, "stress_avg", None),
        }


class _TomorrowPlanProvider:
    def __init__(
        self, bridge: Any, profile_service: Any, plan_state: "_MorningPlanStateStore"
    ) -> None:
        self.bridge = bridge
        self.profile_service = profile_service
        self.plan_state = plan_state

    async def get_tomorrow_plan(self, user_id: str) -> dict[str, Any]:
        state = self.plan_state.get_today_state(user_id)
        if state.get("action") == "postpone":
            return {"session": "미뤄둔 오늘 세션 재진행", "recommended_bedtime": "22:00"}
        weekly_plan = await self.bridge.create_weekly_plan(user_id)
        tomorrow = date.today() + timedelta(days=1)
        day = next((item for item in weekly_plan.days if item.date == tomorrow.isoformat()), None)
        bedtime = (
            "22:00"
            if day
            and day.session_type in {SessionType.HARD, SessionType.INTERVAL, SessionType.TEMPO}
            else "22:30"
        )
        return {
            "session": day.description if day else "회복 세션",
            "recommended_bedtime": bedtime,
        }


class _NutritionGuideProvider:
    def __init__(self, bridge: _RuntimeDataBridge) -> None:
        self.bridge = bridge

    async def get_daily_guide(self, user_id: str) -> dict[str, Any]:
        return await self.bridge.create_daily_guide(user_id)


class _PreWorkoutNutritionProvider:
    def __init__(self, bridge: _RuntimeDataBridge) -> None:
        self.bridge = bridge

    async def get_pre_workout_advice(
        self, user_id: str, session_type: str
    ) -> dict[str, Any] | None:
        return await self.bridge.create_pre_workout_advice(user_id, session_type)


class _WorkoutAnalyzer:
    def __init__(self, bridge: _RuntimeDataBridge) -> None:
        self.bridge = bridge

    async def analyze(self, user_id: str, activity: dict[str, Any]) -> WorkoutAnalysis:
        return await self.bridge.create_workout_analysis(user_id, activity)


class _RecoveryFuelProvider:
    def __init__(self, bridge: _RuntimeDataBridge) -> None:
        self.bridge = bridge

    async def get_advice(self, user_id: str, activity: dict[str, Any]) -> dict[str, Any]:
        return await self.bridge.create_recovery_advice(user_id, activity)


class _ManualFeedbackCollector:
    def __init__(self, adapter: TelegramAdapter, database: GarminCoachDatabase) -> None:
        self.adapter = adapter
        self.database = database

    async def collect_manual(self, user_id: str) -> None:
        try:
            rpe = int(
                await self.adapter.request_number(
                    user_id, "📝 오늘 세션의 체감 강도(RPE)를 입력해주세요.", 1, 10
                )
            )
            feeling = await self.adapter.request_select(
                user_id,
                "전체적인 느낌을 선택해주세요.",
                [
                    Option("좋았어요", "good"),
                    Option("보통", "neutral"),
                    Option("힘들었어요", "bad"),
                ],
            )
            note = await self.adapter.request_text(
                user_id, "추가 메모가 있으면 입력해주세요. 없으면 '없음'이라고 적어주세요."
            )
            feedback = SessionFeedback(
                session_date=date.today().isoformat(),
                activity_id=f"manual-{uuid.uuid4().hex[:8]}",
                completion=FeedbackCompletion.UNKNOWN,
                feeling=feeling,
                rpe=rpe,
                note="" if note.strip().lower() in {"", "없음", "none"} else note.strip(),
            )
            self.database.save_feedback(
                user_id,
                feedback.activity_id or f"manual-{uuid.uuid4().hex[:8]}",
                feedback.session_date,
                feedback.to_dict(),
            )
            await self.adapter.send_message(user_id, "✅ 피드백을 기록했어요.")
        except InputAborted as exc:
            if exc.reason == InputAbortReason.TIMEOUT:
                await self.adapter.send_message(
                    user_id, "⏱️ 피드백 입력 시간이 초과되어 저장하지 않았어요."
                )
            else:
                await self.adapter.send_message(user_id, "⏹️ 피드백 입력을 취소했어요.")


class _FeedbackStore(_ManualFeedbackCollector):
    def __init__(self, adapter: TelegramAdapter, database: GarminCoachDatabase) -> None:
        super().__init__(adapter, database)
        self.service = FeedbackAggregatorService(database, GUARDRAIL_DIR)

    async def save_feedback(self, user_id: str, activity_id: str, feedback: dict[str, Any]) -> None:
        self.service.save_feedback(
            user_id,
            activity_id,
            feedback,
            activity_date=str(feedback.get("session_date") or date.today().isoformat()),
        )


class _NutritionStore:
    def __init__(self, database: GarminCoachDatabase) -> None:
        self.database = database

    async def save_meal(self, user_id: str, meal: dict[str, Any]) -> None:
        entry_id = f"meal-{uuid.uuid4().hex[:8]}"
        self.database.save_nutrition_log(user_id, entry_id, date.today().isoformat(), meal)


class _FoodPhotoAnalyzer:
    def __init__(self, profile_service: "_UserProfileService") -> None:
        self.profile_service = profile_service

    async def analyze(self, user_id: str, photo: bytes) -> dict[str, Any]:
        profile = self.profile_service._load(user_id)
        weight = profile.profile.weight_kg if profile else 70.0
        height = int(profile.profile.height_cm) if profile else 170
        age = profile.profile.age if profile else 30
        sex = profile.profile.sex.value if profile else "other"
        sport = profile.profile.primary_sport.value if profile else "running"
        targets = calculate_nutrition_targets(weight, height, age, sex, sport, 45)
        is_screenshot = photo.startswith(b"\x89PNG")
        return {
            "items_detected": ["운동 직후 간식"] if is_screenshot else ["한 끼 식사"],
            "estimated_macros": {
                "calories": int(targets.calories * (0.3 if is_screenshot else 0.4)),
                "protein_g": int(targets.protein_grams * (0.35 if is_screenshot else 0.4)),
                "carbs_g": int(targets.carbs_grams * (0.25 if is_screenshot else 0.3)),
                "fat_g": int(targets.fat_grams * (0.2 if is_screenshot else 0.3)),
            },
            "coaching_note": "사진 기준 추정치예요. 실제 섭취량과 다르면 수정해서 저장하세요.",
        }


class _PhotoRouter:
    def __init__(self, bridge: Any, food_analyzer: Any = None) -> None:
        self.bridge = bridge
        self.food_analyzer = food_analyzer or _FoodPhotoAnalyzer(bridge.profile_service)

    async def auto_detect_type(self, photo: bytes) -> str | None:
        if photo.startswith(b"\x89PNG"):
            return "workout"
        if photo.startswith(b"\xff\xd8\xff"):
            return "food"
        return None

    async def analyze_workout(self, user_id: str, photo: bytes) -> dict[str, Any]:
        activity = self.bridge.latest_activity_payload(user_id)
        if not activity:
            return {
                "summary": "최근 운동 기록을 찾지 못했어요.",
                "comparison_to_recent": "Garmin 동기화 후 다시 시도해주세요.",
                "coaching_notes": [
                    "기록을 확인하고 필요하면 /feedback 으로 주관적 피드백도 남겨주세요."
                ],
            }
        analysis = (await self.bridge.create_workout_analysis(user_id, activity)).to_dict()
        analysis["comparison_to_recent"] = (
            "운동 캡쳐로 인식되어 최근 Garmin 활동 기록과 비교했어요."
            if photo.startswith(b"\x89PNG")
            else "일반 사진으로 판단되어 최근 Garmin 활동 기록 기준으로 보수적으로 해석했어요."
        )
        return analysis

    async def analyze_food(self, user_id: str, photo: bytes) -> dict[str, Any]:
        analysis = await self.food_analyzer.analyze(user_id, photo)
        return {
            "timing": "식사 기록으로 반영했어요.",
            "examples": analysis.get("items_detected", ["탄수화물과 단백질 균형을 맞춰보세요."]),
            "macros": {
                "carbs": f"~{analysis.get('estimated_macros', {}).get('carbs_g', '?')}g",
                "protein": f"~{analysis.get('estimated_macros', {}).get('protein_g', '?')}g",
            },
        }


class _MorningPlanStateStore:
    def __init__(self, root: Path = MORNING_PLAN_DIR) -> None:
        self.root = root

    async def change_today_session(self, user_id: str, session_type: str) -> None:
        payload = self._load(user_id)
        payload[date.today().isoformat()] = {"action": "change", "session_type": session_type}
        self._save(user_id, payload)

    async def postpone_today(self, user_id: str) -> None:
        payload = self._load(user_id)
        payload[date.today().isoformat()] = {"action": "postpone"}
        self._save(user_id, payload)

    def get_today_state(self, user_id: str) -> dict[str, Any]:
        return self._load(user_id).get(date.today().isoformat(), {})

    def _load(self, user_id: str) -> dict[str, Any]:
        path = self.root / f"{user_id}.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text())

    def _save(self, user_id: str, payload: dict[str, Any]) -> None:
        (self.root / f"{user_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2)
        )


class _InjuryStorage:
    def __init__(self, root: Path = INJURY_DIR) -> None:
        self.root = root

    async def save_injury(self, user_id: str, injury: dict[str, Any]) -> None:
        path = self.root / f"{user_id}.json"
        records = []
        if path.exists():
            records = json.loads(path.read_text())
        records.append({**injury, "reported_at": datetime.now().isoformat()})
        path.write_text(json.dumps(records, ensure_ascii=False, indent=2))


class _GuardrailNotifier:
    def __init__(self, root: Path = GUARDRAIL_DIR) -> None:
        self.root = root

    async def on_injury_reported(self, user_id: str, injury: dict[str, Any]) -> None:
        severity = injury.get("severity", "mild")
        restricted = (
            ["hard", "interval", "tempo"] if severity in {"moderate", "severe"} else ["hard"]
        )
        payload = {
            "body_part": injury.get("body_part", "unknown"),
            "severity": severity,
            "restricted_session_types": restricted,
            "updated_at": datetime.now().isoformat(),
        }
        (self.root / f"{user_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2)
        )

    async def on_profile_updated(self, user_id: str, profile: Any) -> None:
        current_injuries = list(getattr(profile.medical, "current_injuries", []))
        path = self.root / f"{user_id}.json"
        if not current_injuries:
            if path.exists():
                path.unlink()
            return
        payload = {
            "body_part": current_injuries[0],
            "severity": "moderate",
            "restricted_session_types": ["hard", "interval", "tempo"],
            "updated_at": datetime.now().isoformat(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        path.chmod(0o600)


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



def _build_flow_registry(
    adapter: TelegramAdapter, bridge: _RuntimeDataBridge, database: GarminCoachDatabase
) -> _FlowRegistry:
    profile_service = bridge.profile_service
    morning_state = _MorningPlanStateStore()
    feedback_service = _FeedbackStore(adapter, database)
    nutrition_store = _NutritionStore(database)
    food_analyzer = _FoodPhotoAnalyzer(profile_service)
    nutrition_flow = NutritionLogFlow(
        port=adapter,
        photo_analyzer=food_analyzer,
        storage=nutrition_store,
        nutrition_guide=_NutritionGuideProvider(bridge),
    )
    return _FlowRegistry(
        morning_briefing=MorningBriefingFlow(
            port=adapter,
            readiness=_ReadinessProvider(bridge),
            coaching=_DailyCoachingProvider(bridge, morning_state),
            nutrition=_PreWorkoutNutritionProvider(bridge),
            plan_state=morning_state,
        ),
        post_workout=PostWorkoutFlow(
            port=adapter,
            analyzer=_WorkoutAnalyzer(bridge),
            recovery_fuel=_RecoveryFuelProvider(bridge),
            feedback_agg=feedback_service,
        ),
        evening_checkin=EveningCheckinFlow(
            port=adapter,
            summary_provider=_DailySummaryProvider(bridge),
            tomorrow_plan=_TomorrowPlanProvider(bridge, profile_service, morning_state),
        ),
        nutrition_log=nutrition_flow,
        injury_report=InjuryReportFlow(
            port=adapter,
            injury_storage=_InjuryStorage(),
            guardrail_notifier=_GuardrailNotifier(),
        ),
        onboarding=OnboardingFlow(adapter, onboarding_service=profile_service),
        settings=SettingsFlow(adapter, settings_service=profile_service),
        goals=GoalsFlow(adapter, goals_service=profile_service),
    )


def _set_bot_commands(
    app: Any, scheduler: TelegramScheduler, registry: TelegramUserRegistry
) -> None:
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
        for user_id in await registry.get_all_user_ids():
            await scheduler.schedule_for_user(user_id)

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
    profile_service = _UserProfileService()
    database = GarminCoachDatabase(RUNTIME_DB)
    bridge = _RuntimeDataBridge(profile_service, database)
    flow_registry = _build_flow_registry(runtime_adapter, bridge, database)
    report_service = _RuntimeReportService(bridge)
    feedback_service = _FeedbackStore(runtime_adapter, database)
    actual_bus = sync_bus or SyncEventBus()
    runtime_handlers = handlers or TelegramHandlers(
        runtime_adapter,
        flows=flow_registry,
        engine=_RuntimeEngineProxy(bridge),
        reports=report_service,
        feedback=feedback_service,
        photo_router=_PhotoRouter(bridge),
        user_registry=registry,
    )
    runtime_scheduler = scheduler or TelegramScheduler(
        flow_registry,
        user_config=_ScheduleConfigProvider(registry, profile_service),
        delivery=runtime_adapter,
        reports=report_service,
        locker=runtime_adapter,
    )
    guardrail_notifier = _GuardrailNotifier()

    async def _profile_side_effect(user_id: str, change_kind: str, profile: Any) -> None:
        if change_kind in {"schedule", "preferences", "onboarding_sections"} and (
            change_kind != "onboarding_sections"
            or bool(profile.preferences.timezone or profile.preferences.preferred_training_time)
        ):
            await runtime_scheduler.schedule_for_user(user_id)
            return
        if change_kind in {"medical", "onboarding_sections"}:
            await guardrail_notifier.on_profile_updated(user_id, profile)

    set_side_effect = getattr(profile_service, "set_settings_side_effect", None)
    if callable(set_side_effect):
        set_side_effect(_profile_side_effect)

    async def _activity_sync_job(context: Any) -> None:
        for user_id in await registry.get_all_user_ids():
            with _scoped_garth_home(user_id):
                service = GarminSyncService(
                    GarminAdapter(), database, bus=actual_bus, user_id=user_id
                )
                service.sync_recent_activities()
                service.sync_daily_health()

    runtime_handlers.register(app)
    runtime_scheduler.setup(app.job_queue)
    if hasattr(app.job_queue, "run_repeating"):
        app.job_queue.run_repeating(
            _activity_sync_job, interval=900, first=10, name="activity_sync"
        )
    _set_bot_commands(app, runtime_scheduler, registry)
    _bind_sync_bus(app, runtime_scheduler, actual_bus)

    app.bot_data["stream2_adapter"] = runtime_adapter
    app.bot_data["stream2_handlers"] = runtime_handlers
    app.bot_data["stream2_scheduler"] = runtime_scheduler
    app.bot_data["stream2_sync_bus"] = actual_bus
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
