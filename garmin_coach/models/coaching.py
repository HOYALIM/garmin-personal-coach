from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SessionType(str, Enum):
    REST = "rest"
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    LONG = "long"
    INTERVAL = "interval"
    TEMPO = "tempo"
    RACE = "race"
    CROSS = "cross"


@dataclass
class DayPlan:
    date: str
    session_type: SessionType
    description: str
    target_tss: float = 0.0
    rationale: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "date": self.date,
            "session_type": self.session_type.value,
            "description": self.description,
            "target_tss": self.target_tss,
            "rationale": self.rationale,
        }


@dataclass
class WeeklyPlan:
    days: list[DayPlan] = field(default_factory=list)
    total_tss: float = 0.0
    notes: list[str] = field(default_factory=list)
    focus: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "days": [day.to_dict() for day in self.days],
            "total_tss": self.total_tss,
            "notes": self.notes,
            "focus": self.focus,
        }


@dataclass
class WorkoutAnalysis:
    summary: str
    zone_distribution: dict[str, float] = field(default_factory=dict)
    comparison_to_recent: str = ""
    pace_drift: float | None = None
    coaching_notes: list[str] = field(default_factory=list)
    recovery_recommendation: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "zone_distribution": self.zone_distribution,
            "comparison_to_recent": self.comparison_to_recent,
            "pace_drift": self.pace_drift,
            "coaching_notes": self.coaching_notes,
            "recovery_recommendation": self.recovery_recommendation,
        }


@dataclass
class CoachingResponse:
    text: str
    intensity: str
    max_zone: int = 2
    uses_hr_zones: bool = True
    session_type: SessionType = SessionType.EASY
    guardrail_applied: bool = False
    guardrail_reason: str | None = None
    guardrail_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "intensity": self.intensity,
            "max_zone": self.max_zone,
            "uses_hr_zones": self.uses_hr_zones,
            "session_type": self.session_type.value,
            "guardrail_applied": self.guardrail_applied,
            "guardrail_reason": self.guardrail_reason,
            "guardrail_reasons": self.guardrail_reasons,
            "metadata": self.metadata,
        }
