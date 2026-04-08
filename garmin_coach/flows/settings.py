from __future__ import annotations

from typing import Protocol

from garmin_coach.ports import CoachingPort, InputAbortReason, InputAborted, Option


class SettingsService(Protocol):
    async def has_profile(self, user_id: str) -> bool: ...
    async def summarize_settings(self, user_id: str) -> str: ...
    async def update_profile_name(self, user_id: str, value: str) -> None: ...
    async def update_weight(self, user_id: str, value: float) -> None: ...
    async def update_available_days(self, user_id: str, value: int) -> None: ...
    async def update_schedule(self, user_id: str, field: str, value: str) -> None: ...
    async def update_nutrition(
        self, user_id: str, weight_goal: str, dietary_style: str
    ) -> None: ...
    async def update_medical(
        self, user_id: str, beta_blocker: bool, current_injuries: list[str], notes: str
    ) -> None: ...
    async def update_sleep(
        self, user_id: str, bedtime: str, wake_time: str, issues: list[str]
    ) -> None: ...
    async def update_preferences(
        self,
        user_id: str,
        preferred_training_time: str,
        cross_training_preferences: list[str],
        notification_frequency: str,
        units: str,
        timezone: str,
        strava_connected: bool,
    ) -> None: ...
    async def update_ai_tone(self, user_id: str, tone: str) -> None: ...


class SettingsFlow:
    def __init__(self, port: CoachingPort, settings_service: SettingsService) -> None:
        self.port = port
        self.settings_service = settings_service

    async def execute(self, user_id: str) -> None:
        if not await self.settings_service.has_profile(user_id):
            await self.port.send_message(user_id, "먼저 /start 로 기본 설정을 완료해주세요.")
            return
        try:
            category = await self.port.request_select(
                user_id,
                await self.settings_service.summarize_settings(user_id),
                [
                    Option("기본 프로필", "profile"),
                    Option("알림 시간", "schedule"),
                    Option("영양 설정", "nutrition"),
                    Option("건강 정보", "medical"),
                    Option("수면 설정", "sleep"),
                    Option("코칭 선호", "preferences"),
                    Option("AI 코치 톤", "ai"),
                ],
            )
            if category == "profile":
                await self._edit_profile(user_id)
            elif category == "schedule":
                await self._edit_schedule(user_id)
            elif category == "nutrition":
                await self._edit_nutrition(user_id)
            elif category == "medical":
                await self._edit_medical(user_id)
            elif category == "sleep":
                await self._edit_sleep(user_id)
            elif category == "preferences":
                await self._edit_preferences(user_id)
            elif category == "ai":
                await self._edit_ai(user_id)
            await self.port.send_message(user_id, "✅ 설정이 저장되었어요.")
        except InputAborted as exc:
            await self._handle_abort(user_id, exc)

    async def _edit_profile(self, user_id: str) -> None:
        field = await self.port.request_select(
            user_id,
            "수정할 프로필 항목을 선택해주세요.",
            [Option("이름", "name"), Option("체중", "weight"), Option("주당 훈련일", "days")],
        )
        if field == "name":
            await self.settings_service.update_profile_name(
                user_id, await self.port.request_text(user_id, "새 이름을 입력해주세요.")
            )
        elif field == "weight":
            await self.settings_service.update_weight(
                user_id,
                float(
                    await self.port.request_number(user_id, "새 체중(kg)을 입력해주세요.", 30, 200)
                ),
            )
        elif field == "days":
            await self.settings_service.update_available_days(
                user_id,
                int(
                    await self.port.request_number(
                        user_id, "주당 훈련 가능 일수를 입력해주세요.", 1, 7
                    )
                ),
            )

    async def _edit_schedule(self, user_id: str) -> None:
        field = await self.port.request_select(
            user_id,
            "수정할 알림 시간을 선택해주세요.",
            [Option("아침 브리핑", "morning"), Option("저녁 체크인", "evening")],
        )
        raw_time = await self.port.request_text(user_id, "새 시간을 입력해주세요. (HH:MM)")
        await self.settings_service.update_schedule(
            user_id,
            field,
            self._normalize_time(raw_time, "06:00" if field == "morning" else "22:00"),
        )

    async def _edit_nutrition(self, user_id: str) -> None:
        weight_goal = await self.port.request_select(
            user_id,
            "체중/체성분 목표를 선택해주세요.",
            [Option("유지", "maintain"), Option("감량", "lose"), Option("증량", "gain")],
        )
        dietary_style = await self.port.request_select(
            user_id,
            "식단 스타일을 선택해주세요.",
            [
                Option("일반식", "omnivore"),
                Option("채식", "vegetarian"),
                Option("비건", "vegan"),
                Option("기타", "other"),
            ],
        )
        await self.settings_service.update_nutrition(user_id, weight_goal, dietary_style)

    async def _edit_ai(self, user_id: str) -> None:
        await self.settings_service.update_ai_tone(
            user_id,
            await self.port.request_select(
                user_id,
                "AI 코치 톤을 선택해주세요.",
                [
                    Option("응원형", "encouraging"),
                    Option("직설형", "direct"),
                    Option("분석형", "analytical"),
                ],
            ),
        )

    async def _edit_medical(self, user_id: str) -> None:
        beta_blocker = await self.port.request_select(
            user_id,
            "베타차단제 등 심박 반응에 영향을 주는 약을 복용 중인가요?",
            [Option("예", "yes"), Option("아니오", "no")],
        )
        injuries = await self.port.request_text(
            user_id,
            "현재 부상/통증 부위를 입력해주세요. 없으면 '없음'이라고 적어주세요.",
        )
        notes = await self.port.request_text(
            user_id,
            "운동 시 참고해야 할 건강 메모를 입력해주세요. 없으면 '없음'이라고 적어주세요.",
        )
        await self.settings_service.update_medical(
            user_id,
            beta_blocker == "yes",
            self._to_list(injuries),
            self._optional_text(notes),
        )

    async def _edit_sleep(self, user_id: str) -> None:
        bedtime = await self.port.request_text(user_id, "평소 취침 시간을 입력해주세요. (HH:MM)")
        wake_time = await self.port.request_text(user_id, "평소 기상 시간을 입력해주세요. (HH:MM)")
        issues = await self.port.request_text(
            user_id,
            "수면 이슈가 있으면 입력해주세요. 없으면 '없음'이라고 적어주세요.",
        )
        await self.settings_service.update_sleep(
            user_id,
            self._normalize_time(bedtime, "23:00"),
            self._normalize_time(wake_time, "07:00"),
            self._to_list(issues),
        )

    async def _edit_preferences(self, user_id: str) -> None:
        preferred_training_time = await self.port.request_select(
            user_id,
            "선호하는 훈련 시간을 선택해주세요.",
            [Option("아침", "morning"), Option("저녁", "evening"), Option("유동적", "flexible")],
        )
        cross_training = await self.port.request_multi_select(
            user_id,
            "선호하는 크로스트레이닝을 모두 선택해주세요.",
            [
                Option("근력", "strength"),
                Option("요가", "yoga"),
                Option("사이클", "cycling"),
                Option("수영", "swimming"),
            ],
        )
        notification_frequency = await self.port.request_select(
            user_id,
            "알림 빈도를 선택해주세요.",
            [Option("적게", "low"), Option("기본", "default"), Option("자주", "high")],
        )
        units = await self.port.request_select(
            user_id,
            "단위를 선택해주세요.",
            [Option("미터법", "metric"), Option("영미권", "imperial")],
        )
        timezone = await self.port.request_text(user_id, "시간대를 입력해주세요. (예: Asia/Seoul)")
        strava_connected = await self.port.request_select(
            user_id,
            "Strava 연동을 이미 사용 중인가요?",
            [Option("예", "yes"), Option("아니오", "no")],
        )
        await self.settings_service.update_preferences(
            user_id,
            preferred_training_time,
            cross_training,
            notification_frequency,
            units,
            timezone.strip() or "Asia/Seoul",
            strava_connected == "yes",
        )

    def _normalize_time(self, raw: str, default: str) -> str:
        value = (raw or "").strip()
        parts = value.split(":")
        if len(parts) == 2 and all(part.isdigit() for part in parts):
            hour = int(parts[0])
            minute = int(parts[1])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"
        return default

    async def _handle_abort(self, user_id: str, exc: InputAborted) -> None:
        if exc.reason == InputAbortReason.TIMEOUT:
            await self.port.send_message(user_id, "⏱️ 입력 시간이 초과되어 설정 변경을 취소했어요.")
        else:
            await self.port.send_message(user_id, "⏹️ 설정 변경을 취소했어요.")

    def _optional_text(self, value: str) -> str:
        text = (value or "").strip()
        return "" if text.lower() in {"", "없음", "none"} else text

    def _to_list(self, value: str) -> list[str]:
        text = self._optional_text(value)
        if not text:
            return []
        return [item.strip() for item in text.split(",") if item.strip()]
