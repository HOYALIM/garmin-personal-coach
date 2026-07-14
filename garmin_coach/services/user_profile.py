"""UserProfileService — channel-agnostic profile/onboarding persistence.

Extracted verbatim from telegram_bot.py so that every channel (Telegram,
iMessage, future app/web) can run the same onboarding and settings flows
without importing across an interface boundary. telegram_bot re-exports
this class as `_UserProfileService` for backward compatibility (tests
subclass and monkeypatch that name).

The state root is still `~/.config/garmin_coach/telegram_states/` — the
directory name is historical (it predates multi-channel support) but is
kept as-is because existing users' profiles already live there; renaming
would orphan their data for zero functional gain.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml

import garmin_coach.activity_fetch as activity_fetch_module
import garmin_coach.adapters.garmin as garmin_adapter_module
from garmin_coach.adapters.garmin import GarminAdapter
from garmin_coach.profile_manager import ProfileManager

DATA_DIR = Path.home() / ".config" / "garmin_coach"
STATE_DIR = DATA_DIR / "telegram_states"
PROFILE_DIR = STATE_DIR / "profiles"
ONBOARDING_PROGRESS_DIR = STATE_DIR / "onboarding_progress"
GARTH_USER_DIR = STATE_DIR / "garth"


@contextmanager
def scoped_garth_home(user_id: str):
    original = garmin_adapter_module.GARTH_HOME
    original_fetch = activity_fetch_module.GARTH_HOME
    garmin_adapter_module.GARTH_HOME = str(GARTH_USER_DIR / user_id)
    activity_fetch_module.GARTH_HOME = str(GARTH_USER_DIR / user_id)
    try:
        yield
    finally:
        garmin_adapter_module.GARTH_HOME = original
        activity_fetch_module.GARTH_HOME = original_fetch


class UserProfileService:
    def __init__(
        self,
        settings_side_effect: Callable[[str, str, Any], Awaitable[None] | None] | None = None,
    ) -> None:
        self._settings_side_effect = settings_side_effect

    def _manager(self, user_id: str) -> Any:
        return ProfileManager(config_path=PROFILE_DIR / f"{user_id}.yaml")

    def _load(self, user_id: str) -> Any:
        return self._manager(user_id).load()

    def _save(self, user_id: str, profile: Any) -> None:
        manager = self._manager(user_id)
        manager.validate_or_raise(profile)
        manager.save(profile)

    def set_settings_side_effect(
        self,
        callback: Callable[[str, str, Any], Awaitable[None] | None] | None,
    ) -> None:
        self._settings_side_effect = callback

    async def _emit_settings_side_effect(
        self, user_id: str, change_kind: str, profile: Any
    ) -> None:
        if self._settings_side_effect is None:
            return
        result = self._settings_side_effect(user_id, change_kind, profile)
        if asyncio.iscoroutine(result):
            await result

    async def _mutate_profile(
        self,
        user_id: str,
        change_kind: str,
        mutator: Callable[[Any], None],
    ) -> None:
        profile = self._load(user_id)
        if profile is None:
            raise ValueError(f"Profile not found for user {user_id}")
        mutator(profile)
        self._save(user_id, profile)
        await self._emit_settings_side_effect(user_id, change_kind, profile)

    def _progress_path(self, user_id: str) -> Path:
        return ONBOARDING_PROGRESS_DIR / f"{user_id}.json"

    def _default_progress(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "status": "in_progress",
            "current_step": "phase1.garmin_email",
            "profile_created": False,
            "phase1": {},
            "phase2": {},
            "phase3": {},
            "phase2_status": "pending",
            "phase3_status": "pending",
        }

    def _normalize_progress(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        progress = self._default_progress()
        if not payload:
            return progress
        if "schema_version" not in payload:
            progress["phase1"] = dict(payload)
            if payload.get("garmin_connected"):
                progress["current_step"] = "phase1.target_event"
            return progress
        progress.update(
            {
                "schema_version": payload.get("schema_version", 2),
                "status": payload.get("status", "in_progress"),
                "current_step": payload.get("current_step", "phase1.garmin_email"),
                "profile_created": bool(payload.get("profile_created")),
                "phase2_status": payload.get("phase2_status", "pending"),
                "phase3_status": payload.get("phase3_status", "pending"),
            }
        )
        for section in ("phase1", "phase2", "phase3"):
            progress[section] = dict(payload.get(section, {}))
        return progress

    def _write_progress(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        path.chmod(0o600)

    async def has_profile(self, user_id: str) -> bool:
        return self._load(user_id) is not None

    async def summarize_profile(self, user_id: str) -> str:
        profile = self._load(user_id)
        if not profile:
            return "먼저 /start 로 기본 설정을 완료해주세요."
        return (
            f"👋 이미 설정이 완료되어 있어요.\n"
            f"이름: {profile.profile.name}\n"
            f"Garmin 연결: {'완료' if profile.garmin.connected else '미완료'}\n"
            f"목표: {profile.profile.goal_event or '미설정'}\n"
            f"훈련 가능일: 주 {profile.profile.available_days}일\n\n"
            f"세부 설정은 /settings, 목표 변경은 /goals 에서 계속할 수 있어요."
        )

    async def connect_garmin(self, user_id: str, email: str, password: str) -> bool:
        with scoped_garth_home(user_id):
            return GarminAdapter().authenticate({"email": email, "password": password})

    async def create_profile(self, user_id: str, payload: dict[str, Any]) -> str:
        from garmin_coach.profile_manager import (
            AICoachConfig,
            FitnessData,
            FitnessLevel,
            GarminConfig,
            MedicalConfig,
            NutritionPreferences,
            ProfileData,
            ScheduleConfig,
            Sex,
            SleepConfig,
            Sport,
            UserPreferences,
            UserProfile,
        )

        profile = UserProfile(
            profile=ProfileData(
                name=payload["name"],
                age=int(payload["age"]),
                sex=Sex(payload["sex"]),
                height_cm=float(payload["height_cm"]),
                weight_kg=float(payload["weight_kg"]),
                sports=[Sport(value) for value in payload.get("sports", ["running"])],
                goal_event=payload.get("goal_event", ""),
                goal_date=payload.get("goal_date", ""),
                fitness_level=FitnessLevel(payload.get("fitness_level", "intermediate")),
                available_days=int(payload.get("available_days", 4)),
            ),
            fitness=FitnessData(),
            garmin=GarminConfig(
                email=payload.get("garmin_email") or None,
                connected=bool(payload.get("garmin_connected")),
            ),
            schedule=ScheduleConfig(
                morning_checkin={"enabled": True, "time": payload.get("morning_time", "06:00")},
                evening_checkin={"enabled": True, "time": payload.get("evening_time", "22:00")},
                weekly_review={"enabled": True, "day": "sunday", "time": "20:00"},
            ),
            ai_coach=AICoachConfig(enabled=False),
            nutrition=NutritionPreferences(
                weight_goal=payload.get("weight_goal", "maintain"),
                dietary_style=payload.get("dietary_style", "omnivore"),
                food_restrictions=list(payload.get("food_restrictions", [])),
                allergies=list(payload.get("allergies", [])),
                meal_pattern=payload.get("meal_pattern", ""),
                supplements=list(payload.get("supplements", [])),
                alcohol_frequency=payload.get("alcohol_frequency", ""),
            ),
            medical=MedicalConfig(
                cardiac_conditions=list(payload.get("cardiac_conditions", [])),
                hypertension=payload.get("hypertension", "none"),
                diabetes=payload.get("diabetes", "none"),
                respiratory=list(payload.get("respiratory", [])),
                beta_blocker=bool(payload.get("beta_blocker", False)),
                current_injuries=list(payload.get("current_injuries", [])),
                notes=payload.get("medical_notes", ""),
            ),
            sleep=SleepConfig(
                bedtime=payload.get("bedtime") or None,
                wake_time=payload.get("wake_time") or None,
                issues=list(payload.get("sleep_issues", [])),
            ),
            preferences=UserPreferences(
                preferred_training_time=payload.get("preferred_training_time") or None,
                cross_training_preferences=list(payload.get("cross_training_preferences", [])),
                notification_frequency=payload.get("notification_frequency", "default"),
                units=payload.get("units", "metric"),
                timezone=payload.get("timezone", "Asia/Seoul"),
                strava_connected=bool(payload.get("strava_connected", False)),
            ),
        )
        self._save(user_id, profile)
        sports = ", ".join(s.value for s in profile.profile.sports)
        return (
            f"✅ 온보딩이 완료되었어요.\n"
            f"이름: {profile.profile.name}\n"
            f"운동: {sports}\n"
            f"Garmin 연결: {'완료' if profile.garmin.connected else '미완료'}\n"
            f"목표: {profile.profile.goal_event or '미설정'}\n"
            f"아침 브리핑: {profile.schedule.morning_checkin.get('time', '06:00')}\n"
            f"저녁 체크인: {profile.schedule.evening_checkin.get('time', '22:00')}\n\n"
            f"이제 /today, /week, /report 를 바로 사용할 수 있어요."
        )

    async def update_profile_sections(self, user_id: str, payload: dict[str, Any]) -> None:
        def mutate(profile: Any) -> None:
            medical = payload.get("medical") or {}
            nutrition = payload.get("nutrition") or {}
            sleep = payload.get("sleep") or {}
            preferences = payload.get("preferences") or {}
            if medical:
                profile.medical.cardiac_conditions = list(medical.get("cardiac_conditions", []))
                profile.medical.hypertension = medical.get("hypertension", "none")
                profile.medical.diabetes = medical.get("diabetes", "none")
                profile.medical.respiratory = list(medical.get("respiratory", []))
                profile.medical.beta_blocker = bool(medical.get("beta_blocker", False))
                profile.medical.current_injuries = list(medical.get("current_injuries", []))
                profile.medical.notes = medical.get("notes", "")
            if nutrition:
                profile.nutrition.food_restrictions = list(
                    nutrition.get("food_restrictions", profile.nutrition.food_restrictions)
                )
                profile.nutrition.allergies = list(
                    nutrition.get("allergies", profile.nutrition.allergies)
                )
                profile.nutrition.meal_pattern = nutrition.get(
                    "meal_pattern", profile.nutrition.meal_pattern
                )
                profile.nutrition.supplements = list(
                    nutrition.get("supplements", profile.nutrition.supplements)
                )
                profile.nutrition.alcohol_frequency = nutrition.get(
                    "alcohol_frequency", profile.nutrition.alcohol_frequency
                )
            if sleep:
                profile.sleep.bedtime = sleep.get("bedtime") or None
                profile.sleep.wake_time = sleep.get("wake_time") or None
                profile.sleep.issues = list(sleep.get("issues", []))
            if preferences:
                profile.preferences.preferred_training_time = (
                    preferences.get("preferred_training_time") or None
                )
                profile.preferences.cross_training_preferences = list(
                    preferences.get(
                        "cross_training_preferences",
                        profile.preferences.cross_training_preferences,
                    )
                )
                profile.preferences.notification_frequency = preferences.get(
                    "notification_frequency", profile.preferences.notification_frequency
                )
                profile.preferences.units = preferences.get("units", profile.preferences.units)
                profile.preferences.timezone = preferences.get(
                    "timezone", profile.preferences.timezone
                )
                profile.preferences.strava_connected = bool(
                    preferences.get("strava_connected", profile.preferences.strava_connected)
                )
                ai_tone = preferences.get("ai_tone")
                if ai_tone:
                    from garmin_coach.profile_manager import AITone

                    profile.ai_coach.tone = AITone(ai_tone)

        await self._mutate_profile(user_id, "onboarding_sections", mutate)

    async def load_progress(self, user_id: str) -> dict[str, Any]:
        path = self._progress_path(user_id)
        if not path.exists():
            return self._default_progress()
        return self._normalize_progress(json.loads(path.read_text()))

    async def save_progress(self, user_id: str, payload: dict[str, Any]) -> None:
        self._write_progress(self._progress_path(user_id), self._normalize_progress(payload))

    async def clear_progress(self, user_id: str) -> None:
        path = self._progress_path(user_id)
        if path.exists():
            path.unlink()

    async def summarize_settings(self, user_id: str) -> str:
        profile = self._load(user_id)
        return (
            f"⚙️ 현재 설정\n"
            f"이름: {profile.profile.name}\n"
            f"체중: {profile.profile.weight_kg:.1f}kg\n"
            f"아침 브리핑: {profile.schedule.morning_checkin.get('time', '06:00')}\n"
            f"저녁 체크인: {profile.schedule.evening_checkin.get('time', '22:00')}\n"
            f"영양 목표: {profile.nutrition.weight_goal}"
        )

    async def update_profile_name(self, user_id: str, value: str) -> None:
        await self._mutate_profile(
            user_id,
            "profile",
            lambda profile: setattr(profile.profile, "name", value.strip() or profile.profile.name),
        )

    async def update_weight(self, user_id: str, value: float) -> None:
        await self._mutate_profile(
            user_id,
            "profile",
            lambda profile: setattr(profile.profile, "weight_kg", value),
        )

    async def update_available_days(self, user_id: str, value: int) -> None:
        await self._mutate_profile(
            user_id,
            "profile",
            lambda profile: setattr(profile.profile, "available_days", value),
        )

    async def update_schedule(self, user_id: str, field: str, value: str) -> None:
        def mutate(profile: Any) -> None:
            if field == "morning":
                profile.schedule.morning_checkin["time"] = value
            else:
                profile.schedule.evening_checkin["time"] = value

        await self._mutate_profile(user_id, "schedule", mutate)

    async def update_nutrition(self, user_id: str, weight_goal: str, dietary_style: str) -> None:
        def mutate(profile: Any) -> None:
            profile.nutrition.weight_goal = weight_goal
            profile.nutrition.dietary_style = dietary_style

        await self._mutate_profile(user_id, "nutrition", mutate)

    async def update_medical(
        self,
        user_id: str,
        beta_blocker: bool,
        current_injuries: list[str],
        notes: str,
    ) -> None:
        def mutate(profile: Any) -> None:
            profile.medical.beta_blocker = beta_blocker
            profile.medical.current_injuries = list(current_injuries)
            profile.medical.notes = notes

        await self._mutate_profile(user_id, "medical", mutate)

    async def update_sleep(
        self,
        user_id: str,
        bedtime: str,
        wake_time: str,
        issues: list[str],
    ) -> None:
        def mutate(profile: Any) -> None:
            profile.sleep.bedtime = bedtime or None
            profile.sleep.wake_time = wake_time or None
            profile.sleep.issues = list(issues)

        await self._mutate_profile(user_id, "sleep", mutate)

    async def update_preferences(
        self,
        user_id: str,
        preferred_training_time: str,
        cross_training_preferences: list[str],
        notification_frequency: str,
        units: str,
        timezone: str,
        strava_connected: bool,
    ) -> None:
        def mutate(profile: Any) -> None:
            profile.preferences.preferred_training_time = preferred_training_time or None
            profile.preferences.cross_training_preferences = list(cross_training_preferences)
            profile.preferences.notification_frequency = notification_frequency
            profile.preferences.units = units
            profile.preferences.timezone = timezone or profile.preferences.timezone
            profile.preferences.strava_connected = strava_connected

        await self._mutate_profile(user_id, "preferences", mutate)

    async def update_ai_tone(self, user_id: str, tone: str) -> None:
        from garmin_coach.profile_manager import AITone

        await self._mutate_profile(
            user_id,
            "ai",
            lambda profile: setattr(profile.ai_coach, "tone", AITone(tone)),
        )

    async def summarize_goals(self, user_id: str) -> str:
        profile = self._load(user_id)
        return (
            f"🎯 현재 목표\n"
            f"이벤트: {profile.profile.goal_event or '미설정'}\n"
            f"날짜: {profile.profile.goal_date or '미설정'}\n"
            f"수준: {profile.profile.fitness_level.value}\n"
            f"최대 훈련 시간: {profile.profile.max_weekly_hours:.1f}h"
        )

    async def update_goal_event(self, user_id: str, value: str) -> None:
        await self._mutate_profile(
            user_id,
            "goal",
            lambda profile: setattr(profile.profile, "goal_event", value),
        )

    async def update_goal_date(self, user_id: str, value: str) -> None:
        await self._mutate_profile(
            user_id,
            "goal",
            lambda profile: setattr(profile.profile, "goal_date", value),
        )

    async def update_fitness_level(self, user_id: str, value: str) -> None:
        from garmin_coach.profile_manager import FitnessLevel

        await self._mutate_profile(
            user_id,
            "goal",
            lambda profile: setattr(profile.profile, "fitness_level", FitnessLevel(value)),
        )

    async def update_max_weekly_hours(self, user_id: str, value: float) -> None:
        await self._mutate_profile(
            user_id,
            "goal",
            lambda profile: setattr(profile.profile, "max_weekly_hours", value),
        )

    async def get_schedule_config(self, user_id: str) -> dict[str, Any]:
        profile = self._load(user_id)
        timezone = "Asia/Seoul"
        config_path = self._manager(user_id).config_path
        if config_path.exists():
            raw = yaml.safe_load(config_path.read_text()) or {}
            timezone = raw.get("preferences", {}).get("timezone") or raw.get("timezone") or timezone
        if not profile:
            return {"morning_time": "07:00", "evening_time": "21:00", "timezone": timezone}
        return {
            "morning_time": profile.schedule.morning_checkin.get("time", "07:00"),
            "evening_time": profile.schedule.evening_checkin.get("time", "21:00"),
            "weekly_time": profile.schedule.weekly_review.get("time", "20:00"),
            "weekly_day": profile.schedule.weekly_review.get("day", "sunday"),
            "monthly_time": "09:00",
            "timezone": profile.preferences.timezone or timezone,
        }


__all__ = [
    "GARTH_USER_DIR",
    "ONBOARDING_PROGRESS_DIR",
    "PROFILE_DIR",
    "UserProfileService",
    "scoped_garth_home",
]
