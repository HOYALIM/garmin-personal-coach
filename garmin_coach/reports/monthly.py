from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from garmin_coach.feedback import FeedbackAggregatorService
from garmin_coach.models.reporting import WeeklyReport
from garmin_coach.storage.database import GarminCoachDatabase

from .weekly import WeeklyReportGenerator


@dataclass
class MonthlyReportGenerator:
    database: GarminCoachDatabase
    feedback_service: FeedbackAggregatorService

    async def generate(
        self,
        user_id: str,
        *,
        end_date: date | None = None,
        label: str = "최근 30일",
        coach_comment: str = "",
    ) -> WeeklyReport:
        generator = WeeklyReportGenerator(self.database, self.feedback_service)
        return await generator.generate(
            user_id,
            end_date=end_date,
            window_days=30,
            label=label,
            coach_comment=coach_comment,
        )
