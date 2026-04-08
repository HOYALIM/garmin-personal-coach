from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any


@dataclass
class GarminAuth:
    email: str
    connected: bool = False
    connected_at: datetime | None = None
    mfa_enabled: bool = False
    auth_provider: str = "garmin_connect"

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "email": _mask_email(self.email),
            "connected": self.connected,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "mfa_enabled": self.mfa_enabled,
            "auth_provider": self.auth_provider,
        }


@dataclass
class StravaAuth:
    athlete_id: str | None = None
    connected: bool = False
    expires_at: datetime | None = None
    connected_at: datetime | None = None
    scopes: list[str] = field(default_factory=list)

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "athlete_id": self.athlete_id,
            "connected": self.connected,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "scopes": self.scopes,
        }


@dataclass
class RaceResult:
    event_name: str | None = None
    finish_time: timedelta | None = None
    event_date: date | None = None


@dataclass
class TrainingGoal:
    type: str
    target_event: str | None = None
    target_time: timedelta | None = None
    target_date: date | None = None
    weekly_volume_km: float = 0.0
    recent_race: RaceResult | None = None


@dataclass
class FitnessLevel:
    level: str
    weekly_avg_distance_km: float | None = None
    weekly_avg_sessions: float | None = None
    avg_zone_distribution: dict[str, float] = field(default_factory=dict)
    estimated_vo2max: float | None = None
    confirmed_by_user: bool = False


@dataclass
class Medication:
    name: str
    dosage: str | None = None
    affects_heart_rate: bool = False


@dataclass
class InjuryRecord:
    body_part: str
    description: str
    date_occurred: date | None = None
    date_cleared: date | None = None
    restrictions: list[str] = field(default_factory=list)
    medical_clearance: str = "pending"
    pain_reports_count: int = 0
    restricted_session_types: list[str] = field(default_factory=list)


@dataclass
class MedicalProfile:
    cardiac_conditions: list[str] = field(default_factory=list)
    hypertension: str = "none"
    diabetes: str = "none"
    respiratory: list[str] = field(default_factory=list)
    injury_history: list[InjuryRecord] = field(default_factory=list)
    current_injuries: list[InjuryRecord] = field(default_factory=list)
    medications: list[Medication] = field(default_factory=list)
    beta_blocker: bool = False
    notes: str = ""


@dataclass
class NutritionProfile:
    dietary_restrictions: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)
    meal_pattern: str = ""
    supplements: list[str] = field(default_factory=list)
    alcohol_frequency: str = ""
    daily_calorie_target: int | None = None


@dataclass
class SleepProfile:
    bedtime: str | None = None
    wake_time: str | None = None
    issues: list[str] = field(default_factory=list)


@dataclass
class CoachingPreferences:
    tone: str = "encouraging"
    preferred_training_time: str | None = None
    cross_training_preferences: list[str] = field(default_factory=list)
    notification_frequency: str = "default"
    units: str = "metric"
    timezone: str = "Asia/Seoul"


@dataclass
class UserProfile:
    garmin_credentials: GarminAuth
    birth_date: date
    sex: str
    height_cm: float
    weight_kg: float
    goal: TrainingGoal
    fitness_level: FitnessLevel
    medical: MedicalProfile | None = None
    nutrition: NutritionProfile | None = None
    sleep: SleepProfile | None = None
    preferences: CoachingPreferences | None = None
    strava_auth: StravaAuth | None = None

    @property
    def age(self) -> int:
        today = date.today()
        years = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years

    def to_safe_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["garmin_credentials"] = self.garmin_credentials.to_safe_dict()
        if self.medical:
            payload["medical"] = {
                "beta_blocker": self.medical.beta_blocker,
                "cardiac_condition_count": len(self.medical.cardiac_conditions),
                "current_injury_count": len(self.medical.current_injuries),
                "has_notes": bool(self.medical.notes.strip()),
            }
        if self.nutrition:
            payload["nutrition"] = {
                "dietary_restriction_count": len(self.nutrition.dietary_restrictions),
                "allergy_count": len(self.nutrition.allergies),
                "supplement_count": len(self.nutrition.supplements),
                "has_meal_pattern": bool(self.nutrition.meal_pattern.strip()),
            }
        if self.sleep:
            payload["sleep"] = {
                "has_bedtime": bool(self.sleep.bedtime),
                "has_wake_time": bool(self.sleep.wake_time),
                "issue_count": len(self.sleep.issues),
            }
        if self.strava_auth:
            payload["strava_auth"] = self.strava_auth.to_safe_dict()
        return payload


def _mask_email(value: str) -> str:
    if "@" not in value:
        return "***REDACTED***" if value else ""
    local, domain = value.split("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[:1]}***@{domain}"
