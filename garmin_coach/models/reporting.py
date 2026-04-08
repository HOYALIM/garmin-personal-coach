from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .feedback import FeedbackSummary


@dataclass
class WeeklyReportSummary:
    sessions: int
    total_distance_km: float | None = None
    prev_distance_km: float | None = None
    total_time: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sessions": self.sessions,
            "total_distance_km": self.total_distance_km,
            "prev_distance_km": self.prev_distance_km,
            "total_time": self.total_time,
        }


@dataclass
class WeeklyRecoverySummary:
    avg_sleep: str | None = None
    avg_sleep_score: float | None = None
    hrv_trend: str | None = None
    avg_body_battery: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "avg_sleep": self.avg_sleep,
            "avg_sleep_score": self.avg_sleep_score,
            "hrv_trend": self.hrv_trend,
            "avg_body_battery": self.avg_body_battery,
        }


@dataclass
class WeeklyTrainingLoadSummary:
    ctl: float | None = None
    atl: float | None = None
    tsb: float | None = None
    ramp_rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ctl": self.ctl,
            "atl": self.atl,
            "tsb": self.tsb,
            "ramp_rate": self.ramp_rate,
        }


@dataclass
class WeeklyReport:
    period: str
    summary: WeeklyReportSummary
    training_load: WeeklyTrainingLoadSummary | None = None
    recovery: WeeklyRecoverySummary | None = None
    feedback: FeedbackSummary | None = None
    missing_data_notes: list[str] | None = None
    coach_comment: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "summary": self.summary.to_dict(),
            "training_load": self.training_load.to_dict() if self.training_load else None,
            "recovery": self.recovery.to_dict() if self.recovery else None,
            "feedback": self.feedback.to_dict() if self.feedback else None,
            "missing_data_notes": list(self.missing_data_notes or []),
            "coach_comment": self.coach_comment,
        }
