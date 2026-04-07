from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .coaching import SessionType


class FeedbackCompletion(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"
    UNKNOWN = "unknown"


@dataclass
class PainReport:
    body_part: str
    severity: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "body_part": self.body_part,
            "severity": self.severity,
            "description": self.description,
        }


@dataclass
class SessionFeedback:
    session_date: str
    activity_id: str | None = None
    session_type: SessionType | None = None
    completion: FeedbackCompletion = FeedbackCompletion.UNKNOWN
    feeling: str | None = None
    rpe: int | None = None
    pain_report: PainReport | None = None
    during_nutrition: str | None = None
    note: str = ""
    flagged_for_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_date": self.session_date,
            "activity_id": self.activity_id,
            "session_type": self.session_type.value if self.session_type else None,
            "completion": self.completion.value,
            "feeling": self.feeling,
            "rpe": self.rpe,
            "pain_report": self.pain_report.to_dict() if self.pain_report else None,
            "during_nutrition": self.during_nutrition,
            "note": self.note,
            "flagged_for_review": self.flagged_for_review,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionFeedback":
        pain = payload.get("pain_report")
        session_type = payload.get("session_type")
        return cls(
            session_date=str(payload.get("session_date", "")),
            activity_id=payload.get("activity_id"),
            session_type=SessionType(session_type) if session_type else None,
            completion=FeedbackCompletion(
                payload.get("completion", FeedbackCompletion.UNKNOWN.value)
            ),
            feeling=payload.get("feeling"),
            rpe=payload.get("rpe"),
            pain_report=PainReport(**pain) if isinstance(pain, dict) else None,
            during_nutrition=payload.get("during_nutrition"),
            note=payload.get("note", ""),
            flagged_for_review=bool(payload.get("flagged_for_review", False)),
        )


@dataclass
class WeeklyFeedbackSummary:
    average_rpe: float | None = None
    pain_reports: int = 0
    missed_key_sessions: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "average_rpe": self.average_rpe,
            "pain_reports": self.pain_reports,
            "missed_key_sessions": self.missed_key_sessions,
            "notes": self.notes,
        }
