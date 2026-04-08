from __future__ import annotations

from datetime import datetime
from typing import Any

from garmin_coach.models import (
    BodyBatteryData,
    BodyBatteryEvent,
    BodyCompositionData,
    HRVData,
    RHRData,
    SleepData,
    SpO2Data,
    StressData,
    TrainingReadinessData,
)


def parse_sleep_data(payload: dict[str, Any] | None) -> SleepData | None:
    if not isinstance(payload, dict) or not payload:
        return None
    return SleepData(
        score=payload.get("sleepScore") or payload.get("overallSleepScore"),
        total_sleep_seconds=payload.get("sleepTimeSeconds") or payload.get("totalSleepSeconds"),
        deep_sleep_seconds=payload.get("deepSleepSeconds"),
        rem_sleep_seconds=payload.get("remSleepSeconds"),
        light_sleep_seconds=payload.get("lightSleepSeconds"),
        awake_sleep_seconds=payload.get("awakeSleepSeconds"),
        stages={
            "deep": payload.get("deepSleepSeconds", 0),
            "rem": payload.get("remSleepSeconds", 0),
            "light": payload.get("lightSleepSeconds", 0),
            "awake": payload.get("awakeSleepSeconds", 0),
        },
        raw=payload,
    )


def parse_hrv_data(payload: dict[str, Any] | None) -> HRVData | None:
    if not isinstance(payload, dict) or not payload:
        return None
    baseline = payload.get("baselineValue") or payload.get("weeklyAvg")
    value = payload.get("lastNightAvg") or payload.get("hrvValue") or payload.get("value")
    deviation = None
    if baseline and value is not None:
        try:
            deviation = ((float(value) - float(baseline)) / float(baseline)) * 100
        except Exception:
            deviation = None
    return HRVData(
        value_ms=value,
        status=payload.get("status") or payload.get("hrvStatus"),
        baseline_ms=baseline,
        deviation_pct=deviation,
        weekly_average_ms=payload.get("weeklyAvg"),
        raw=payload,
    )


def parse_body_battery(payload: Any) -> BodyBatteryData | None:
    if payload is None:
        return None
    events: list[BodyBatteryEvent] = []
    morning = None
    current = None
    charged = 0
    drained = 0
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            value = item.get("bodyBattery") or item.get("value")
            current = value if value is not None else current
            morning = value if morning is None and value is not None else morning
            delta = item.get("bodyBatteryChange") or item.get("delta")
            if isinstance(delta, (int, float)):
                if delta > 0:
                    charged += int(delta)
                else:
                    drained += abs(int(delta))
            events.append(
                BodyBatteryEvent(
                    event_type=item.get("eventType", "sample"),
                    start_time=_parse_dt(item.get("startTimeGMT") or item.get("startTime")),
                    end_time=_parse_dt(item.get("endTimeGMT") or item.get("endTime")),
                    body_battery_change=delta,
                )
            )
    elif isinstance(payload, dict):
        morning = payload.get("morningValue")
        current = payload.get("currentValue") or morning
    return BodyBatteryData(
        morning_value=morning,
        current_value=current,
        charged=charged or None,
        drained=drained or None,
        events=events,
        raw={"payload": payload},
    )


def parse_stress_data(payload: dict[str, Any] | None) -> StressData | None:
    if not isinstance(payload, dict) or not payload:
        return None
    return StressData(
        avg=payload.get("avgStressLevel")
        or payload.get("averageStressLevel")
        or payload.get("stressAvg"),
        max=payload.get("maxStressLevel"),
        rest_avg=payload.get("restStressDuration") or payload.get("restAvg"),
        time_in_high=payload.get("highStressDuration") or payload.get("timeInHighStress"),
        raw=payload,
    )


def parse_rhr_data(payload: dict[str, Any] | None) -> RHRData | None:
    if not isinstance(payload, dict) or not payload:
        return None
    value = (
        payload.get("value")
        or payload.get("restingHeartRate")
        or payload.get("allMetrics", {}).get("metricsMap", {}).get("60")
    )
    baseline = payload.get("baseline") or payload.get("baselineValue")
    deviation = None
    if baseline is not None and value is not None:
        try:
            deviation = float(value) - float(baseline)
        except Exception:
            deviation = None
    return RHRData(value_bpm=value, baseline_bpm=baseline, deviation_bpm=deviation, raw=payload)


def parse_spo2_data(payload: dict[str, Any] | None) -> SpO2Data | None:
    if not isinstance(payload, dict) or not payload:
        return None
    return SpO2Data(
        avg_pct=payload.get("averageValue")
        or payload.get("avgPulseOx")
        or payload.get("averageSpO2"),
        min_pct=payload.get("lowestValue")
        or payload.get("minPulseOx")
        or payload.get("minimumValue"),
        raw=payload,
    )


def parse_body_composition(payload: dict[str, Any] | None) -> BodyCompositionData | None:
    if not isinstance(payload, dict) or not payload:
        return None
    return BodyCompositionData(
        weight_kg=payload.get("weight") or payload.get("weightKg"),
        body_fat_pct=payload.get("percentFat") or payload.get("bodyFatPercentage"),
        muscle_mass_kg=payload.get("muscleMass") or payload.get("skeletalMuscleMass"),
        body_water_pct=payload.get("bodyWater") or payload.get("bodyWaterPercentage"),
        bone_mass_kg=payload.get("boneMass"),
        basal_metabolism_kcal=payload.get("bmr") or payload.get("basalMet"),
        bmi=payload.get("bmi"),
        raw=payload,
    )


def parse_training_readiness(payload: dict[str, Any] | None) -> TrainingReadinessData | None:
    if not isinstance(payload, dict) or not payload:
        return None
    raw_score = payload.get("score") or payload.get("trainingReadinessScore")
    score = int(raw_score) if isinstance(raw_score, (int, float)) else None
    level = None
    if score is not None:
        if score >= 75:
            level = "green"
        elif score >= 50:
            level = "yellow"
        elif score >= 30:
            level = "red"
        else:
            level = "critical"
    return TrainingReadinessData(
        score=score,
        level=level,
        recovery_time_hours=payload.get("recoveryTime") or payload.get("recoveryHours"),
        acute_load=payload.get("acuteLoad") or payload.get("load"),
        load_balance=payload.get("loadBalance") or payload.get("loadFocus"),
        sleep_contribution=payload.get("sleepScoreContribution")
        or payload.get("sleepContribution"),
        hrv_contribution=payload.get("hrvContribution") or payload.get("hrvStatusContribution"),
        raw=payload,
    )


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
