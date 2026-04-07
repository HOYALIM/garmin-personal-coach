from __future__ import annotations

from typing import Any

from garmin_coach.models import ActivityLap, ActivitySummary, RunningDynamics


def _parse_training_effect_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped.count(".") > 1:
            return None
        normalized = stripped.replace(".", "", 1)
        if not normalized.isdigit():
            return None
        numeric = float(stripped)
    else:
        return None
    if numeric < 0.0 or numeric > 5.0:
        return None
    return numeric


def extract_training_effect(details: dict[str, Any]) -> tuple[float | None, float | None]:
    aerobic = _parse_training_effect_value(details.get("aerobicTrainingEffect"))
    anaerobic = _parse_training_effect_value(details.get("anaerobicTrainingEffect"))
    return aerobic, anaerobic


def extract_running_dynamics(details: dict[str, Any]) -> RunningDynamics | None:
    values = {
        "cadence_spm": details.get("averageRunCadence") or details.get("averageCadence"),
        "ground_contact_time_ms": details.get("avgGroundContactTime"),
        "ground_contact_balance_pct": details.get("avgGroundContactBalance"),
        "step_length_m": details.get("avgStrideLength"),
        "vertical_oscillation_cm": details.get("avgVerticalOscillation"),
        "vertical_ratio_pct": details.get("avgVerticalRatio"),
    }
    if not any(v is not None for v in values.values()):
        return None
    return RunningDynamics(**values)


def extract_laps(details: dict[str, Any]) -> list[ActivityLap]:
    laps: list[ActivityLap] = []
    for idx, lap in enumerate(details.get("laps", []) or [], start=1):
        if not isinstance(lap, dict):
            continue
        laps.append(
            ActivityLap(
                lap_index=idx,
                duration_seconds=lap.get("duration") or lap.get("elapsedDuration"),
                distance_meters=lap.get("distance"),
                avg_hr=lap.get("averageHR") or lap.get("averageHeartRate"),
                max_hr=lap.get("maxHR") or lap.get("maxHeartRate"),
                avg_power=lap.get("averagePower"),
                avg_pace_sec_per_km=lap.get("averagePaceSecondsPerKilometer"),
                recovery_seconds=lap.get("recoveryDuration"),
            )
        )
    return laps


def enrich_activity_summary(base: ActivitySummary, details: dict[str, Any]) -> ActivitySummary:
    aerobic, anaerobic = extract_training_effect(details)
    base.training_effect_aerobic = aerobic
    base.training_effect_anaerobic = anaerobic
    if aerobic is not None or anaerobic is not None:
        base.training_effect = f"aerobic={aerobic}, anaerobic={anaerobic}"
    base.running_dynamics = extract_running_dynamics(details)
    base.laps = extract_laps(details)
    return base
