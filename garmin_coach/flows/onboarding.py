from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from garmin_coach.ports import CoachingPort, InputAbortReason, InputAborted, InputType, Option


class OnboardingService(Protocol):
    async def has_profile(self, user_id: str) -> bool: ...
    async def summarize_profile(self, user_id: str) -> str: ...
    async def connect_garmin(self, user_id: str, email: str, password: str) -> bool: ...
    async def create_profile(self, user_id: str, payload: dict[str, Any]) -> str: ...
    async def update_profile_sections(self, user_id: str, payload: dict[str, Any]) -> None: ...
    async def load_progress(self, user_id: str) -> dict[str, Any]: ...
    async def save_progress(self, user_id: str, payload: dict[str, Any]) -> None: ...
    async def clear_progress(self, user_id: str) -> None: ...


class OnboardingFlow:
    def __init__(self, port: CoachingPort, onboarding_service: OnboardingService) -> None:
        self.port = port
        self.onboarding_service = onboarding_service

    async def execute(self, user_id: str) -> None:
        progress = self._normalize_progress(await self.onboarding_service.load_progress(user_id))
        has_profile = await self.onboarding_service.has_profile(user_id)
        if has_profile:
            progress["profile_created"] = True
        if has_profile and not self._has_pending_progress(progress):
            await self.port.send_message(
                user_id, await self.onboarding_service.summarize_profile(user_id)
            )
            return
        if self._has_saved_answers(progress):
            await self.port.send_message(user_id, self._resume_message(progress))

        try:
            phase1 = progress["phase1"]
            garmin_email = await self._ask_step(
                progress,
                user_id,
                "phase1.garmin_email",
                lambda: self.port.request_text(user_id, "📧 Garmin Connect 이메일을 입력해주세요."),
            )
            garmin_connected = await self._ensure_garmin_connected(
                progress, user_id, str(garmin_email or "")
            )
            name = await self._ask_step(
                progress,
                user_id,
                "phase1.name",
                lambda: self.port.request_text(user_id, "👋 이름을 알려주세요."),
            )
            age = int(
                await self._ask_step(
                    progress,
                    user_id,
                    "phase1.age",
                    lambda: self.port.request_number(user_id, "나이를 입력해주세요.", 10, 100),
                )
            )
            sex = await self._ask_step(
                progress,
                user_id,
                "phase1.sex",
                lambda: self.port.request_select(
                    user_id,
                    "성별을 선택해주세요.",
                    [Option("남성", "male"), Option("여성", "female"), Option("기타", "other")],
                ),
            )
            height_cm = await self._ask_step(
                progress,
                user_id,
                "phase1.height_cm",
                lambda: self.port.request_number(user_id, "키(cm)를 입력해주세요.", 100, 250),
            )
            weight_kg = await self._ask_step(
                progress,
                user_id,
                "phase1.weight_kg",
                lambda: self.port.request_number(user_id, "체중(kg)를 입력해주세요.", 30, 200),
            )
            sports = await self._ask_step(
                progress,
                user_id,
                "phase1.sports",
                lambda: self.port.request_multi_select(
                    user_id,
                    "주로 하는 운동을 모두 선택해주세요.",
                    [
                        Option("러닝", "running", "🏃"),
                        Option("사이클", "cycling", "🚴"),
                        Option("수영", "swimming", "🏊"),
                        Option("트라이애슬론", "triathlon", "🔥"),
                    ],
                ),
            )
            target_event = await self._ask_step(
                progress,
                user_id,
                "phase1.target_event",
                lambda: self.port.request_text(
                    user_id,
                    "목표 대회나 이벤트가 있으면 입력해주세요. 없으면 '없음'이라고 적어주세요.",
                ),
            )
            has_goal_date = await self._ask_step(
                progress,
                user_id,
                "phase1.has_goal_date",
                lambda: self.port.request_select(
                    user_id,
                    "목표 날짜가 있나요?",
                    [Option("예", "yes"), Option("아니오", "no")],
                ),
            )
            goal_date = ""
            if has_goal_date == "yes":
                goal_date = await self._ask_step(
                    progress,
                    user_id,
                    "phase1.goal_date",
                    lambda: self.port.request_date(user_id, "목표 날짜를 입력해주세요"),
                )
            else:
                phase1.pop("goal_date", None)
            fitness_level = await self._ask_step(
                progress,
                user_id,
                "phase1.fitness_level",
                lambda: self.port.request_select(
                    user_id,
                    "현재 운동 수준을 선택해주세요.",
                    [
                        Option("초급", "beginner"),
                        Option("중급", "intermediate"),
                        Option("고급", "advanced"),
                    ],
                ),
            )
            available_days = int(
                await self._ask_step(
                    progress,
                    user_id,
                    "phase1.available_days",
                    lambda: self.port.request_number(
                        user_id, "주당 훈련 가능 일수를 입력해주세요.", 1, 7
                    ),
                )
            )
            morning_time = await self._ask_step(
                progress,
                user_id,
                "phase1.morning_time",
                lambda: self.port.request_text(
                    user_id, "아침 브리핑 시간을 입력해주세요. (예: 06:30)"
                ),
            )
            evening_time = await self._ask_step(
                progress,
                user_id,
                "phase1.evening_time",
                lambda: self.port.request_text(
                    user_id, "저녁 체크인 시간을 입력해주세요. (예: 21:30)"
                ),
            )

            if not progress["profile_created"]:
                summary = await self.onboarding_service.create_profile(
                    user_id,
                    {
                        "garmin_email": str(garmin_email or ""),
                        "garmin_connected": garmin_connected,
                        "name": str(name).strip() or "Runner",
                        "age": age,
                        "sex": sex or "other",
                        "height_cm": float(height_cm or 170.0),
                        "weight_kg": float(weight_kg or 70.0),
                        "sports": sports or ["running"],
                        "goal_event": self._goal_value(target_event),
                        "goal_date": goal_date.isoformat()
                        if isinstance(goal_date, date)
                        else str(goal_date or ""),
                        "fitness_level": fitness_level or "intermediate",
                        "available_days": available_days or 4,
                        "morning_time": self._normalize_time(str(morning_time or ""), "06:00"),
                        "evening_time": self._normalize_time(str(evening_time or ""), "22:00"),
                        "weight_goal": "maintain",
                        "dietary_style": "omnivore",
                    },
                )
                progress["profile_created"] = True
                progress["status"] = "in_progress"
                progress["current_step"] = "phase2.entry"
                await self.onboarding_service.save_progress(user_id, progress)
                await self.port.send_message(
                    user_id,
                    f"{summary}\n\n🟢 기본 온보딩(Phase 1)이 완료되어 코칭을 바로 시작할 수 있어요.",
                )

            if await self._should_collect_optional_phase(
                progress,
                user_id,
                "phase2",
                "추가 건강/영양/수면 설정(권장)을 지금 이어서 진행할까요?",
            ):
                await self._collect_phase2(progress, user_id)
            if await self._should_collect_optional_phase(
                progress,
                user_id,
                "phase3",
                "마지막으로 코칭 선호 설정(선택)을 진행할까요?",
            ):
                await self._collect_phase3(progress, user_id)

            await self.onboarding_service.clear_progress(user_id)
            await self.port.send_message(
                user_id,
                "✅ Stream 3 온보딩이 완료되었어요. 이후 변경은 /settings 에서 언제든 수정할 수 있어요.",
            )
        except InputAborted as exc:
            progress["status"] = exc.reason.value
            await self.onboarding_service.save_progress(user_id, progress)
            if exc.reason == InputAbortReason.TIMEOUT:
                await self.port.send_message(
                    user_id,
                    "⏱️ 온보딩 입력 시간이 초과되어 여기까지 저장했어요. /start 로 마지막 단계부터 이어서 진행할 수 있어요.",
                )
            elif exc.reason == InputAbortReason.SKIPPED:
                await self.port.send_message(
                    user_id,
                    "⏭️ 이 단계는 건너뛰었어요. /start 로 마지막 단계부터 이어서 진행할 수 있어요.",
                )
            else:
                await self.port.send_message(
                    user_id,
                    "⏹️ 온보딩을 중단했어요. /start 로 마지막 단계부터 이어서 진행할 수 있어요.",
                )

    async def _collect_phase2(self, progress: dict[str, Any], user_id: str) -> None:
        allergies = await self._ask_step(
            progress,
            user_id,
            "phase2.allergies",
            lambda: self.port.request_text(
                user_id,
                "알레르기나 피해야 할 음식이 있으면 입력해주세요. 없으면 '없음'이라고 적어주세요.",
            ),
        )
        food_restrictions = await self._ask_step(
            progress,
            user_id,
            "phase2.food_restrictions",
            lambda: self.port.request_text(
                user_id,
                "식이 제한이나 선호가 있으면 입력해주세요. 없으면 '없음'이라고 적어주세요.",
            ),
        )
        beta_blocker = await self._ask_step(
            progress,
            user_id,
            "phase2.beta_blocker",
            lambda: self.port.request_select(
                user_id,
                "베타차단제 등 심박 반응에 영향을 줄 수 있는 약을 복용 중인가요?",
                [Option("예", "yes"), Option("아니오", "no")],
            ),
        )
        current_injuries = await self._ask_step(
            progress,
            user_id,
            "phase2.current_injuries",
            lambda: self.port.request_text(
                user_id,
                "현재 통증이나 부상 부위가 있으면 입력해주세요. 없으면 '없음'이라고 적어주세요.",
            ),
        )
        medical_notes = await self._ask_step(
            progress,
            user_id,
            "phase2.medical_notes",
            lambda: self.port.request_text(
                user_id,
                "운동 코칭에 참고해야 할 건강 메모가 있으면 입력해주세요. 없으면 '없음'이라고 적어주세요.",
            ),
        )
        bedtime = await self._ask_step(
            progress,
            user_id,
            "phase2.bedtime",
            lambda: self.port.request_text(user_id, "평소 취침 시간을 입력해주세요. (예: 23:00)"),
        )
        wake_time = await self._ask_step(
            progress,
            user_id,
            "phase2.wake_time",
            lambda: self.port.request_text(user_id, "평소 기상 시간을 입력해주세요. (예: 07:00)"),
        )
        sleep_issues = await self._ask_step(
            progress,
            user_id,
            "phase2.sleep_issues",
            lambda: self.port.request_text(
                user_id,
                "수면 관련 이슈가 있으면 입력해주세요. 없으면 '없음'이라고 적어주세요.",
            ),
        )
        await self.onboarding_service.update_profile_sections(
            user_id,
            {
                "medical": {
                    "beta_blocker": beta_blocker == "yes",
                    "current_injuries": self._to_list(current_injuries),
                    "notes": self._optional_text(medical_notes),
                },
                "nutrition": {
                    "allergies": self._to_list(allergies),
                    "food_restrictions": self._to_list(food_restrictions),
                },
                "sleep": {
                    "bedtime": self._normalize_time(str(bedtime or ""), "23:00"),
                    "wake_time": self._normalize_time(str(wake_time or ""), "07:00"),
                    "issues": self._to_list(sleep_issues),
                },
            },
        )
        progress["phase2_status"] = "completed"
        progress["status"] = "in_progress"
        progress["current_step"] = "phase3.entry"
        await self.onboarding_service.save_progress(user_id, progress)

    async def _collect_phase3(self, progress: dict[str, Any], user_id: str) -> None:
        preferred_training_time = await self._ask_step(
            progress,
            user_id,
            "phase3.preferred_training_time",
            lambda: self.port.request_select(
                user_id,
                "선호하는 훈련 시간을 선택해주세요.",
                [
                    Option("아침", "morning"),
                    Option("저녁", "evening"),
                    Option("유동적", "flexible"),
                ],
            ),
        )
        cross_training_preferences = await self._ask_step(
            progress,
            user_id,
            "phase3.cross_training_preferences",
            lambda: self.port.request_multi_select(
                user_id,
                "선호하는 크로스트레이닝을 모두 선택해주세요.",
                [
                    Option("근력", "strength"),
                    Option("요가", "yoga"),
                    Option("사이클", "cycling"),
                    Option("수영", "swimming"),
                ],
            ),
        )
        ai_tone = await self._ask_step(
            progress,
            user_id,
            "phase3.ai_tone",
            lambda: self.port.request_select(
                user_id,
                "AI 코치 톤을 선택해주세요.",
                [
                    Option("응원형", "encouraging"),
                    Option("직설형", "direct"),
                    Option("분석형", "analytical"),
                ],
            ),
        )
        notification_frequency = await self._ask_step(
            progress,
            user_id,
            "phase3.notification_frequency",
            lambda: self.port.request_select(
                user_id,
                "알림 빈도를 선택해주세요.",
                [Option("적게", "low"), Option("기본", "default"), Option("자주", "high")],
            ),
        )
        units = await self._ask_step(
            progress,
            user_id,
            "phase3.units",
            lambda: self.port.request_select(
                user_id,
                "단위를 선택해주세요.",
                [Option("미터법", "metric"), Option("영미권", "imperial")],
            ),
        )
        timezone = await self._ask_step(
            progress,
            user_id,
            "phase3.timezone",
            lambda: self.port.request_text(user_id, "시간대를 입력해주세요. (예: Asia/Seoul)"),
        )
        strava_connected = await self._ask_step(
            progress,
            user_id,
            "phase3.strava_connected",
            lambda: self.port.request_select(
                user_id,
                "Strava 연동을 이미 사용 중인가요?",
                [Option("예", "yes"), Option("아니오", "no")],
            ),
        )
        await self.onboarding_service.update_profile_sections(
            user_id,
            {
                "preferences": {
                    "preferred_training_time": preferred_training_time,
                    "cross_training_preferences": cross_training_preferences,
                    "ai_tone": ai_tone,
                    "notification_frequency": notification_frequency,
                    "units": units,
                    "timezone": str(timezone or "Asia/Seoul").strip() or "Asia/Seoul",
                    "strava_connected": strava_connected == "yes",
                }
            },
        )
        progress["phase3_status"] = "completed"
        progress["status"] = "in_progress"
        progress["current_step"] = "done"
        await self.onboarding_service.save_progress(user_id, progress)

    async def _ensure_garmin_connected(
        self, progress: dict[str, Any], user_id: str, garmin_email: str
    ) -> bool:
        phase1 = progress["phase1"]
        if phase1.get("garmin_connected") is True:
            return True
        progress["current_step"] = "phase1.garmin_auth"
        progress["status"] = "in_progress"
        await self.onboarding_service.save_progress(user_id, progress)
        while True:
            password = await self.port.request_text(
                user_id,
                "🔑 Garmin Connect 비밀번호를 입력해주세요.\n(로컬 인증에만 사용되며 저장하지 않습니다)",
            )
            if await self.onboarding_service.connect_garmin(user_id, garmin_email, password):
                phase1["garmin_connected"] = True
                progress["current_step"] = "phase1.name"
                await self.onboarding_service.save_progress(user_id, progress)
                await self.port.send_message(user_id, "✅ Garmin 계정 연결을 확인했어요.")
                return True
            retry = await self.port.request_select(
                user_id,
                "⚠️ Garmin 연결에 실패했어요. 다시 시도할까요?",
                [Option("다시 시도", "retry"), Option("나중에 계속", "later")],
            )
            if retry != "retry":
                progress["status"] = InputAbortReason.CANCELLED.value
                progress["current_step"] = "phase1.garmin_auth"
                await self.onboarding_service.save_progress(user_id, progress)
                raise InputAborted(InputType.TEXT, InputAbortReason.CANCELLED)

    async def _should_collect_optional_phase(
        self, progress: dict[str, Any], user_id: str, phase: str, prompt: str
    ) -> bool:
        status_key = f"{phase}_status"
        current_step = str(progress.get("current_step", ""))
        if progress.get(status_key) == "completed":
            return False
        if current_step.startswith(f"{phase}.") and current_step != f"{phase}.entry":
            return True
        if self._has_phase_data(progress, phase):
            return True
        progress["current_step"] = f"{phase}.entry"
        progress["status"] = "in_progress"
        await self.onboarding_service.save_progress(user_id, progress)
        decision = await self.port.request_select(
            user_id,
            prompt,
            [Option("계속 진행", "continue"), Option("지금은 건너뛰기", "skip")],
        )
        if decision == "continue":
            progress[status_key] = "in_progress"
            progress["current_step"] = f"{phase}.{self._first_phase_step(phase)}"
            await self.onboarding_service.save_progress(user_id, progress)
            return True
        progress[status_key] = InputAbortReason.SKIPPED.value
        progress["status"] = "in_progress"
        progress["current_step"] = "phase3.entry" if phase == "phase2" else "done"
        await self.onboarding_service.save_progress(user_id, progress)
        return False

    async def _ask_step(
        self,
        progress: dict[str, Any],
        user_id: str,
        step_id: str,
        loader: Any,
    ) -> Any:
        section, key = step_id.split(".", 1)
        values = progress[section]
        if key in values:
            value = values[key]
            if key == "goal_date" and isinstance(value, str):
                return date.fromisoformat(value)
            return value
        progress["status"] = "in_progress"
        progress["current_step"] = step_id
        await self.onboarding_service.save_progress(user_id, progress)
        value = await loader()
        values[key] = value.isoformat() if isinstance(value, date) else value
        await self.onboarding_service.save_progress(user_id, progress)
        return value

    def _normalize_progress(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = {
            "schema_version": payload.get("schema_version", 2),
            "status": payload.get("status", "in_progress"),
            "current_step": payload.get("current_step", "phase1.garmin_email"),
            "profile_created": bool(payload.get("profile_created", False)),
            "phase1": dict(payload.get("phase1", {})),
            "phase2": dict(payload.get("phase2", {})),
            "phase3": dict(payload.get("phase3", {})),
            "phase2_status": payload.get("phase2_status", "pending"),
            "phase3_status": payload.get("phase3_status", "pending"),
        }
        if "schema_version" not in payload:
            normalized["phase1"] = dict(payload)
        return normalized

    def _has_saved_answers(self, progress: dict[str, Any]) -> bool:
        return any(progress[section] for section in ("phase1", "phase2", "phase3"))

    def _has_phase_data(self, progress: dict[str, Any], phase: str) -> bool:
        return bool(progress.get(phase, {}))

    def _has_pending_progress(self, progress: dict[str, Any]) -> bool:
        return self._has_saved_answers(progress) and (
            progress.get("phase2_status") != "completed"
            or progress.get("phase3_status") != "completed"
            or str(progress.get("current_step", "")).startswith(("phase2.", "phase3."))
        )

    def _resume_message(self, progress: dict[str, Any]) -> str:
        status = progress.get("status")
        if status == InputAbortReason.TIMEOUT.value:
            prefix = "이전에 시간이 초과된 지점부터"
        elif status == InputAbortReason.CANCELLED.value:
            prefix = "이전에 중단한 지점부터"
        elif status == InputAbortReason.SKIPPED.value:
            prefix = "이전에 건너뛴 지점부터"
        else:
            prefix = "이전에 저장한 지점부터"
        return f"{prefix} 온보딩을 이어서 진행할게요."

    def _first_phase_step(self, phase: str) -> str:
        return {"phase2": "allergies", "phase3": "preferred_training_time"}[phase]

    def _goal_value(self, value: Any) -> str:
        text = str(value or "").strip()
        return "" if text.lower() in {"", "없음", "none"} else text

    def _optional_text(self, value: Any) -> str:
        text = str(value or "").strip()
        return "" if text.lower() in {"", "없음", "none"} else text

    def _to_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = self._optional_text(value)
        if not text:
            return []
        return [item.strip() for item in text.split(",") if item.strip()]

    def _normalize_time(self, raw: str, default: str) -> str:
        value = (raw or "").strip()
        parts = value.split(":")
        if len(parts) == 2 and all(part.isdigit() for part in parts):
            hour = int(parts[0])
            minute = int(parts[1])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"
        return default
