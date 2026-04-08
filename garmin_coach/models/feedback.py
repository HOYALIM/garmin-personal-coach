from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .coaching import SessionType


class FeedbackCompletion(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"
    ABANDONED = "abandoned"
    UNKNOWN = "unknown"


class FeedbackCollectionStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass
class PainReport:
    body_part: str
    severity: str
    description: str = ""
    consecutive_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "body_part": self.body_part,
            "severity": self.severity,
            "description": self.description,
            "consecutive_count": self.consecutive_count,
        }


@dataclass
class RPEIntensityGap:
    rpe: int
    actual_avg_hr_pct: float | None = None
    expected_rpe_range: tuple[int, int] = (0, 0)
    gap_direction: str = "match"
    significance: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rpe": self.rpe,
            "actual_avg_hr_pct": self.actual_avg_hr_pct,
            "expected_rpe_range": list(self.expected_rpe_range),
            "gap_direction": self.gap_direction,
            "significance": self.significance,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RPEIntensityGap":
        expected = payload.get("expected_rpe_range") or [0, 0]
        if not isinstance(expected, (list, tuple)) or len(expected) != 2:
            expected = [0, 0]
        return cls(
            rpe=int(payload.get("rpe", 0)),
            actual_avg_hr_pct=(
                float(payload["actual_avg_hr_pct"])
                if payload.get("actual_avg_hr_pct") is not None
                else None
            ),
            expected_rpe_range=(int(expected[0]), int(expected[1])),
            gap_direction=str(payload.get("gap_direction", "match")),
            significance=str(payload.get("significance", "normal")),
        )


@dataclass
class SessionFeedback:
    session_date: str
    activity_id: str | None = None
    session_type: SessionType | None = None
    completion: FeedbackCompletion = FeedbackCompletion.UNKNOWN
    collection_status: FeedbackCollectionStatus = FeedbackCollectionStatus.COMPLETE
    feeling: str | None = None
    rpe: int | None = None
    target_pace_met: bool | None = None
    pain_report: PainReport | None = None
    during_nutrition: str | None = None
    gi_issues: bool | None = None
    note: str = ""
    flagged_for_review: bool = False
    answered_keys: list[str] = field(default_factory=list)
    pending_keys: list[str] = field(default_factory=list)
    source_event_id: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_date": self.session_date,
            "activity_id": self.activity_id,
            "session_type": self.session_type.value if self.session_type else None,
            "completion": self.completion.value,
            "collection_status": self.collection_status.value,
            "feeling": self.feeling,
            "rpe": self.rpe,
            "target_pace_met": self.target_pace_met,
            "pain_report": self.pain_report.to_dict() if self.pain_report else None,
            "during_nutrition": self.during_nutrition,
            "gi_issues": self.gi_issues,
            "note": self.note,
            "flagged_for_review": self.flagged_for_review,
            "answered_keys": self.answered_keys,
            "pending_keys": self.pending_keys,
            "source_event_id": self.source_event_id,
            "updated_at": self.updated_at,
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
            collection_status=FeedbackCollectionStatus(
                payload.get("collection_status", FeedbackCollectionStatus.COMPLETE.value)
            ),
            feeling=payload.get("feeling"),
            rpe=payload.get("rpe"),
            target_pace_met=payload.get("target_pace_met"),
            pain_report=PainReport(**pain) if isinstance(pain, dict) else None,
            during_nutrition=payload.get("during_nutrition"),
            gi_issues=payload.get("gi_issues"),
            note=payload.get("note", ""),
            flagged_for_review=bool(payload.get("flagged_for_review", False)),
            answered_keys=[str(item) for item in payload.get("answered_keys", [])],
            pending_keys=[str(item) for item in payload.get("pending_keys", [])],
            source_event_id=payload.get("source_event_id"),
            updated_at=payload.get("updated_at"),
        )


@dataclass
class FeedbackSummary:
    average_rpe: float | None = None
    pain_reports: int = 0
    missed_key_sessions: int = 0
    pace_achievement_rate: float | None = None
    gi_issue_reports: int = 0
    completed_feedbacks: int = 0
    partial_feedbacks: int = 0
    skipped_feedbacks: int = 0
    rpe_intensity_gaps: list[RPEIntensityGap] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "average_rpe": self.average_rpe,
            "pain_reports": self.pain_reports,
            "missed_key_sessions": self.missed_key_sessions,
            "pace_achievement_rate": self.pace_achievement_rate,
            "gi_issue_reports": self.gi_issue_reports,
            "completed_feedbacks": self.completed_feedbacks,
            "partial_feedbacks": self.partial_feedbacks,
            "skipped_feedbacks": self.skipped_feedbacks,
            "rpe_intensity_gaps": [gap.to_dict() for gap in self.rpe_intensity_gaps],
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FeedbackSummary":
        return cls(
            average_rpe=(
                float(payload["average_rpe"]) if payload.get("average_rpe") is not None else None
            ),
            pain_reports=int(payload.get("pain_reports", 0)),
            missed_key_sessions=int(payload.get("missed_key_sessions", 0)),
            pace_achievement_rate=(
                float(payload["pace_achievement_rate"])
                if payload.get("pace_achievement_rate") is not None
                else None
            ),
            gi_issue_reports=int(payload.get("gi_issue_reports", 0)),
            completed_feedbacks=int(payload.get("completed_feedbacks", 0)),
            partial_feedbacks=int(payload.get("partial_feedbacks", 0)),
            skipped_feedbacks=int(payload.get("skipped_feedbacks", 0)),
            rpe_intensity_gaps=[
                RPEIntensityGap.from_dict(item)
                for item in payload.get("rpe_intensity_gaps", [])
                if isinstance(item, dict)
            ],
            notes=[str(item) for item in payload.get("notes", [])],
        )


@dataclass
class WeeklyFeedbackSummary(FeedbackSummary):
    pass
