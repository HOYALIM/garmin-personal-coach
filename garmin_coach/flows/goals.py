from __future__ import annotations

from typing import Protocol

from garmin_coach.ports import CoachingPort, InputAbortReason, InputAborted, Option


class GoalsService(Protocol):
    async def has_profile(self, user_id: str) -> bool: ...
    async def summarize_goals(self, user_id: str) -> str: ...
    async def update_goal_event(self, user_id: str, value: str) -> None: ...
    async def update_goal_date(self, user_id: str, value: str) -> None: ...
    async def update_fitness_level(self, user_id: str, value: str) -> None: ...
    async def update_max_weekly_hours(self, user_id: str, value: float) -> None: ...


class GoalsFlow:
    def __init__(self, port: CoachingPort, goals_service: GoalsService) -> None:
        self.port = port
        self.goals_service = goals_service

    async def execute(self, user_id: str) -> None:
        if not await self.goals_service.has_profile(user_id):
            await self.port.send_message(user_id, "먼저 /start 로 기본 설정을 완료해주세요.")
            return

        try:
            await self.port.send_message(user_id, await self.goals_service.summarize_goals(user_id))
            action = await self.port.request_select(
                user_id,
                "무엇을 수정할까요?",
                [
                    Option("목표 이벤트", "event"),
                    Option("목표 날짜", "date"),
                    Option("훈련 수준", "fitness"),
                    Option("주당 최대 시간", "hours"),
                ],
            )
            if action == "event":
                value = await self.port.request_text(
                    user_id,
                    "새 목표 이벤트를 입력해주세요. 없으면 '없음'이라고 입력해주세요.",
                )
                await self.goals_service.update_goal_event(
                    user_id,
                    "" if value.strip().lower() in {"", "없음", "none"} else value.strip(),
                )
            elif action == "date":
                has_date = await self.port.request_select(
                    user_id,
                    "목표 날짜를 설정할까요?",
                    [Option("예", "yes"), Option("삭제", "clear")],
                )
                if has_date == "yes":
                    await self.goals_service.update_goal_date(
                        user_id,
                        (
                            await self.port.request_date(user_id, "목표 날짜를 입력해주세요")
                        ).isoformat(),
                    )
                else:
                    await self.goals_service.update_goal_date(user_id, "")
            elif action == "fitness":
                await self.goals_service.update_fitness_level(
                    user_id,
                    await self.port.request_select(
                        user_id,
                        "훈련 수준을 선택해주세요.",
                        [
                            Option("초급", "beginner"),
                            Option("중급", "intermediate"),
                            Option("고급", "advanced"),
                        ],
                    ),
                )
            elif action == "hours":
                await self.goals_service.update_max_weekly_hours(
                    user_id,
                    float(
                        await self.port.request_number(
                            user_id, "주당 최대 훈련 시간을 입력해주세요.", 1, 40
                        )
                    ),
                )
            await self.port.send_message(user_id, await self.goals_service.summarize_goals(user_id))
        except InputAborted as exc:
            if exc.reason == InputAbortReason.TIMEOUT:
                await self.port.send_message(
                    user_id, "⏱️ 목표 설정 입력 시간이 초과되어 취소했어요."
                )
            else:
                await self.port.send_message(user_id, "⏹️ 목표 설정을 취소했어요.")
