"""Parser tests bound to REAL captured Garmin payloads.

Every expected value below was read out of tests/fixtures/garmin/, captured
from a live account on 2026-07-25. This file exists because the previous
tests asserted against invented payload shapes, so parsers and tests shared
the same wrong assumption and 294 tests passed while production parsed
nothing. If a fixture is regenerated and these numbers change, update them
from the fixture — never loosen an assertion to make it pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from garmin_coach.adapters.garmin.health import (
    parse_body_battery,
    parse_body_composition,
    parse_hrv_data,
    parse_rhr_data,
    parse_sleep_data,
    parse_spo2_data,
    parse_stress_data,
    parse_training_readiness,
)

FIXTURES = Path(__file__).parent / "fixtures" / "garmin"


def load(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text())


# --- populated day (watch synced) -------------------------------------------


def test_sleep_reads_nested_dailySleepDTO():
    sleep = parse_sleep_data(load("sleep_populated"))
    assert sleep is not None
    # score lives at dailySleepDTO.sleepScores.overall.value — NOT top level
    assert sleep.score == 73
    assert sleep.total_sleep_seconds == 21480
    assert sleep.deep_sleep_seconds == 5700
    assert sleep.light_sleep_seconds == 13080
    assert sleep.rem_sleep_seconds == 2700
    assert sleep.awake_sleep_seconds == 360
    assert sleep.stages["deep"] == 5700


def test_stress_reads_top_level_levels():
    stress = parse_stress_data(load("stress_populated"))
    assert stress is not None
    assert stress.avg == 15
    assert stress.max == 72


def test_rhr_reads_wellness_metric_list():
    rhr = parse_rhr_data(load("rhr_populated"))
    assert rhr is not None
    # allMetrics.metricsMap.WELLNESS_RESTING_HEART_RATE[0].value
    assert isinstance(rhr.value_bpm, (int, float))
    assert rhr.value_bpm > 0
    # this account's payload carries no baseline, so deviation stays unknown
    assert rhr.baseline_bpm is None
    assert rhr.deviation_bpm is None


def test_body_battery_reads_values_array_and_totals():
    bb = parse_body_battery(load("body_battery_populated"))
    assert bb is not None
    assert bb.charged == 59
    assert bb.drained == 12
    # morning = first non-null level in bodyBatteryValuesArray, current = last
    assert bb.morning_value == 23
    assert bb.current_value is not None


# --- un-synced day: envelope present, every leaf null -----------------------


@pytest.mark.parametrize(
    "fixture,parser",
    [
        ("sleep", parse_sleep_data),
        ("stress", parse_stress_data),
        ("rhr", parse_rhr_data),
        ("body_battery", parse_body_battery),
        ("spo2", parse_spo2_data),
        ("body_composition", parse_body_composition),
    ],
)
def test_unsynced_day_returns_none_not_hollow_object(fixture, parser):
    """A hollow object here is what let the snapshot report 'collected, 0 errors'
    while every field inside was None."""
    assert parser(load(fixture)) is None


def test_empty_hrv_and_training_readiness_return_none():
    assert parse_hrv_data(load("hrv")) is None  # {} on devices without HRV
    assert parse_training_readiness(load("training_readiness")) is None  # []


# --- shape handling ---------------------------------------------------------


def test_training_readiness_accepts_list_envelope():
    assert parse_training_readiness([{"score": 82}]).score == 82
    assert parse_training_readiness([]) is None
    assert parse_training_readiness({"score": 40}).level == "red"


def test_zero_values_survive_falsy_coalescing():
    """`a or b` would drop a legitimate 0; parsers must use None checks."""
    assert parse_stress_data({"avgStressLevel": 0, "maxStressLevel": 5}).avg == 0
    sleep = parse_sleep_data({"sleepScore": 0, "sleepTimeSeconds": 0})
    assert sleep is not None and sleep.score == 0


# --- legacy flat shapes still parse (cached payloads) -----------------------


def test_legacy_flat_shapes_still_supported():
    assert parse_sleep_data({"sleepScore": 85, "sleepTimeSeconds": 27000}).score == 85
    assert parse_body_battery([{"bodyBattery": 78}]).morning_value == 78
    assert parse_rhr_data({"value": 48, "baseline": 49}).deviation_bpm == -1.0
    assert parse_body_composition({"weight": 70.0}).weight_kg == 70.0


def test_none_and_garbage_inputs_are_safe():
    for parser in (
        parse_sleep_data,
        parse_stress_data,
        parse_rhr_data,
        parse_spo2_data,
        parse_body_composition,
        parse_hrv_data,
    ):
        assert parser(None) is None
        assert parser({}) is None
    assert parse_body_battery(None) is None
    assert parse_body_battery([]) is None
