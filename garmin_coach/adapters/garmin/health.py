"""Parsers mapping raw Garmin Connect payloads onto our health models.

Ground truth for every shape here is `tests/fixtures/garmin/*.json`, captured
from a real account (ids zeroed, long timeseries truncated). Do not change a
key path in this module without a fixture that proves it.

Why that rule exists: the first version of these parsers was written against
*imagined* payload shapes, and the tests were written against the same
imagination. 294 tests stayed green while every single health metric parsed
to None in production — the parser and its test agreed with each other and
with nothing else. Real fixtures are the only thing that can break that tie.

Two shapes exist per endpoint and both matter:
- populated (`*_populated.json`) — a day the watch synced
- empty (`*.json`) — a day it did not: the envelope is present, every leaf is
  null. Parsers return None for that case rather than a hollow object, so
  "no data yet" is distinguishable from "data collected" upstream.
"""

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

RHR_METRIC_KEY = "WELLNESS_RESTING_HEART_RATE"


def _first(*values: Any) -> Any:
    """First value that is not None.

    Deliberately not `a or b`: a legitimate 0 (stress level, sleep seconds)
    is falsy and would silently fall through to the next candidate.
    """
    for value in values:
        if value is not None:
            return value
    return None


def _dig(payload: Any, *keys: str) -> Any:
    """Walk nested dicts, returning None if any hop is missing/not a dict."""
    node = payload
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def parse_sleep_data(payload: dict[str, Any] | None) -> SleepData | None:
    if not isinstance(payload, dict) or not payload:
        return None
    # Real shape nests everything under dailySleepDTO; flat keys are the
    # legacy/cached shape and stay as fallbacks.
    dto = payload.get("dailySleepDTO")
    dto = dto if isinstance(dto, dict) else {}

    score = _first(
        _dig(dto, "sleepScores", "overall", "value"),
        _dig(payload, "sleepScores", "overall", "value"),
        payload.get("sleepScore"),
        payload.get("overallSleepScore"),
    )
    total = _first(
        dto.get("sleepTimeSeconds"),
        payload.get("sleepTimeSeconds"),
        payload.get("totalSleepSeconds"),
    )
    deep = _first(dto.get("deepSleepSeconds"), payload.get("deepSleepSeconds"))
    rem = _first(dto.get("remSleepSeconds"), payload.get("remSleepSeconds"))
    light = _first(dto.get("lightSleepSeconds"), payload.get("lightSleepSeconds"))
    awake = _first(dto.get("awakeSleepSeconds"), payload.get("awakeSleepSeconds"))

    if score is None and total is None:
        return None  # envelope present but the watch recorded no sleep

    stages = {
        key: value
        for key, value in (("deep", deep), ("rem", rem), ("light", light), ("awake", awake))
        if value is not None
    }
    return SleepData(
        score=score,
        total_sleep_seconds=total,
        deep_sleep_seconds=deep,
        rem_sleep_seconds=rem,
        light_sleep_seconds=light,
        awake_sleep_seconds=awake,
        stages=stages,
        raw=payload,
    )


def parse_hrv_data(payload: dict[str, Any] | None) -> HRVData | None:
    # Accounts/devices without HRV status return {} — treated as "no data".
    # The populated shape below is unverified against a real fixture (the
    # capture account has HRV disabled); keys come from garminconnect usage
    # and should be re-confirmed with a fixture when such an account exists.
    if not isinstance(payload, dict) or not payload:
        return None
    summary = payload.get("hrvSummary")
    summary = summary if isinstance(summary, dict) else {}

    value = _first(
        summary.get("lastNightAvg"),
        payload.get("lastNightAvg"),
        payload.get("hrvValue"),
        payload.get("value"),
    )
    baseline = _first(
        _dig(summary, "baseline", "balancedLow"),
        summary.get("baselineValue"),
        payload.get("baselineValue"),
        payload.get("weeklyAvg"),
    )
    if value is None and baseline is None:
        return None

    deviation = None
    if baseline not in (None, 0) and value is not None:
        try:
            deviation = ((float(value) - float(baseline)) / float(baseline)) * 100
        except (TypeError, ValueError, ZeroDivisionError):
            deviation = None
    return HRVData(
        value_ms=value,
        status=_first(summary.get("status"), payload.get("status"), payload.get("hrvStatus")),
        baseline_ms=baseline,
        deviation_pct=deviation,
        weekly_average_ms=_first(summary.get("weeklyAvg"), payload.get("weeklyAvg")),
        raw=payload,
    )


def parse_body_battery(payload: Any) -> BodyBatteryData | None:
    """Real shape: [{charged, drained, bodyBatteryValuesArray: [[ts, level], ...]}].

    ``raw`` stays wrapped as {"payload": ...} because the snapshot cache
    round-trip unwraps that key.
    """
    if payload is None:
        return None

    events: list[BodyBatteryEvent] = []
    morning = current = charged = drained = None

    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            charged = _first(charged, item.get("charged"))
            drained = _first(drained, item.get("drained"))

            for sample in item.get("bodyBatteryValuesArray") or []:
                # [epoch_millis, level]; level is null before the watch syncs
                if not isinstance(sample, (list, tuple)) or len(sample) < 2:
                    continue
                level = sample[1]
                if level is None:
                    continue
                if morning is None:
                    morning = level
                current = level

            # Legacy/flat sample shape kept as a fallback
            legacy = _first(item.get("bodyBattery"), item.get("value"))
            if legacy is not None:
                morning = _first(morning, legacy)
                current = legacy

            delta = _first(item.get("bodyBatteryChange"), item.get("delta"))
            if delta is not None:
                events.append(
                    BodyBatteryEvent(
                        event_type=item.get("eventType", "sample"),
                        start_time=_parse_dt(_first(item.get("startTimeGMT"), item.get("startTime"))),
                        end_time=_parse_dt(_first(item.get("endTimeGMT"), item.get("endTime"))),
                        body_battery_change=delta,
                    )
                )
    elif isinstance(payload, dict):
        morning = payload.get("morningValue")
        current = _first(payload.get("currentValue"), morning)
        charged = payload.get("charged")
        drained = payload.get("drained")

    if morning is None and current is None and charged is None and drained is None:
        return None

    return BodyBatteryData(
        morning_value=morning,
        current_value=current,
        charged=charged,
        drained=drained,
        events=events,
        raw={"payload": payload},
    )


def parse_stress_data(payload: dict[str, Any] | None) -> StressData | None:
    if not isinstance(payload, dict) or not payload:
        return None
    avg = _first(
        payload.get("avgStressLevel"),
        payload.get("averageStressLevel"),
        payload.get("stressAvg"),
    )
    max_level = payload.get("maxStressLevel")
    if avg is None and max_level is None:
        return None
    return StressData(
        avg=avg,
        max=max_level,
        rest_avg=_first(payload.get("restStressDuration"), payload.get("restAvg")),
        time_in_high=_first(
            payload.get("highStressDuration"), payload.get("timeInHighStress")
        ),
        raw=payload,
    )


def parse_rhr_data(payload: dict[str, Any] | None) -> RHRData | None:
    """Real shape: allMetrics.metricsMap.WELLNESS_RESTING_HEART_RATE[0].value."""
    if not isinstance(payload, dict) or not payload:
        return None

    value = _first(payload.get("value"), payload.get("restingHeartRate"))
    if value is None:
        metrics = _dig(payload, "allMetrics", "metricsMap")
        if isinstance(metrics, dict):
            entries = metrics.get(RHR_METRIC_KEY)
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict) and entry.get("value") is not None:
                        value = entry["value"]
                        break

    baseline = _first(payload.get("baseline"), payload.get("baselineValue"))
    if value is None and baseline is None:
        return None

    deviation = None
    if baseline is not None and value is not None:
        try:
            deviation = float(value) - float(baseline)
        except (TypeError, ValueError):
            deviation = None
    return RHRData(value_bpm=value, baseline_bpm=baseline, deviation_bpm=deviation, raw=payload)


def parse_spo2_data(payload: dict[str, Any] | None) -> SpO2Data | None:
    if not isinstance(payload, dict) or not payload:
        return None
    avg = _first(
        payload.get("averageSpO2"),
        payload.get("averageValue"),
        payload.get("avgPulseOx"),
    )
    low = _first(
        payload.get("lowestSpO2"),
        payload.get("lowestValue"),
        payload.get("minPulseOx"),
        payload.get("minimumValue"),
    )
    if avg is None and low is None:
        return None
    return SpO2Data(avg_pct=avg, min_pct=low, raw=payload)


def parse_body_composition(payload: dict[str, Any] | None) -> BodyCompositionData | None:
    """Real shape wraps values in totalAverage; flat keys are the legacy shape."""
    if not isinstance(payload, dict) or not payload:
        return None
    avg = payload.get("totalAverage")
    avg = avg if isinstance(avg, dict) else {}

    weight = _first(avg.get("weight"), payload.get("weight"), payload.get("weightKg"))
    body_fat = _first(
        avg.get("bodyFat"), payload.get("percentFat"), payload.get("bodyFatPercentage")
    )
    muscle = _first(
        avg.get("muscleMass"), payload.get("muscleMass"), payload.get("skeletalMuscleMass")
    )
    water = _first(
        avg.get("bodyWater"), payload.get("bodyWater"), payload.get("bodyWaterPercentage")
    )
    bone = _first(avg.get("boneMass"), payload.get("boneMass"))
    bmr = _first(payload.get("bmr"), payload.get("basalMet"))
    bmi = _first(avg.get("bmi"), payload.get("bmi"))

    if all(v is None for v in (weight, body_fat, muscle, water, bone, bmr, bmi)):
        return None

    return BodyCompositionData(
        weight_kg=weight,
        body_fat_pct=body_fat,
        muscle_mass_kg=muscle,
        body_water_pct=water,
        bone_mass_kg=bone,
        basal_metabolism_kcal=bmr,
        bmi=bmi,
        raw=payload,
    )


def parse_training_readiness(payload: Any) -> TrainingReadinessData | None:
    """Real endpoint returns a list (empty when the device does not support it)."""
    if isinstance(payload, list):
        payload = payload[0] if payload else None
    if not isinstance(payload, dict) or not payload:
        return None

    raw_score = _first(payload.get("score"), payload.get("trainingReadinessScore"))
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
        recovery_time_hours=_first(payload.get("recoveryTime"), payload.get("recoveryHours")),
        acute_load=_first(payload.get("acuteLoad"), payload.get("load")),
        load_balance=_first(payload.get("loadBalance"), payload.get("loadFocus")),
        sleep_contribution=_first(
            payload.get("sleepScoreContribution"), payload.get("sleepContribution")
        ),
        hrv_contribution=_first(
            payload.get("hrvContribution"), payload.get("hrvStatusContribution")
        ),
        raw=payload,
    )


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
