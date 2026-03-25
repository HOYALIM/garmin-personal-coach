"""Structured data models for Garmin Personal Coach."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Status(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class Phase(str, Enum):
    PRECHECK = "precheck"
    FINAL = "final"


class SessionClass(str, Enum):
    EASY = "easy"
    RECOVERY = "recovery"
    THRESHOLD = "threshold"
    MP = "mp"
    LONG_RUN = "long_run"
    REST = "rest"
    STRENGTH_SUPPORTED = "strength_supported"
    AEROBIC = "aerobic"
    UNKNOWN = "unknown"


@dataclass
class MorningMetrics:
    sleep_hours: float | None = None
    resting_hr: int | None = None
    rhr_baseline: float | None = None
    body_battery: int | None = None
    training_readiness: int | None = None
    hrv_status: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MorningResult:
    date: str
    phase: Phase
    week: int
    planned_session: str
    recommended_session: str
    status: Status
    reasons: list[str]
    total_score: int
    week_brief: str
    session_purpose: str
    execution_guidance: list[str]
    pace_hr_guidance: str
    downgrade_rule: str
    metrics: MorningMetrics
    freshness: dict[str, bool]
    session_class: SessionClass = SessionClass.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "phase": self.phase.value,
            "week": self.week,
            "planned_session": self.planned_session,
            "recommended_session": self.recommended_session,
            "status": self.status.value,
            "reasons": self.reasons,
            "total_score": self.total_score,
            "week_brief": self.week_brief,
            "session_purpose": self.session_purpose,
            "execution_guidance": self.execution_guidance,
            "pace_hr_guidance": self.pace_hr_guidance,
            "downgrade_rule": self.downgrade_rule,
            "session_class": self.session_class.value,
            "metrics": {
                "sleep_hours": self.metrics.sleep_hours,
                "resting_hr": self.metrics.resting_hr,
                "rhr_baseline": self.metrics.rhr_baseline,
                "body_battery": self.metrics.body_battery,
                "training_readiness": self.metrics.training_readiness,
                "hrv_status": self.metrics.hrv_status,
            },
            "freshness": self.freshness,
        }

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "plan_week": self.week,
            "planned_session": self.planned_session,
            "phase": self.phase.value,
            "status": self.status.value,
            "recommended_session": self.recommended_session,
            "score": self.total_score,
            "why": self.reasons,
            "week_brief": self.week_brief,
            "session_purpose": self.session_purpose,
            "session_class": self.session_class.value,
            "metrics": {
                "sleep_hours": self.metrics.sleep_hours,
                "resting_hr": self.metrics.resting_hr,
                "rhr_baseline": self.metrics.rhr_baseline,
                "body_battery": self.metrics.body_battery,
                "training_readiness": self.metrics.training_readiness,
                "hrv_status": self.metrics.hrv_status,
            },
            "freshness": self.freshness,
            "summary": self.format_message(),
        }

    def format_message(self) -> str:
        icon = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(self.status.value, "⚪")
        label = "PRECHECK" if self.phase == Phase.PRECHECK else "FINAL CALL"
        reason_text = ", ".join(self.reasons[:3]) if self.reasons else "metrics normal"
        lines = [
            f"{icon} {label} — {self.recommended_session}",
            f"Why: {reason_text}",
            "",
            f"Week {self.week} brief: {self.week_brief}",
            f"Session purpose: {self.session_purpose}",
            "",
            "Details:",
            f"- Planned: {self.planned_session}",
            f"- Today: {self.recommended_session}",
            f"- Sleep: {self.metrics.sleep_hours if self.metrics.sleep_hours is not None else 'n/a'}h",
            f"- RHR: {self.metrics.resting_hr if self.metrics.resting_hr is not None else 'n/a'} "
            f"(baseline {round(self.metrics.rhr_baseline, 1) if self.metrics.rhr_baseline is not None else 'n/a'})",
            f"- Readiness: {self.metrics.training_readiness if self.metrics.training_readiness is not None else 'n/a'}",
            f"- Body battery: {self.metrics.body_battery if self.metrics.body_battery is not None else 'n/a'}",
            "- How:",
        ]
        for item in self.execution_guidance:
            lines.append(f"  - {item}")
        lines.append(f"- {self.pace_hr_guidance}")
        lines.append(f"- {self.downgrade_rule}")
        lines.append(
            f"- [{'PRECHECK' if self.phase == Phase.PRECHECK else 'FINAL CALL'}]"
        )
        return "\n".join(lines)


@dataclass
class ActivitySummary:
    activity_id: str | None = None
    type: str | None = None
    start_time: str | None = None
    distance_km: float | None = None
    duration_min: float | None = None
    avg_pace: str | None = None
    avg_hr: int | None = None
    calories: int | None = None
    training_effect: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "start_time": self.start_time,
            "distance_km": self.distance_km,
            "duration_min": self.duration_min,
            "avg_pace": self.avg_pace,
            "avg_hr": self.avg_hr,
            "calories": self.calories,
            "training_effect": self.training_effect,
        }


@dataclass
class SubjectiveRating:
    energy: int = 3
    legs: int = 2
    mood: int = 3
    pain: bool = False
    illness: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "energy": self.energy,
            "legs": self.legs,
            "mood": self.mood,
            "pain": self.pain,
            "illness": self.illness,
        }


@dataclass
class WorkoutLog:
    date: str
    planned: str | None = None
    final_status: str | None = None
    activity: ActivitySummary | None = None
    completed: str | None = None
    subjective: SubjectiveRating | None = None
    coach_note: str = ""
    tomorrow_note: str = ""
    source: str = "unknown"  # garmin | manual | strava | unknown
    synced: dict[str, bool] = field(
        default_factory=lambda: {
            "markdown": False,
            "calendar": False,
            "garmin_writeback": False,
        }
    )
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "planned": self.planned,
            "final_status": self.final_status,
            "activity": self.activity.to_dict() if self.activity else None,
            "completed": self.completed,
            "subjective": self.subjective.to_dict() if self.subjective else None,
            "coach_note": self.coach_note,
            "tomorrow_note": self.tomorrow_note,
            "source": self.source,
            "synced": self.synced,
            "updated_at": self.updated_at or datetime.now().isoformat(),
        }
