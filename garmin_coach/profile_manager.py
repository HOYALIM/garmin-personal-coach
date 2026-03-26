"""User profile management — read/write/validate config.yaml, calculate training zones."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml


# ─── Exceptions ────────────────────────────────────────────────────────────────


class ProfileError(Exception):
    """Base exception for profile operations."""

    pass


class ProfileValidationError(ProfileError):
    """Raised when profile data fails validation."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"Validation failed:\n  " + "\n  ".join(errors))


# ─── Enums ────────────────────────────────────────────────────────────────────


class FitnessLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Sex(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Sport(str, Enum):
    RUNNING = "running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    TRIATHLON = "triathlon"


class AIFlexibility(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    FLEXIBLE = "flexible"


class AITone(str, Enum):
    ENCOURAGING = "encouraging"
    DIRECT = "direct"
    ANALYTICAL = "analytical"
    MOTIVATIONAL = "motivational"


class NotificationMethod(str, Enum):
    PRINT = "print"
    NOTIFY_SEND = "notify-send"
    TELEGRAM = "telegram"
    DISCORD = "discord"


class GarMiniAuthMethod(str, Enum):
    GARTH = "garth"
    MANUAL = "manual"


# ─── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class ProfileData:
    name: str = ""
    age: int = 30
    sex: Sex = Sex.OTHER
    height_cm: float = 170.0
    weight_kg: float = 70.0
    sports: list[Sport] = field(default_factory=lambda: [Sport.RUNNING])
    goal_event: str = ""
    goal_date: str = ""  # ISO "YYYY-MM-DD"
    fitness_level: FitnessLevel = FitnessLevel.INTERMEDIATE
    available_days: int = 5  # per week
    max_weekly_hours: float = 10.0
    primary_sport: Sport = Sport.RUNNING

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sex"] = self.sex.value
        d["sports"] = [s.value for s in self.sports]
        d["primary_sport"] = self.primary_sport.value
        d["fitness_level"] = self.fitness_level.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProfileData:
        d = dict(d)
        d["sex"] = Sex(d.get("sex", "other"))
        d["sports"] = [Sport(s) for s in d.get("sports", ["running"])]
        d["primary_sport"] = Sport(d.get("primary_sport", "running"))
        d["fitness_level"] = FitnessLevel(d.get("fitness_level", "intermediate"))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class FitnessData:
    # Running race times: "HH:MM" or "MM:SS" or "auto" or None
    recent_5k: str | None = None
    recent_10k: str | None = None
    recent_half: str | None = None
    recent_marathon: str | None = None
    # Cycling
    cycling_ftp_w: int | None = None  # Watts
    # Swimming
    swim_100m_pace: str | None = None  # "MM:SS" per 100m
    # Heart rate
    resting_hr: int | None = None  # bpm
    max_hr: int | None = None  # bpm (if known)
    # Auto-fetch flags
    fetch_race_times: bool = True
    fetch_hr_baseline: bool = True
    fetch_cycling_data: bool = False
    fetch_swimming_data: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FitnessData:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class GarminConfig:
    email: str | None = None
    connected: bool = False
    auth_method: GarMiniAuthMethod = GarMiniAuthMethod.GARTH

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["auth_method"] = self.auth_method.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GarminConfig:
        d = dict(d)
        d["auth_method"] = GarMiniAuthMethod(d.get("auth_method", "garth"))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ScheduleConfig:
    morning_checkin: dict[str, Any] = field(
        default_factory=lambda: {"enabled": True, "time": "06:00"}
    )
    final_check: dict[str, Any] = field(
        default_factory=lambda: {"enabled": True, "time": "06:30"}
    )
    evening_checkin: dict[str, Any] = field(
        default_factory=lambda: {"enabled": True, "time": "22:00"}
    )
    weekly_review: dict[str, Any] = field(
        default_factory=lambda: {"enabled": True, "day": "sunday", "time": "21:00"}
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScheduleConfig:
        return cls(
            morning_checkin=d.get(
                "morning_checkin", {"enabled": True, "time": "06:00"}
            ),
            final_check=d.get("final_check", {"enabled": True, "time": "06:30"}),
            evening_checkin=d.get(
                "evening_checkin", {"enabled": True, "time": "22:00"}
            ),
            weekly_review=d.get(
                "weekly_review", {"enabled": True, "day": "sunday", "time": "21:00"}
            ),
        )


@dataclass
class AICoachConfig:
    enabled: bool = True
    flexibility: AIFlexibility = AIFlexibility.MODERATE
    tone: AITone = AITone.ENCOURAGING
    can_modify_plan: bool = True
    notification_method: NotificationMethod = NotificationMethod.PRINT
    notification_target: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["flexibility"] = self.flexibility.value
        d["tone"] = self.tone.value
        d["notification_method"] = self.notification_method.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AICoachConfig:
        d = dict(d)
        d["flexibility"] = AIFlexibility(d.get("flexibility", "moderate"))
        d["tone"] = AITone(d.get("tone", "encouraging"))
        d["notification_method"] = NotificationMethod(
            d.get("notification_method", "print")
        )
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class UserProfile:
    """Full user profile container."""

    profile: ProfileData = field(default_factory=ProfileData)
    fitness: FitnessData = field(default_factory=FitnessData)
    garmin: GarminConfig = field(default_factory=GarminConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    ai_coach: AICoachConfig = field(default_factory=AICoachConfig)
    version: str = "1.0"
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "profile": self.profile.to_dict(),
            "fitness": self.fitness.to_dict(),
            "garmin": self.garmin.to_dict(),
            "schedule": self.schedule.to_dict(),
            "ai_coach": self.ai_coach.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UserProfile:
        now = datetime.now().isoformat()
        return cls(
            version=d.get("version", "1.0"),
            created_at=d.get("created_at", now),
            updated_at=d.get("updated_at", now),
            profile=ProfileData.from_dict(d.get("profile", {})),
            fitness=FitnessData.from_dict(d.get("fitness", {})),
            garmin=GarminConfig.from_dict(d.get("garmin", {})),
            schedule=ScheduleConfig.from_dict(d.get("schedule", {})),
            ai_coach=AICoachConfig.from_dict(d.get("ai_coach", {})),
        )


# ─── Zone Structures ───────────────────────────────────────────────────────────


@dataclass
class HRZones:
    z1_min: int  # bpm
    z1_max: int
    z2_min: int
    z2_max: int
    z3_min: int
    z3_max: int
    z4_min: int
    z4_max: int
    z5_min: int
    z5_max: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def for_sport(self, sport: Sport) -> dict[str, Any]:
        return self.to_dict()


@dataclass
class PaceZones:
    z1: str | None = None  # e.g. "7:00/km"
    z2: str | None = None
    z3: str | None = None
    z4: str | None = None
    z5: str | None = None
    threshold_pace: str | None = None  # LT pace
    race_pace: str | None = None  # marathon pace

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PowerZones:
    z1_max: int = 0  # watts
    z2_min: int = 0
    z2_max: int = 0
    z3_min: int = 0
    z3_max: int = 0
    z4_min: int = 0
    z4_max: int = 0
    z5_min: int = 0
    z5_max: int = 0
    z6_min: int = 0
    z6_max: int = 0
    z7_min: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SwimZones:
    easy_max: str | None = None  # pace per 100m
    threshold_min: str | None = None
    threshold_max: str | None = None
    vo2max_max: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrainingZones:
    hr: HRZones | None = None
    running_pace: PaceZones | None = None
    cycling_power: PowerZones | None = None
    swimming: SwimZones | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "hr": self.hr.to_dict() if self.hr else None,
            "running_pace": self.running_pace.to_dict() if self.running_pace else None,
            "cycling_power": self.cycling_power.to_dict()
            if self.cycling_power
            else None,
            "swimming": self.swimming.to_dict() if self.swimming else None,
        }


# ─── Profile Manager ─────────────────────────────────────────────────────────


class ProfileManager:
    """Read/write/validate user profile from config.yaml."""

    DEFAULT_CONFIG_PATH = Path("~/.config/garmin_coach/config.yaml").expanduser()

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path = (
            Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        )

    # ── Load / Save ──────────────────────────────────────────────────────────

    def load(self) -> UserProfile | None:
        """Load profile from config file. Returns None if not found."""
        if not self.config_path.exists():
            return None
        with open(self.config_path) as f:
            raw = yaml.safe_load(f)
        if not raw:
            return None
        return UserProfile.from_dict(raw)

    def save(self, user_profile: UserProfile) -> None:
        """Save profile to config file. Creates parent directories."""
        user_profile.updated_at = datetime.now().isoformat()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump(
                user_profile.to_dict(),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def exists(self) -> bool:
        """Check if profile exists."""
        return self.config_path.exists()

    # ── Validation ───────────────────────────────────────────────────────────

    def validate(self, user_profile: UserProfile) -> list[str]:
        """Return list of validation errors. Empty = valid."""
        errors: list[str] = []

        p = user_profile.profile
        f = user_profile.fitness

        if not p.name.strip():
            errors.append("profile.name is required")
        if not (1 <= p.age <= 100):
            errors.append(f"profile.age must be 1-100, got {p.age}")
        if p.height_cm < 100 or p.height_cm > 250:
            errors.append(f"profile.height_cm must be 100-250 cm, got {p.height_cm}")
        if p.weight_kg < 30 or p.weight_kg > 200:
            errors.append(f"profile.weight_kg must be 30-200 kg, got {p.weight_kg}")
        if not p.sports:
            errors.append("profile.sports must have at least one sport")
        if p.available_days < 1 or p.available_days > 7:
            errors.append(f"profile.available_days must be 1-7, got {p.available_days}")
        if p.max_weekly_hours < 1 or p.max_weekly_hours > 40:
            errors.append(
                f"profile.max_weekly_hours must be 1-40, got {p.max_weekly_hours}"
            )
        if p.goal_date:
            try:
                date.fromisoformat(p.goal_date)
            except ValueError:
                errors.append(
                    f"profile.goal_date must be ISO format, got {p.goal_date!r}"
                )

        # Validate race times format
        for field_name, value in [
            ("5K", f.recent_5k),
            ("10K", f.recent_10k),
            ("Half", f.recent_half),
            ("Marathon", f.recent_marathon),
        ]:
            if value and value != "auto" and not _parse_duration(value):
                errors.append(
                    f"fitness.recent_{field_name.lower()} must be "
                    f"'auto', 'unknown', or HH:MM/SS format, got {value!r}"
                )

        if f.cycling_ftp_w is not None and (
            f.cycling_ftp_w < 50 or f.cycling_ftp_w > 500
        ):
            errors.append(
                f"fitness.cycling_ftp_w must be 50-500W, got {f.cycling_ftp_w}"
            )
        if f.resting_hr is not None and (f.resting_hr < 30 or f.resting_hr > 120):
            errors.append(f"fitness.resting_hr must be 30-120 bpm, got {f.resting_hr}")
        if f.max_hr is not None and (f.max_hr < 120 or f.max_hr > 220):
            errors.append(f"fitness.max_hr must be 120-220 bpm, got {f.max_hr}")

        # Validate schedule times
        for job in ["morning_checkin", "final_check", "evening_checkin"]:
            entry = getattr(user_profile.schedule, job)
            if entry.get("enabled") and not _validate_time(entry.get("time", "")):
                errors.append(
                    f"schedule.{job}.time must be HH:MM, got {entry.get('time')!r}"
                )

        wr = user_profile.schedule.weekly_review
        if wr.get("enabled") and not _validate_time(wr.get("time", "")):
            errors.append(f"schedule.weekly_review.time must be HH:MM")
        if wr.get("enabled") and wr.get("day", "") not in [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]:
            errors.append(
                f"schedule.weekly_review.day must be day name, got {wr.get('day')!r}"
            )

        return errors

    def validate_or_raise(self, user_profile: UserProfile) -> None:
        errors = self.validate(user_profile)
        if errors:
            raise ProfileValidationError(errors)

    # ── Zone Calculations ────────────────────────────────────────────────────

    def calculate_hr_zones(self, user_profile: UserProfile) -> HRZones:
        """Calculate 5 HR zones based on max HR.

        Default max HR = 220 - age if not known.
        Zone % of max HR:
          Z1: 50-60%   Recovery
          Z2: 60-70%   Aerobic / Fat burn
          Z3: 70-80%   Tempo
          Z4: 80-90%   Threshold / Lactate threshold
          Z5: 90-100%  VO2max / Anaerobic
        """
        max_hr = user_profile.fitness.max_hr
        if max_hr is None:
            max_hr = 220 - user_profile.profile.age
        return HRZones(
            z1_min=_pct(max_hr, 50),
            z1_max=_pct(max_hr, 60),
            z2_min=_pct(max_hr, 60),
            z2_max=_pct(max_hr, 70),
            z3_min=_pct(max_hr, 70),
            z3_max=_pct(max_hr, 80),
            z4_min=_pct(max_hr, 80),
            z4_max=_pct(max_hr, 90),
            z5_min=_pct(max_hr, 90),
            z5_max=max_hr,
        )

    def calculate_running_pace_zones(
        self, user_profile: UserProfile
    ) -> PaceZones | None:
        """Calculate running pace zones from known race times.

        Uses Jack Daniels VDOT approximation.
        Returns None if no race data available.
        """
        # Find best known race time
        known_races: list[tuple[str, str]] = [
            ("5k", user_profile.fitness.recent_5k or ""),
            ("10k", user_profile.fitness.recent_10k or ""),
            ("half", user_profile.fitness.recent_half or ""),
            ("marathon", user_profile.fitness.recent_marathon or ""),
        ]
        best_pace_per_km: float | None = None

        for race, time_str in known_races:
            if time_str and time_str not in ("auto", "unknown", ""):
                seconds = _parse_duration(time_str)
                if seconds:
                    km = {"5k": 5.0, "10k": 10.0, "half": 21.0975, "marathon": 42.195}[
                        race
                    ]
                    pace = seconds / km
                    if best_pace_per_km is None or pace < best_pace_per_km:
                        best_pace_per_km = pace

        if best_pace_per_km is None:
            return None

        # LT pace ≈ 10K pace
        lt_pace = best_pace_per_km
        # Race pace (marathon) ≈ 1.15x LT pace
        race_pace = lt_pace * 1.15

        def pace_str(sec_per_km: float) -> str:
            mins = int(sec_per_km // 60)
            secs = int(sec_per_km % 60)
            return f"{mins}:{secs:02d}/km"

        # Zone 1: > 130% LT (very easy)
        # Zone 2: 100-115% LT (easy/aerobic)
        # Zone 3: 85-100% LT (tempo)
        # Zone 4: 75-85% LT (threshold)
        # Zone 5: < 75% LT (VO2max)
        return PaceZones(
            z1=pace_str(lt_pace * 1.30),
            z2=pace_str(lt_pace * 1.15),
            z3=pace_str(lt_pace * 1.00),
            z4=pace_str(lt_pace * 0.88),
            z5=pace_str(lt_pace * 0.78),
            threshold_pace=pace_str(lt_pace),
            race_pace=pace_str(race_pace),
        )

    def calculate_cycling_power_zones(
        self, user_profile: UserProfile
    ) -> PowerZones | None:
        """Calculate cycling power zones from FTP.

        Returns None if FTP not known.
        Zones (cycling-specific, Coggan-style):
          Z1: <55% FTP   Active recovery
          Z2: 55-75%     Endurance
          Z3: 75-90%     Tempo
          Z4: 90-105%    Threshold (LTHR)
          Z5: 105-120%   VO2max
          Z6: 120-150%   Anaerobic
          Z7: >150%      Neuromuscular
        """
        ftp = user_profile.fitness.cycling_ftp_w
        if ftp is None:
            return None

        return PowerZones(
            z1_max=_pct_int(ftp, 55),
            z2_min=_pct_int(ftp, 55),
            z2_max=_pct_int(ftp, 75),
            z3_min=_pct_int(ftp, 75),
            z3_max=_pct_int(ftp, 90),
            z4_min=_pct_int(ftp, 90),
            z4_max=_pct_int(ftp, 105),
            z5_min=_pct_int(ftp, 105),
            z5_max=_pct_int(ftp, 120),
            z6_min=_pct_int(ftp, 120),
            z6_max=_pct_int(ftp, 150),
            z7_min=_pct_int(ftp, 150),
        )

    def calculate_swim_zones(self, user_profile: UserProfile) -> SwimZones | None:
        """Calculate swimming pace zones from 100m threshold pace.

        Returns None if no swim data.
        Zones:
          Z1: > 120% threshold (easy)
          Z2: 95-105% threshold (threshold)
          Z3: < 95% threshold (VO2max)
        """
        pace_str_val = user_profile.fitness.swim_100m_pace
        if not pace_str_val or pace_str_val in ("auto", "unknown", ""):
            return None
        secs = _parse_duration(pace_str_val)
        if secs is None:
            return None

        def fmt(s: float) -> str:
            mins = int(s // 60)
            sec = int(s % 60)
            return f"{mins}:{sec:02d}/100m"

        threshold_min = secs * 0.95
        threshold_max = secs * 1.05
        return SwimZones(
            easy_max=fmt(secs * 1.20),
            threshold_min=fmt(threshold_min),
            threshold_max=fmt(threshold_max),
            vo2max_max=fmt(secs * 0.90),
        )

    def calculate_all_zones(self, user_profile: UserProfile) -> TrainingZones:
        """Calculate all training zones for a user."""
        return TrainingZones(
            hr=self.calculate_hr_zones(user_profile),
            running_pace=self.calculate_running_pace_zones(user_profile),
            cycling_power=self.calculate_cycling_power_zones(user_profile),
            swimming=self.calculate_swim_zones(user_profile),
        )

    # ── Weekly load targets ───────────────────────────────────────────────────

    def weekly_trimp_target(self, user_profile: UserProfile) -> tuple[float, float]:
        """Return (min_trimp, max_trimp) per week by fitness level.

        Based on TrainingPeaks / TRIMP modeling.
        """
        targets: dict[FitnessLevel, tuple[float, float]] = {
            FitnessLevel.BEGINNER: (200.0, 350.0),
            FitnessLevel.INTERMEDIATE: (350.0, 600.0),
            FitnessLevel.ADVANCED: (600.0, 900.0),
        }
        return targets.get(user_profile.profile.fitness_level, (350.0, 600.0))

    def weekly_hours_target(self, user_profile: UserProfile) -> tuple[float, float]:
        """Return (min_hours, max_hours) per week."""
        targets: dict[FitnessLevel, tuple[float, float]] = {
            FitnessLevel.BEGINNER: (4.0, 6.0),
            FitnessLevel.INTERMEDIATE: (6.0, 10.0),
            FitnessLevel.ADVANCED: (10.0, 15.0),
        }
        return targets.get(user_profile.profile.fitness_level, (6.0, 10.0))


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _pct(value: float, pct: float) -> float:
    return round(value * pct / 100, 1)


def _pct_int(value: float, pct: float) -> int:
    return int(round(value * pct / 100))


def _parse_duration(time_str: str) -> float | None:
    """Parse 'HH:MM', 'MM:SS', 'H:MM:SS' → total seconds. Returns None on failure."""
    if not time_str or time_str in ("auto", "unknown", ""):
        return None
    time_str = time_str.strip()
    parts = time_str.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 1:
            return int(parts[0])
    except ValueError:
        return None
    return None


def _validate_time(time_str: str) -> bool:
    """Validate HH:MM format."""
    if not time_str:
        return False
    try:
        h, m = time_str.split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except (ValueError, TypeError):
        return False
