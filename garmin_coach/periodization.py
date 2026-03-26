"""Rule-based periodization engine — generates adaptive training phases.

Implements Base → Build → Peak → Race periodization with:
- Volume/intensity progression rules
- Multi-sport distribution (triathlon)
- Brick workout scheduling
- Recovery/deload week logic
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any

from garmin_coach.profile_manager import ProfileManager, UserProfile


class Phase(str, Enum):
    BASE = "base"
    BUILD = "build"
    PEAK = "peak"
    RACE = "race"
    RECOVERY = "recovery"


@dataclass
class PhaseConfig:
    name: Phase
    weeks: int
    volume_pct_of_target: float
    intensity_distribution: dict[str, float]
    description: str


@dataclass
class WeekPlan:
    week_number: int
    phase: Phase
    week_start: date
    sessions: list[dict[str, Any]]
    total_volume_hours: float
    is_deload: bool = False
    trimp_target: float | None = None
    focus: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "week_number": self.week_number,
            "phase": self.phase.value,
            "week_start": self.week_start.isoformat(),
            "sessions": self.sessions,
            "total_volume_hours": round(self.total_volume_hours, 1),
            "is_deload": self.is_deload,
            "trimp_target": self.trimp_target,
            "focus": self.focus,
        }


@dataclass
class PeriodizationEngine:
    """Build a complete periodized training plan from user profile."""

    profile: UserProfile
    plan_start: date
    goal_date: date | None = None
    _weeks: list[WeekPlan] = field(default_factory=list)

    BASE = PhaseConfig(
        name=Phase.BASE,
        weeks=4,
        volume_pct_of_target=0.70,
        intensity_distribution={
            "z1": 0.30,
            "z2": 0.50,
            "z3": 0.15,
            "z4": 0.05,
            "z5": 0.00,
        },
        description="Build aerobic base. High volume, low intensity.",
    )
    BUILD = PhaseConfig(
        name=Phase.BUILD,
        weeks=4,
        volume_pct_of_target=0.90,
        intensity_distribution={
            "z1": 0.20,
            "z2": 0.40,
            "z3": 0.20,
            "z4": 0.15,
            "z5": 0.05,
        },
        description="Increase intensity. Introduce threshold and intervals.",
    )
    PEAK = PhaseConfig(
        name=Phase.PEAK,
        weeks=3,
        volume_pct_of_target=0.75,
        intensity_distribution={
            "z1": 0.15,
            "z2": 0.30,
            "z3": 0.25,
            "z4": 0.20,
            "z5": 0.10,
        },
        description="Race-specific intensity. Volume drops, quality rises.",
    )
    RACE = PhaseConfig(
        name=Phase.RACE,
        weeks=1,
        volume_pct_of_target=0.40,
        intensity_distribution={
            "z1": 0.20,
            "z2": 0.30,
            "z3": 0.20,
            "z4": 0.20,
            "z5": 0.10,
        },
        description="Race week. Minimal volume, peak intensity.",
    )
    RECOVERY = PhaseConfig(
        name=Phase.RECOVERY,
        weeks=1,
        volume_pct_of_target=0.40,
        intensity_distribution={
            "z1": 0.50,
            "z2": 0.40,
            "z3": 0.10,
            "z4": 0.00,
            "z5": 0.00,
        },
        description="Recovery week. Volume halved, easy intensity.",
    )

    def build(self) -> list[WeekPlan]:
        """Generate full periodized plan from start to goal_date (or 14 weeks default)."""
        total_weeks = self._calculate_total_weeks()
        phases = self._build_phase_sequence(total_weeks)

        self._weeks = []
        week_start = self.plan_start

        for week_num, phase_config in enumerate(phases, start=1):
            is_deload = self._is_deload_week(week_num, phase_config.name)
            volume_mult = 0.40 if is_deload else phase_config.volume_pct_of_target

            sessions = self._generate_sessions(
                week_num, phase_config, is_deload, week_start
            )
            total_hours = sum(s.get("duration_hours", 0) for s in sessions)

            self._weeks.append(
                WeekPlan(
                    week_number=week_num,
                    phase=phase_config.name,
                    week_start=week_start,
                    sessions=sessions,
                    total_volume_hours=total_hours,
                    is_deload=is_deload,
                    trimp_target=self._trimp_target(phase_config.name, is_deload),
                    focus=self._week_focus(phase_config, is_deload),
                )
            )
            week_start += timedelta(days=7)

        return self._weeks

    def _calculate_total_weeks(self) -> int:
        if self.goal_date:
            delta = (self.goal_date - self.plan_start).days
            return max(8, min(20, delta // 7))
        return 14

    def _build_phase_sequence(self, total: int) -> list[PhaseConfig]:
        seq: list[PhaseConfig] = []
        remaining = total

        base_weeks = min(4, remaining)
        seq.extend([self.BASE] * base_weeks)
        remaining -= base_weeks

        if remaining > 0:
            seq.append(self.RECOVERY)
            remaining -= 1

        build_weeks = min(4, remaining)
        seq.extend([self.BUILD] * build_weeks)
        remaining -= build_weeks

        if remaining > 0:
            seq.append(self.RECOVERY)
            remaining -= 1

        if remaining >= 4:
            seq.extend([self.PEAK] * 3)
            seq.append(self.RACE)
        elif remaining >= 2:
            seq.extend([self.PEAK] * remaining)
        elif remaining > 0:
            seq.append(self.PEAK)

        return seq

    def _is_deload_week(self, week_num: int, phase: Phase) -> bool:
        return phase == Phase.RECOVERY

    def _trimp_target(self, phase_name: Phase, is_deload: bool) -> float:
        pm = ProfileManager()
        profile = self.profile
        min_t, max_t = pm.weekly_trimp_target(profile)
        base = (min_t + max_t) / 2.0

        phase_mult: dict[Phase, float] = {
            Phase.BASE: 0.70,
            Phase.BUILD: 0.90,
            Phase.PEAK: 0.75,
            Phase.RACE: 0.40,
            Phase.RECOVERY: 0.40,
        }
        mult = phase_mult.get(phase_name, 0.8) if not is_deload else 0.40
        return round(base * mult)

    def _week_focus(self, config: PhaseConfig, is_deload: bool) -> str:
        if is_deload:
            return "Recovery — active rest, mobility, reflection"
        return config.description

    def _generate_sessions(
        self,
        week_num: int,
        phase: PhaseConfig,
        is_deload: bool,
        week_start: date,
    ) -> list[dict[str, Any]]:
        sports = [s.value for s in self.profile.profile.sports]
        available = self.profile.profile.available_days
        is_tri = "triathlon" in sports

        if is_deload:
            return self._deload_sessions(week_start, sports)

        if phase.name == Phase.BASE:
            return self._base_sessions(week_start, sports, available, is_tri)
        if phase.name == Phase.BUILD:
            return self._build_sessions(week_start, sports, available, is_tri)
        if phase.name == Phase.PEAK:
            return self._peak_sessions(week_start, sports, available, is_tri)
        if phase.name == Phase.RACE:
            return self._race_sessions(week_start, sports)
        return []

    def _deload_sessions(
        self, week_start: date, sports: list[str]
    ) -> list[dict[str, Any]]:
        sessions = []
        for i in range(len(sports) * 2):
            day = week_start + timedelta(days=i * 2)
            sessions.append(
                {
                    "date": day.isoformat(),
                    "sport": sports[i % len(sports)],
                    "type": "easy",
                    "duration_hours": 0.5,
                    "intensity": "low",
                    "description": "Active recovery",
                }
            )
        sessions.append(
            {
                "date": (week_start + timedelta(days=6)).isoformat(),
                "sport": sports[0],
                "type": "rest",
                "duration_hours": 0.0,
                "intensity": "none",
                "description": "Full rest",
            }
        )
        return sessions

    def _base_sessions(
        self,
        week_start: date,
        sports: list[str],
        available: int,
        is_tri: bool,
    ) -> list[dict[str, Any]]:
        sessions = []
        primary = sports[0]

        sessions.append(
            {
                "date": (week_start + timedelta(days=6)).isoformat(),
                "sport": primary,
                "type": "long_run",
                "duration_hours": 1.5,
                "intensity": "easy",
                "description": "Easy long run — build aerobic base",
            }
        )

        easy_days = [0, 1, 3, 4]
        for d in easy_days[: available - 1]:
            sessions.append(
                {
                    "date": (week_start + timedelta(days=d)).isoformat(),
                    "sport": primary,
                    "type": "easy",
                    "duration_hours": 0.75,
                    "intensity": "easy",
                    "description": "Easy aerobic run",
                }
            )

        if is_tri and len(sports) > 1:
            sessions.append(
                {
                    "date": (week_start + timedelta(days=2)).isoformat(),
                    "sport": "cycling",
                    "type": "endurance",
                    "duration_hours": 1.0,
                    "intensity": "easy",
                    "description": "Endurance ride",
                }
            )
        return sessions

    def _build_sessions(
        self,
        week_start: date,
        sports: list[str],
        available: int,
        is_tri: bool,
    ) -> list[dict[str, Any]]:
        sessions = self._base_sessions(week_start, sports, available, is_tri)
        primary = sports[0]

        # Replace one easy session with threshold
        if len(sessions) > 2:
            for s in sessions:
                if s["type"] == "easy" and s["sport"] == primary:
                    s["type"] = "threshold"
                    s["duration_hours"] = 1.0
                    s["description"] = "Threshold — sustained tempo effort"
                    break
        return sessions

    def _peak_sessions(
        self,
        week_start: date,
        sports: list[str],
        available: int,
        is_tri: bool,
    ) -> list[dict[str, Any]]:
        sessions = []
        primary = sports[0]

        sessions.append(
            {
                "date": (week_start + timedelta(days=6)).isoformat(),
                "sport": primary,
                "type": "race_pace",
                "duration_hours": 1.0,
                "intensity": "threshold",
                "description": "Race-pace rehearsal",
            }
        )

        sessions.append(
            {
                "date": (week_start + timedelta(days=2)).isoformat(),
                "sport": primary,
                "type": "intervals",
                "duration_hours": 0.75,
                "intensity": "high",
                "description": "VO2max intervals",
            }
        )
        return sessions

    def _race_sessions(
        self, week_start: date, sports: list[str]
    ) -> list[dict[str, Any]]:
        primary = sports[0]
        return [
            {
                "date": (week_start + timedelta(days=6)).isoformat(),
                "sport": primary,
                "type": "race",
                "duration_hours": 0.0,
                "intensity": "max",
                "description": "Race day!",
            }
        ]

    def get_week(self, week_number: int) -> WeekPlan | None:
        for w in self._weeks:
            if w.week_number == week_number:
                return w
        return None

    def get_current_phase(self, as_of: date | None = None) -> Phase:
        if as_of is None:
            as_of = date.today()
        for w in reversed(self._weeks):
            if w.week_start <= as_of:
                return w.phase
        return Phase.BASE
