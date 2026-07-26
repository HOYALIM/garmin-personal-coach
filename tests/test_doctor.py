"""Tests for the schema-drift alarm.

The whole point of doctor is catching the case where Garmin sends real data
and our parser returns nothing. That case must be loud (PARSE_MISS) and must
never be confused with the benign case of Garmin having no data at all.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from garmin_coach.adapters.garmin.health import parse_sleep_data
from garmin_coach.doctor import (
    EMPTY,
    FAIL,
    OK,
    PARSE_MISS,
    classify,
    diagnose,
    has_parsed_values,
    has_substantive_data,
    run_doctor,
)

FIXTURES = Path(__file__).parent / "fixtures" / "garmin"


def fixture(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text())


# -- substantive-data detection ----------------------------------------------


def test_real_payload_is_substantive_and_unsynced_one_is_not():
    assert has_substantive_data(fixture("sleep_populated")) is True
    # envelope with ids/dates but every metric null
    assert has_substantive_data(fixture("sleep")) is False
    assert has_substantive_data(fixture("hrv")) is False  # {}
    assert has_substantive_data(fixture("training_readiness")) is False  # []


def test_ids_and_timestamps_alone_are_not_substantive():
    assert has_substantive_data({"userProfilePK": 12, "calendarDate": "2026-07-24"}) is False
    assert has_substantive_data({"startTimestampGMT": 1784880635000}) is False
    assert has_substantive_data({"userProfilePK": 12, "avgStressLevel": 15}) is True


def test_has_parsed_values_ignores_raw_only_objects():
    assert has_parsed_values(None) is False
    assert has_parsed_values(SimpleNamespace(raw={"lots": "of stuff"})) is False
    assert has_parsed_values(SimpleNamespace(score=73, raw={})) is True
    assert has_parsed_values(SimpleNamespace(score=None, stages={}, raw={})) is False


# -- the four verdicts -------------------------------------------------------


def test_classify_ok_when_parser_extracts_values():
    raw = fixture("sleep_populated")
    assert classify(raw, parse_sleep_data(raw)) == OK


def test_classify_empty_when_garmin_has_no_data():
    raw = fixture("sleep")
    assert classify(raw, parse_sleep_data(raw)) == EMPTY


def test_classify_parse_miss_is_the_incident_signature():
    """Real data in, nothing out — exactly what happened silently in prod."""
    substantive_but_unparseable = {"someNewGarminKey": {"sleepScoreV2": 88}}
    assert classify(substantive_but_unparseable, None) == PARSE_MISS


def test_diagnose_reports_per_metric_verdicts_and_survives_exceptions():
    populated = fixture("sleep_populated")

    class Client:
        def get_sleep_data(self, d):
            return populated

        def get_hrv_data(self, d):
            return fixture("hrv")

        def get_body_battery(self, d, e):
            raise RuntimeError("network down")

        def get_stress_data(self, d):
            return {"avgStressLevel": 15}

        def get_rhr_day(self, d):
            return {"brandNewShape": {"restingHr": 54}}

        def get_spo2_data(self, d):
            return fixture("spo2")

        def get_body_composition(self, d):
            return fixture("body_composition")

        def get_training_readiness(self, d):
            return fixture("training_readiness")

    class Adapter(Client):
        def get_sleep_data(self, d):
            return parse_sleep_data(populated)

        def get_hrv_data(self, d):
            return None

        def get_stress_data(self, d):
            return SimpleNamespace(avg=15, raw={})

        def get_rhr_day(self, d):
            return None  # parser blind to the new shape

        def get_spo2_data(self, d):
            return None

        def get_body_composition(self, d):
            return None

        def get_training_readiness(self, d):
            return None

    verdicts = {r["metric"]: r["verdict"] for r in diagnose(Client(), Adapter(), "2026-07-24")}
    assert verdicts["sleep"] == OK
    assert verdicts["stress"] == OK
    assert verdicts["hrv"] == EMPTY
    assert verdicts["training_readiness"] == EMPTY
    assert verdicts["rhr"] == PARSE_MISS  # the alarm
    assert verdicts["body_battery"] == FAIL


# -- CLI surface -------------------------------------------------------------


def test_run_doctor_exits_nonzero_on_parse_miss(capsys):
    class Client:
        def __getattr__(self, _name):
            return lambda *a, **k: {"unexpectedShape": {"value": 42}}

    class Adapter:
        def __getattr__(self, _name):
            return lambda *a, **k: None

    code = run_doctor(date_str="2026-07-24", client=Client(), adapter=Adapter())
    out = capsys.readouterr().out
    assert code == 1
    assert "스키마" in out


def test_run_doctor_exits_zero_when_only_empty(capsys):
    class Client:
        def __getattr__(self, _name):
            return lambda *a, **k: {}

    class Adapter:
        def __getattr__(self, _name):
            return lambda *a, **k: None

    code = run_doctor(date_str="2026-07-24", client=Client(), adapter=Adapter())
    assert code == 0
    assert "데이터 없음" in capsys.readouterr().out


def test_run_doctor_requires_a_session(tmp_path, capsys):
    code = run_doctor(date_str="2026-07-24", token_dir=str(tmp_path / "missing"))
    assert code == 1
    assert "connect-garmin" in capsys.readouterr().out


def test_timeseries_timestamps_alone_do_not_look_like_data():
    """bodyBatteryValuesArray keeps its timestamps on days with no readings;
    counting those as data made an un-synced day look like a parser failure."""
    assert has_substantive_data(fixture("body_battery")) is False
    assert has_substantive_data(fixture("body_battery_populated")) is True
    assert has_substantive_data({"bodyBatteryValuesArray": [[1784937600001, None]]}) is False
    assert has_substantive_data({"bodyBatteryValuesArray": [[1784937600001, 23]]}) is True
