from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class SleepData:
    score: int | None = None
    total_sleep_seconds: int | None = None
    deep_sleep_seconds: int | None = None
    rem_sleep_seconds: int | None = None
    light_sleep_seconds: int | None = None
    awake_sleep_seconds: int | None = None
    stages: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class HRVData:
    value_ms: float | None = None
    status: str | None = None
    baseline_ms: float | None = None
    deviation_pct: float | None = None
    weekly_average_ms: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class BodyBatteryEvent:
    event_type: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    body_battery_change: float | None = None


@dataclass
class BodyBatteryData:
    morning_value: int | None = None
    current_value: int | None = None
    charged: int | None = None
    drained: int | None = None
    events: list[BodyBatteryEvent] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class StressData:
    avg: float | None = None
    max: float | None = None
    rest_avg: float | None = None
    time_in_high: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RHRData:
    value_bpm: int | None = None
    baseline_bpm: float | None = None
    deviation_bpm: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SpO2Data:
    avg_pct: float | None = None
    min_pct: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class BodyCompositionData:
    weight_kg: float | None = None
    body_fat_pct: float | None = None
    muscle_mass_kg: float | None = None
    body_water_pct: float | None = None
    bone_mass_kg: float | None = None
    basal_metabolism_kcal: float | None = None
    bmi: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingReadinessData:
    score: int | None = None
    level: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunningDynamics:
    cadence_spm: float | None = None
    ground_contact_time_ms: float | None = None
    ground_contact_balance_pct: float | None = None
    step_length_m: float | None = None
    vertical_oscillation_cm: float | None = None
    vertical_ratio_pct: float | None = None


@dataclass
class ActivityLap:
    lap_index: int
    duration_seconds: float | None = None
    distance_meters: float | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    avg_power: float | None = None
    avg_pace_sec_per_km: float | None = None
    recovery_seconds: float | None = None


@dataclass
class TrainingLoad:
    ctl: float = 0.0
    atl: float = 0.0
    tsb: float = 0.0
    ramp_rate: float = 0.0
    monotony: float = 0.0
    strain: float = 0.0
    weekly_volume_km: float = 0.0
    weekly_tss: float = 0.0
    previous_week_volume_km: float = 0.0

    @property
    def weekly_volume_increase_pct(self) -> float:
        if self.previous_week_volume_km <= 0:
            return 0.0
        return (
            (self.weekly_volume_km - self.previous_week_volume_km) / self.previous_week_volume_km
        ) * 100.0


@dataclass
class ReadinessScore:
    score: int
    level: str
    components: dict[str, float] = field(default_factory=dict)
    component_weights: dict[str, float] = field(default_factory=dict)
    confidence: str = "high"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "components": self.components,
            "component_weights": self.component_weights,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass
class EnvironmentMetrics:
    temperature_c: float | None = None
    wbgt_c: float | None = None
    air_quality: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "temperature_c": self.temperature_c,
            "wbgt_c": self.wbgt_c,
            "air_quality": self.air_quality,
        }


@dataclass
class ActivitySummary:
    activity_id: str | None = None
    type: str | None = None
    sport_type: str | None = None
    start_time: str | None = None
    distance_km: float | None = None
    duration_min: float | None = None
    avg_pace: str | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    calories: int | None = None
    training_effect: str | None = None
    training_effect_aerobic: float | None = None
    training_effect_anaerobic: float | None = None
    hr_zones: dict[str, float] = field(default_factory=dict)
    avg_power: float | None = None
    max_power: float | None = None
    tss: float | None = None
    running_dynamics: RunningDynamics | None = None
    laps: list[ActivityLap] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "type": self.type,
            "sport_type": self.sport_type,
            "start_time": self.start_time,
            "distance_km": self.distance_km,
            "duration_min": self.duration_min,
            "avg_pace": self.avg_pace,
            "avg_hr": self.avg_hr,
            "max_hr": self.max_hr,
            "calories": self.calories,
            "training_effect": self.training_effect,
            "training_effect_aerobic": self.training_effect_aerobic,
            "training_effect_anaerobic": self.training_effect_anaerobic,
            "hr_zones": self.hr_zones,
            "avg_power": self.avg_power,
            "max_power": self.max_power,
            "tss": self.tss,
            "running_dynamics": self.running_dynamics.__dict__ if self.running_dynamics else None,
            "laps": [lap.__dict__ for lap in self.laps],
            "raw": self.raw,
        }


@dataclass
class HealthMetrics:
    metric_date: date
    sleep: SleepData | None = None
    hrv: HRVData | None = None
    body_battery: BodyBatteryData | None = None
    stress: StressData | None = None
    rhr: RHRData | None = None
    spo2: SpO2Data | None = None
    body_composition: BodyCompositionData | None = None
    training_readiness: TrainingReadinessData | None = None
    training_load: TrainingLoad = field(default_factory=TrainingLoad)
    readiness: ReadinessScore | None = None
    recent_activities: list[ActivitySummary] = field(default_factory=list)
    recent_sleep_scores: list[int] = field(default_factory=list)
    environment: EnvironmentMetrics | None = None

    @property
    def sleep_score(self) -> int | None:
        return self.sleep.score if self.sleep else None

    @property
    def body_battery_morning(self) -> int | None:
        return self.body_battery.morning_value if self.body_battery else None

    @property
    def hrv_deviation_pct(self) -> float | None:
        return self.hrv.deviation_pct if self.hrv else None

    @property
    def stress_avg(self) -> float | None:
        return self.stress.avg if self.stress else None

    @property
    def rhr_today(self) -> int | None:
        return self.rhr.value_bpm if self.rhr else None

    @property
    def rhr_baseline(self) -> float | None:
        return self.rhr.baseline_bpm if self.rhr else None

    @property
    def tsb(self) -> float:
        return self.training_load.tsb

    @property
    def ramp_rate(self) -> float:
        return self.training_load.ramp_rate

    @property
    def monotony(self) -> float:
        return self.training_load.monotony

    @property
    def recent_max_hr(self) -> int | None:
        values = [
            activity.max_hr for activity in self.recent_activities if activity.max_hr is not None
        ]
        return max(values) if values else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_date": self.metric_date.isoformat(),
            "sleep": self.sleep.raw if self.sleep else None,
            "hrv": self.hrv.raw if self.hrv else None,
            "body_battery": self.body_battery.raw if self.body_battery else None,
            "stress": self.stress.raw if self.stress else None,
            "rhr": self.rhr.raw if self.rhr else None,
            "spo2": self.spo2.raw if self.spo2 else None,
            "body_composition": self.body_composition.raw if self.body_composition else None,
            "training_readiness": self.training_readiness.raw if self.training_readiness else None,
            "training_load": self.training_load.__dict__,
            "readiness": self.readiness.to_dict() if self.readiness else None,
            "recent_activities": [activity.to_dict() for activity in self.recent_activities],
            "recent_sleep_scores": self.recent_sleep_scores,
            "environment": self.environment.to_dict() if self.environment else None,
        }
