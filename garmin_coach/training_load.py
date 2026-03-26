"""Training load metrics — CTL/ATL/TSB calculator, session TRIMP, multi-sport support.

Science references:
- CTL/ATL/TSB: TrainingPeaks WKO+ / Andrew Coggan
- TRIMP: Edwards HR-based training impulse model
- Periodization: periodization-training.com, Bompa & Buzzichelli
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


# ─── Enums ────────────────────────────────────────────────────────────────────


class Sport(str, Enum):
    RUNNING = "running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    TRIATHLON = "triathlon"
    OTHER = "other"


class SessionIntensity(str, Enum):
    RECOVERY = "recovery"
    EASY = "easy"
    AEROBIC = "aerobic"
    THRESHOLD = "threshold"
    INTERVAL = "interval"
    RACE = "race"


class FormCategory(str, Enum):
    FRESHNESS_RISK = "freshness_risk"  # TSB > +25 — detrained risk
    FRESH = "fresh"  # TSB +10 to +25 — race ready
    PREPARED = "prepared"  # TSB -10 to +10 — training ready
    TIRED = "tired"  # TSB -25 to -10 — accumulating fitness
    EXCESSIVE = "excessive"  # TSB < -25 — injury risk


class PeriodizationPhase(str, Enum):
    BASE = "base"  # High volume, low intensity, aerobic development
    BUILD = "build"  # Moderate volume, increasing intensity
    PEAK = "peak"  # Low volume, high intensity, race-specific
    RACE = "race"  # Minimal volume, maximum intensity


# ─── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class DailyLoad:
    date: date
    trimp: float
    sport: Sport
    duration_min: float
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "trimp": self.trimp,
            "sport": self.sport.value,
            "duration_min": self.duration_min,
            "description": self.description,
        }


@dataclass
class LoadSnapshot:
    ctl: float
    atl: float
    tsb: float
    form: FormCategory
    date: date

    def to_dict(self) -> dict[str, Any]:
        return {
            "ctl": round(self.ctl, 1),
            "atl": round(self.atl, 1),
            "tsb": round(self.tsb, 1),
            "form": self.form.value,
            "date": self.date.isoformat(),
        }


@dataclass
class WeeklyStats:
    week_start: date
    total_trimp: float
    total_hours: float
    session_count: int
    sport_breakdown: dict[str, float]
    ctl_change: float
    form_trend: list[FormCategory]

    def to_dict(self) -> dict[str, Any]:
        return {
            "week_start": self.week_start.isoformat(),
            "total_trimp": round(self.total_trimp, 1),
            "total_hours": round(self.total_hours, 1),
            "session_count": self.session_count,
            "sport_breakdown": {
                k: round(v, 1) for k, v in self.sport_breakdown.items()
            },
            "ctl_change": round(self.ctl_change, 1),
            "form_trend": [f.value for f in self.form_trend],
        }


@dataclass
class RecoveryRecommendation:
    deload_needed: bool
    reason: str
    suggested_trimp_reduction: float  # multiplier, e.g. 0.5 = 50% reduction
    next_intensity: str
    rest_days: int


# ─── Session Load Calculator ───────────────────────────────────────────────────


class SessionLoadCalculator:
    """Calculate TRIMP (Training Impulse) for a single session.

    TRIMP = duration_min × intensity_factor × metabolic_factor
    """

    # Running intensity factors by session type
    RUNNING_INTENSITY: dict[SessionIntensity, float] = {
        SessionIntensity.RECOVERY: 0.65,
        SessionIntensity.EASY: 0.70,
        SessionIntensity.AEROBIC: 0.80,
        SessionIntensity.THRESHOLD: 0.90,
        SessionIntensity.INTERVAL: 1.00,
        SessionIntensity.RACE: 1.10,
    }

    # Cycling intensity based on power % FTP
    CYCLING_INTENSITY: list[tuple[float, float]] = [
        (0.55, 0.60),  # <55%: recovery
        (0.75, 0.70),  # 55-75%: endurance
        (0.90, 0.85),  # 75-90%: tempo
        (1.05, 1.00),  # 90-105%: threshold
        (1.20, 1.20),  # 105-120%: VO2max
        (1.50, 1.50),  # >120%: anaerobic
    ]

    # Swimming intensity factors
    SWIMMING_INTENSITY: dict[SessionIntensity, float] = {
        SessionIntensity.RECOVERY: 0.55,
        SessionIntensity.EASY: 0.60,
        SessionIntensity.AEROBIC: 0.75,
        SessionIntensity.THRESHOLD: 0.90,
        SessionIntensity.INTERVAL: 1.00,
        SessionIntensity.RACE: 1.05,
    }

    def __init__(self, sex: str = "male") -> None:
        # Metabolic factor: female has higher HR response, hence higher TRIMP
        self._metabolic_factor = 1.3 if sex.lower() in ("female", "f") else 1.0

    @property
    def metabolic_factor(self) -> float:
        return self._metabolic_factor

    def estimate_running_intensity(
        self,
        distance_km: float | None,
        pace: str | None,
        threshold_pace: str | None,
    ) -> float:
        """Infer running intensity from pace relative to threshold pace.

        threshold_pace and pace are both e.g. "5:30/km"
        """
        if pace and threshold_pace and distance_km and distance_km >= 1:
            session_pace = _pace_to_sec_per_km(pace)
            threshold = _pace_to_sec_per_km(threshold_pace)
            if session_pace and threshold and threshold > 0:
                ratio = session_pace / threshold
                if ratio > 1.20:
                    return 0.65  # very easy
                elif ratio > 1.10:
                    return 0.70
                elif ratio > 1.00:
                    return 0.80
                elif ratio > 0.90:
                    return 0.90
                elif ratio > 0.80:
                    return 1.00
                else:
                    return 1.10  # faster than threshold = race intensity
        # Fallback: estimate from distance alone
        if distance_km:
            if distance_km <= 5:
                return 0.80
            elif distance_km <= 15:
                return 0.75
            elif distance_km <= 25:
                return 0.70
            else:
                return 0.65  # long run = lower intensity per minute
        return 0.75

    def estimate_cycling_intensity(
        self, avg_power: int | None, ftp: int | None
    ) -> float:
        """Infer cycling intensity from power vs FTP."""
        if avg_power and ftp and ftp > 0:
            ratio = avg_power / ftp
            for threshold, factor in self.CYCLING_INTENSITY:
                if ratio <= threshold:
                    return factor
            return 1.50  # >150% FTP
        return 0.80  # default moderate

    def calculate_trimp(
        self,
        sport: Sport,
        duration_min: float,
        avg_hr: int | None = None,
        max_hr: int | None = None,
        rest_hr: int | None = None,
        avg_power: int | None = None,
        ftp: int | None = None,
        distance_km: float | None = None,
        pace: str | None = None,
        threshold_pace: str | None = None,
        session_intensity: SessionIntensity | None = None,
    ) -> float:
        """Calculate TRIMP for a session.

        Uses HR-based TRIMP (Edwards method) where HR data is available,
        falls back to intensity-factor method.
        """
        # HR-based TRIMP (Edwards)
        if avg_hr and max_hr and rest_hr and max_hr > rest_hr:
            hr_range = max_hr - rest_hr
            if hr_range <= 0:
                intensity = 0.5
            else:
                # Zone fraction of HR reserve (Karvonen-adjacent)
                zone_fraction = (avg_hr - rest_hr) / hr_range
                intensity = zone_fraction * 1.0  # normalized to 1.0 at max HR
            trimp = duration_min * intensity * self._metabolic_factor
            return round(trimp, 1)

        # Intensity-factor based TRIMP
        if sport == Sport.RUNNING:
            if session_intensity:
                intensity = self.RUNNING_INTENSITY[session_intensity]
            else:
                intensity = self.estimate_running_intensity(
                    distance_km, pace, threshold_pace
                )
            return round(duration_min * intensity * self._metabolic_factor, 1)

        elif sport == Sport.CYCLING:
            if session_intensity:
                # Map cycling intensity roughly to factors
                intensity_map = {
                    SessionIntensity.RECOVERY: 0.60,
                    SessionIntensity.EASY: 0.70,
                    SessionIntensity.AEROBIC: 0.80,
                    SessionIntensity.THRESHOLD: 1.00,
                    SessionIntensity.INTERVAL: 1.20,
                    SessionIntensity.RACE: 1.50,
                }
                intensity = intensity_map.get(session_intensity, 0.80)
            else:
                intensity = self.estimate_cycling_intensity(avg_power, ftp)
            return round(duration_min * intensity * self._metabolic_factor, 1)

        elif sport == Sport.SWIMMING:
            if session_intensity:
                intensity = self.SWIMMING_INTENSITY[session_intensity]
            else:
                intensity = 0.75
            return round(duration_min * intensity * self._metabolic_factor, 1)

        elif sport == Sport.TRIATHLON:
            # Use the highest-intensity segment as proxy
            return round(duration_min * 0.85 * self._metabolic_factor, 1)

        else:
            return round(duration_min * 0.70 * self._metabolic_factor, 1)

    def trimp_to_load_category(self, trimp: float) -> str:
        """Categorize a single session's TRIMP."""
        if trimp < 50:
            return "very_light"
        elif trimp < 100:
            return "light"
        elif trimp < 200:
            return "moderate"
        elif trimp < 300:
            return "hard"
        else:
            return "very_hard"


# ─── Training Load Calculator ──────────────────────────────────────────────────


class TrainingLoadCalculator:
    """Track CTL (fitness), ATL (fatigue), and TSB (form) over time.

    Uses exponential moving average with fixed decay constants:
      CTL decay constant: 42 days (chronic, ~6 weeks)
      ATL decay constant: 7 days (acute, ~1 week)

    Formulas:
      CTL(t) = EMA(TRIMP, span=42)
      ATL(t) = EMA(TRIMP, span=7)
      TSB(t) = CTL(t) - ATL(t)
    """

    CTL_DECAY = 1 / 42  # ~0.0238
    ATL_DECAY = 1 / 7  # ~0.1429

    def __init__(self, sex: str = "male") -> None:
        self._session_calculator = SessionLoadCalculator(sex=sex)
        self._loads: dict[str, DailyLoad] = {}  # date_iso -> DailyLoad

    @property
    def session_calculator(self) -> SessionLoadCalculator:
        return self._session_calculator

    # ── Load tracking ─────────────────────────────────────────────────────────

    def add_session(
        self,
        session_date: date | str,
        trimp: float,
        sport: Sport | str,
        duration_min: float,
        description: str = "",
    ) -> DailyLoad:
        """Add a training session. Overwrites if same date+sport exists."""
        if isinstance(session_date, str):
            session_date = date.fromisoformat(session_date)
        if isinstance(sport, str):
            sport = Sport(sport)
        load = DailyLoad(
            date=session_date,
            trimp=trimp,
            sport=sport,
            duration_min=duration_min,
            description=description,
        )
        self._loads[session_date.isoformat()] = load
        return load

    def remove_session(self, session_date: date | str) -> bool:
        """Remove a session by date."""
        if isinstance(session_date, str):
            session_date = date.fromisoformat(session_date)
        key = session_date.isoformat()
        if key in self._loads:
            del self._loads[key]
            return True
        return False

    def get_session(self, session_date: date | str) -> DailyLoad | None:
        """Get session by date."""
        if isinstance(session_date, str):
            session_date = date.fromisoformat(session_date)
        return self._loads.get(session_date.isoformat())

    def get_sessions_in_range(
        self, start: date | str, end: date | str
    ) -> list[DailyLoad]:
        """Get all sessions within a date range."""
        if isinstance(start, str):
            start = date.fromisoformat(start)
        if isinstance(end, str):
            end = date.fromisoformat(end)
        return sorted(
            [l for l in self._loads.values() if start <= l.date <= end],
            key=lambda l: l.date,
        )

    # ── CTL / ATL / TSB ──────────────────────────────────────────────────────

    def _ema(self, target_date: date, span: float) -> float:
        """Exponential moving average of TRIMP values up to target_date.

        EMA = α × x_t + (1-α) × EMA_{t-1}
        where α = 2 / (span + 1)
        """
        alpha = 2 / (span + 1)
        result = 0.0
        count = 0
        # Walk backwards through time
        for days_ago in range(1000):  # up to ~3 years back
            check = target_date - timedelta(days=days_ago)
            key = check.isoformat()
            if key in self._loads:
                trimp = self._loads[key].trimp
                if count == 0:
                    result = trimp
                else:
                    result = alpha * trimp + (1 - alpha) * result
                count += 1
                if count > span * 3:  # converged after ~3 spans
                    break
        return result

    def calculate_ctl(self, as_of: date | str | None = None) -> float:
        """Chronic Training Load — fitness accumulation (42-day EMA)."""
        if as_of is None:
            as_of = date.today()
        if isinstance(as_of, str):
            as_of = date.fromisoformat(as_of)
        return round(self._ema(as_of, 42), 1)

    def calculate_atl(self, as_of: date | str | None = None) -> float:
        """Acute Training Load — short-term fatigue (7-day EMA)."""
        if as_of is None:
            as_of = date.today()
        if isinstance(as_of, str):
            as_of = date.fromisoformat(as_of)
        return round(self._ema(as_of, 7), 1)

    def calculate_tsb(self, as_of: date | str | None = None) -> float:
        """Training Stress Balance — form (CTL - ATL)."""
        if as_of is None:
            as_of = date.today()
        if isinstance(as_of, str):
            as_of = date.fromisoformat(as_of)
        ctl = self.calculate_ctl(as_of)
        atl = self.calculate_atl(as_of)
        return round(ctl - atl, 1)

    def get_snapshot(self, as_of: date | str | None = None) -> LoadSnapshot:
        """Get full load snapshot."""
        if as_of is None:
            as_of = date.today()
        if isinstance(as_of, str):
            as_of = date.fromisoformat(as_of)
        ctl = self.calculate_ctl(as_of)
        atl = self.calculate_atl(as_of)
        tsb = ctl - atl
        return LoadSnapshot(
            ctl=ctl,
            atl=atl,
            tsb=tsb,
            form=self._tsb_to_form(tsb),
            date=as_of,
        )

    # ── Form category ────────────────────────────────────────────────────────

    @staticmethod
    def _tsb_to_form(tsb: float) -> FormCategory:
        if tsb > 25:
            return FormCategory.FRESHNESS_RISK
        elif tsb > 10:
            return FormCategory.FRESH
        elif tsb >= -10:
            return FormCategory.PREPARED
        elif tsb >= -25:
            return FormCategory.TIRED
        else:
            return FormCategory.EXCESSIVE

    def get_form_category(self, as_of: date | str | None = None) -> FormCategory:
        return self._tsb_to_form(self.calculate_tsb(as_of))

    def get_form_description(self, as_of: date | str | None = None) -> str:
        """Human-readable form description."""
        form = self.get_form_category(as_of)
        tsb = self.calculate_tsb(as_of)
        descriptions: dict[FormCategory, str] = {
            FormCategory.FRESHNESS_RISK: (
                f"Detrained ({tsb:+.0f}): Too much rest. Fitness may decline. "
                "Consider adding volume."
            ),
            FormCategory.FRESH: (
                f"Fresh ({tsb:+.0f}): Well-rested, race-ready. "
                "Good for high-intensity sessions or race day."
            ),
            FormCategory.PREPARED: (
                f"Prepared ({tsb:+.0f}): Good training balance. "
                "Ready for quality sessions."
            ),
            FormCategory.TIRED: (
                f"Tired ({tsb:+.0f}): Accumulating fatigue. "
                "Stick to easy days, avoid high intensity."
            ),
            FormCategory.EXCESSIVE: (
                f"Overreaching ({tsb:+.0f}): High injury risk. "
                "Take a rest day or very easy session."
            ),
        }
        return descriptions[form]

    # ── Weekly stats ─────────────────────────────────────────────────────────

    def get_weekly_stats(self, week_start: date | str) -> WeeklyStats:
        """Calculate weekly stats for a Mon-Sun week."""
        if isinstance(week_start, str):
            week_start = date.fromisoformat(week_start)
        week_end = week_start + timedelta(days=6)
        sessions = self.get_sessions_in_range(week_start, week_end)

        total_trimp = sum(s.trimp for s in sessions)
        total_hours = sum(s.duration_min for s in sessions) / 60.0
        sport_breakdown: dict[str, float] = defaultdict(float)
        for s in sessions:
            sport_breakdown[s.sport.value] += s.trimp

        prev_week_start = week_start - timedelta(days=7)
        prev_ctl = self.calculate_ctl(prev_week_start)
        curr_ctl = self.calculate_ctl(week_end)
        ctl_change = curr_ctl - prev_ctl

        # Get form for each day in the week
        form_trend: list[FormCategory] = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            form_trend.append(self.get_form_category(d))

        return WeeklyStats(
            week_start=week_start,
            total_trimp=total_trimp,
            total_hours=total_hours,
            session_count=len(sessions),
            sport_breakdown=dict(sport_breakdown),
            ctl_change=ctl_change,
            form_trend=form_trend,
        )

    def get_load_trend(self, weeks: int = 4) -> list[dict[str, Any]]:
        """Get CTL trend over N weeks."""
        today = date.today()
        # Find most recent Monday
        days_since_monday = today.weekday()
        most_recent_monday = today - timedelta(days=days_since_monday)

        trend = []
        for i in range(weeks - 1, -1, -1):
            week_start = most_recent_monday - timedelta(weeks=i * 7)
            stats = self.get_weekly_stats(week_start)
            trend.append(stats.to_dict())
        return trend

    # ── Recovery recommendations ─────────────────────────────────────────────

    def get_recovery_recommendation(
        self, as_of: date | str | None = None
    ) -> RecoveryRecommendation:
        """Recommend recovery actions based on current load state."""
        snapshot = self.get_snapshot(as_of)
        form = snapshot.form
        tsb = snapshot.tsb
        atl = snapshot.atl
        ctl = snapshot.ctl

        # ATL-based overreaching detection
        overreaching = atl > ctl * 1.5

        if form == FormCategory.EXCESSIVE or overreaching:
            return RecoveryRecommendation(
                deload_needed=True,
                reason="Excessive fatigue or overreaching detected. Injury risk is elevated.",
                suggested_trimp_reduction=0.40,
                next_intensity="recovery",
                rest_days=2,
            )
        elif form == FormCategory.TIRED and atl > ctl:
            return RecoveryRecommendation(
                deload_needed=True,
                reason="Fatigue exceeding fitness. Recovery week needed.",
                suggested_trimp_reduction=0.50,
                next_intensity="easy",
                rest_days=1,
            )
        elif form == FormCategory.FRESHNESS_RISK:
            return RecoveryRecommendation(
                deload_needed=False,
                reason="Detraining risk. Volume is too low.",
                suggested_trimp_reduction=-0.2,  # increase
                next_intensity="build_volume",
                rest_days=0,
            )
        else:
            return RecoveryRecommendation(
                deload_needed=False,
                reason="Load is well-managed. Continue as planned.",
                suggested_trimp_reduction=0.0,
                next_intensity="as_planned",
                rest_days=0,
            )

    def should_deload(
        self, current_week: int, weeks_since_last_deload: int = 0
    ) -> tuple[bool, str]:
        """Determine if current week should be a recovery/deload week.

        Recovery weeks typically every 3-4 weeks.
        Triggers:
          - Every 3-4 weeks by schedule
          - ATL > CTL (overreaching)
          - TSB < -25 (excessive fatigue)
          - Consecutive high-intensity weeks
        """
        # Scheduled deload
        if weeks_since_last_deload >= 3:
            return True, "Scheduled recovery week (3+ weeks since last deload)"

        # ATL > CTL
        snapshot = self.get_snapshot()
        if snapshot.atl > snapshot.ctl:
            return True, f"ATL ({snapshot.atl:.0f}) exceeds CTL ({snapshot.ctl:.0f})"

        # TSB very negative
        if snapshot.tsb < -30:
            return True, f"TSB very negative ({snapshot.tsb:.0f}). Recovery required."

        # Progressive fatigue building up
        if current_week > 1 and snapshot.form in (
            FormCategory.EXCESSIVE,
            FormCategory.TIRED,
        ):
            return (
                True,
                f"Accumulated fatigue ({snapshot.form.value}). Deload recommended.",
            )

        return False, "No deload needed"

    # ── Persistence ──────────────────────────────────────────────────────────

    def export_json(self, path: str | Path | None = None) -> str:
        """Export load data to JSON. Returns JSON string."""
        data = {
            "meta": {
                "ctl_decay": self.CTL_DECAY,
                "atl_decay": self.ATL_DECAY,
                "exported_at": datetime.now().isoformat(),
            },
            "loads": [l.to_dict() for l in self._loads.values()],
        }
        json_str = json.dumps(data, indent=2)
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                f.write(json_str)
        return json_str

    @classmethod
    def from_json(
        cls, json_str: str | Path, sex: str = "male"
    ) -> TrainingLoadCalculator:
        """Load calculator from JSON file or string."""
        if isinstance(json_str, Path):
            with open(json_str) as f:
                json_str = f.read()
        data = json.loads(json_str)
        calc = cls(sex=sex)
        for entry in data.get("loads", []):
            d = date.fromisoformat(entry["date"])
            sport = Sport(entry.get("sport", "other"))
            calc.add_session(
                session_date=d,
                trimp=entry["trimp"],
                sport=sport,
                duration_min=entry["duration_min"],
                description=entry.get("description", ""),
            )
        return calc

    def export_time_series(self, days: int = 90) -> list[dict[str, Any]]:
        """Export daily CTL/ATL/TSB time series for the last N days."""
        today = date.today()
        series = []
        for i in range(days):
            d = today - timedelta(days=i)
            snapshot = self.get_snapshot(d)
            series.append(snapshot.to_dict())
        return list(reversed(series))


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _pace_to_sec_per_km(pace: str) -> float | None:
    """Parse 'M:SS/km' or 'M:SS' → seconds per km."""
    if not pace:
        return None
    pace = pace.strip().replace("/km", "").replace("/mi", "")
    parts = pace.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 1:
            return int(parts[0])
    except ValueError:
        return None
    return None
