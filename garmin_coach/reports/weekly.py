from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from garmin_coach.feedback import FeedbackAggregatorService
from garmin_coach.models.feedback import FeedbackSummary
from garmin_coach.models.reporting import (
    WeeklyRecoverySummary,
    WeeklyReport,
    WeeklyReportSummary,
    WeeklyTrainingLoadSummary,
)
from garmin_coach.storage.database import GarminCoachDatabase


@dataclass
class WeeklyReportGenerator:
    database: GarminCoachDatabase
    feedback_service: FeedbackAggregatorService

    async def generate(
        self,
        user_id: str,
        *,
        end_date: date | None = None,
        window_days: int = 7,
        label: str = "최근 7일",
        coach_comment: str = "",
    ) -> WeeklyReport:
        end = end_date or date.today()
        start = end - timedelta(days=window_days - 1)
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=window_days - 1)
        activities = self._activities_in_period(user_id, start, end)
        previous_activities = self._activities_in_period(user_id, prev_start, prev_end)
        feedback_summary = self.feedback_service.get_feedback_summary(
            user_id, days=window_days, end_date=end
        )
        recovery_summary, training_load_summary, missing = self._health_sections(
            user_id, start, end
        )

        summary = WeeklyReportSummary(
            sessions=len(activities),
            total_distance_km=(
                round(sum(self._float(item.get("distance_km")) for item in activities), 1)
                if activities
                else None
            ),
            prev_distance_km=(
                round(sum(self._float(item.get("distance_km")) for item in previous_activities), 1)
                if previous_activities
                else None
            ),
            total_time=(
                self._format_hours(
                    sum(self._float(item.get("duration_min")) for item in activities)
                )
                if activities
                else None
            ),
        )
        if not activities:
            missing.append("선택 기간에 운동 활동이 없어 거리·시간 합계를 계산하지 못했습니다.")
        final_comment = coach_comment or self._default_comment(summary, feedback_summary, missing)
        return WeeklyReport(
            period=label,
            summary=summary,
            training_load=training_load_summary,
            recovery=recovery_summary,
            feedback=feedback_summary,
            missing_data_notes=missing,
            coach_comment=final_comment,
        )

    def _activities_in_period(self, user_id: str, start: date, end: date) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for payload in self.database.list_recent_activities(user_id, limit=365):
            try:
                start_time = str(payload.get("start_time") or "")
                activity_date = datetime.fromisoformat(start_time).date() if start_time else None
            except Exception:
                activity_date = None
            if activity_date and start <= activity_date <= end:
                results.append(payload)
        results.sort(key=lambda item: str(item.get("activity_id") or ""))
        return results

    def _health_sections(
        self, user_id: str, start: date, end: date
    ) -> tuple[WeeklyRecoverySummary | None, WeeklyTrainingLoadSummary | None, list[str]]:
        rows = [
            row
            for row in self.database.list_recent_daily_health(user_id, limit=90)
            if start.isoformat()
            <= str(row.get("metric_date") or row.get("date") or "")
            <= end.isoformat()
            or start.isoformat() <= str(row.get("date") or "") <= end.isoformat()
        ]
        missing: list[str] = []
        sleep_scores = [self._nested_float(row, "sleep", "overallScore") for row in rows]
        sleep_scores = [value for value in sleep_scores if value is not None]
        body_battery = [self._nested_float(row, "body_battery", "morning_value") for row in rows]
        body_battery = [value for value in body_battery if value is not None]
        recovery = None
        if rows:
            recovery = WeeklyRecoverySummary(
                avg_sleep=(
                    f"{round(sum(sleep_scores) / len(sleep_scores))}/100" if sleep_scores else None
                ),
                avg_sleep_score=(
                    round(sum(sleep_scores) / len(sleep_scores), 1) if sleep_scores else None
                ),
                avg_body_battery=(
                    round(sum(body_battery) / len(body_battery), 1) if body_battery else None
                ),
            )
        else:
            missing.append("회복 데이터가 부족해 수면/Body Battery 평균을 표시하지 못했습니다.")

        day_payload = self.database.load_daily_health(user_id, end.isoformat()) or {}
        training_payload = day_payload.get("training_load") if isinstance(day_payload, dict) else {}
        training = None
        if training_payload:
            training = WeeklyTrainingLoadSummary(
                ctl=self._float(training_payload.get("ctl")),
                atl=self._float(training_payload.get("atl")),
                tsb=self._float(training_payload.get("tsb")),
                ramp_rate=self._float(training_payload.get("ramp_rate")),
            )
        else:
            missing.append(
                "해당 기간 말일의 training load 데이터가 없어 CTL/ATL/TSB를 계산하지 못했습니다."
            )
        return recovery, training, missing

    def _default_comment(
        self,
        summary: WeeklyReportSummary,
        feedback: FeedbackSummary,
        missing: list[str],
    ) -> str:
        if missing and summary.sessions == 0:
            return "데이터가 충분하지 않아 보수적으로만 해석할 수 있습니다. 다음 동기화 후 다시 리포트를 생성해 주세요."
        if feedback.pain_reports:
            return "최근 통증 피드백이 있어 다음 주는 보수적으로 조정하는 편이 안전합니다."
        if summary.total_distance_km is None:
            return "활동 데이터가 부족해 추세 해석이 제한됩니다."
        return "최근 저장된 활동과 피드백만 기반으로 요약했습니다."

    def _float(self, value: Any) -> float:
        return float(value or 0.0)

    def _nested_float(self, payload: dict[str, Any], outer: str, inner: str) -> float | None:
        nested = payload.get(outer)
        if isinstance(nested, dict) and nested.get(inner) is not None:
            return float(nested[inner])
        return None

    def _format_hours(self, total_minutes: float) -> str:
        return f"{round(total_minutes / 60.0, 1)}h"
