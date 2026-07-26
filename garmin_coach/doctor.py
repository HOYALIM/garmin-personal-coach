"""`garmin-coach doctor` — live contract check against Garmin's API.

This exists because of a specific failure: the health parsers were written
against imagined payload shapes, the tests were written against the same
imagination, and 294 tests passed while every metric parsed to None in
production. Nothing in the suite could catch it, because the suite never saw
a real payload.

Doctor closes that hole from the other side. It calls the live API and
compares "did Garmin send something substantive?" against "did our parser
get anything out of it?". Those two answers disagreeing is PARSE_MISS — the
schema-drift alarm. It is the check that would have caught the incident on
day one, and the one that will catch Garmin's next silent schema change.

Verdicts:
  OK         parser extracted usable values
  EMPTY      Garmin returned a data-less payload (watch not synced, or the
             device does not support this metric) — not a defect
  PARSE_MISS Garmin returned real data, parser extracted nothing — ALARM
  FAIL       the call itself raised
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Callable

from garmin_coach.adapters.garmin.client import default_token_dir

OK = "OK"
EMPTY = "EMPTY"
PARSE_MISS = "PARSE_MISS"
FAIL = "FAIL"

# Keys that carry no health signal — a payload containing only these is an
# envelope, not data.
_STRUCTURAL_KEYS = {
    "userProfilePK",
    "userProfileId",
    "userProfilePk",
    "profileId",
    "deviceId",
    "id",
    "calendarDate",
    "startDate",
    "endDate",
    "date",
    "statisticsStartDate",
    "statisticsEndDate",
    "from",
    "until",
}

# Advisory sub-objects Garmin ships regardless of whether anything was
# measured. sleepNeed (how much sleep you *should* get) is present on days the
# watch recorded no sleep at all, so counting it as data would make every
# un-synced day look like a parser failure.
_ADVISORY_KEYS = {"sleepNeed", "nextSleepNeed"}

# Timeseries shaped [[epoch_millis, value], ...]. The timestamps are always
# populated even when every value is null, so a generic "any number present"
# check would flag an un-synced day as a parser failure. Judge these on the
# value slot only. A doctor that cries wolf gets ignored.
_TIMESERIES_KEYS = {
    "bodyBatteryValuesArray",
    "stressValuesArray",
    "spo2ValuesArray",
    "respirationValuesArray",
}


def _timeseries_has_values(series: Any) -> bool:
    if not isinstance(series, (list, tuple)):
        return False
    for point in series:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            if point[1] is not None:
                return True
        elif point is not None and not isinstance(point, (list, tuple)):
            return True
    return False

_VERDICT_LABEL = {
    OK: "✅ 정상",
    EMPTY: "⌚ 데이터 없음",
    PARSE_MISS: "🚨 파싱 실패 (스키마 변경 의심)",
    FAIL: "❌ 호출 실패",
}


def has_substantive_data(payload: Any, _depth: int = 0) -> bool:
    """True if the payload carries any real value beyond ids/dates/timestamps."""
    if _depth > 6:
        return False
    if payload is None or isinstance(payload, bool):
        return False
    if isinstance(payload, (int, float)):
        return True
    if isinstance(payload, str):
        return bool(payload.strip())
    if isinstance(payload, (list, tuple)):
        return any(has_substantive_data(item, _depth + 1) for item in payload)
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in _STRUCTURAL_KEYS or key in _ADVISORY_KEYS:
                continue
            if str(key).lower().endswith(("timestampgmt", "timestamplocal")):
                continue
            if key in _TIMESERIES_KEYS:
                if _timeseries_has_values(value):
                    return True
                continue
            if has_substantive_data(value, _depth + 1):
                return True
        return False
    return False


def has_parsed_values(parsed: Any) -> bool:
    """True if a parsed model object carries at least one meaningful field."""
    if parsed is None:
        return False
    fields = getattr(parsed, "__dict__", {})
    return any(
        key != "raw" and value not in (None, {}, [])
        for key, value in fields.items()
    )


def classify(raw: Any, parsed: Any) -> str:
    if has_parsed_values(parsed):
        return OK
    return PARSE_MISS if has_substantive_data(raw) else EMPTY


def _checks(client: Any, adapter: Any, date_str: str) -> list[tuple[str, Callable, Callable]]:
    """(metric, raw getter, parsed getter) — raw and parsed must hit the same endpoint."""
    return [
        ("sleep", lambda: client.get_sleep_data(date_str), lambda: adapter.get_sleep_data(date_str)),
        ("hrv", lambda: client.get_hrv_data(date_str), lambda: adapter.get_hrv_data(date_str)),
        (
            "body_battery",
            lambda: client.get_body_battery(date_str, date_str),
            lambda: adapter.get_body_battery(date_str, date_str),
        ),
        (
            "stress",
            lambda: client.get_stress_data(date_str),
            lambda: adapter.get_stress_data(date_str),
        ),
        ("rhr", lambda: client.get_rhr_day(date_str), lambda: adapter.get_rhr_day(date_str)),
        ("spo2", lambda: client.get_spo2_data(date_str), lambda: adapter.get_spo2_data(date_str)),
        (
            "body_composition",
            lambda: client.get_body_composition(date_str),
            lambda: adapter.get_body_composition(date_str),
        ),
        (
            "training_readiness",
            lambda: client.get_training_readiness(date_str),
            lambda: adapter.get_training_readiness(date_str),
        ),
    ]


def diagnose(client: Any, adapter: Any, date_str: str) -> list[dict[str, Any]]:
    results = []
    for metric, get_raw, get_parsed in _checks(client, adapter, date_str):
        try:
            raw = get_raw()
            parsed = get_parsed()
            verdict = classify(raw, parsed)
            detail = ""
        except Exception as exc:
            verdict = FAIL
            detail = f"{type(exc).__name__}: {exc}"[:120]
        results.append({"metric": metric, "verdict": verdict, "detail": detail})
    return results


def run_doctor(
    date_str: str | None = None,
    client: Any = None,
    adapter: Any = None,
    token_dir: str | None = None,
) -> int:
    """Print a per-metric contract report. Returns a shell exit code."""
    # Default to yesterday: today is frequently not synced yet, and an
    # un-synced day makes every metric look EMPTY for uninteresting reasons.
    date_str = date_str or (date.today() - timedelta(days=1)).isoformat()
    token_dir = token_dir or default_token_dir()

    if client is None or adapter is None:
        expanded = os.path.expanduser(token_dir)
        if not os.path.isdir(expanded) or not os.listdir(expanded):
            print(f"❌ Garmin 세션이 없습니다 ({expanded} 비어 있음).")
            print("   먼저 실행하세요: garmin-coach connect-garmin --email <your@email>")
            return 1
        from garmin_coach.adapters.garmin import GarminAdapter
        from garmin_coach.adapters.garmin.client import garmin_client

        try:
            garmin_client.resume(token_dir)
        except Exception as exc:
            print(f"❌ Garmin 세션 복구 실패: {exc}")
            print("   garmin-coach connect-garmin --force 로 다시 로그인하세요.")
            return 1
        client = client or garmin_client
        adapter = adapter or GarminAdapter()

    print(f"🩺 Garmin 데이터 계약 점검 ({date_str})\n")
    results = diagnose(client, adapter, date_str)

    width = max(len(r["metric"]) for r in results)
    for r in results:
        line = f"  {r['metric']:<{width}}  {_VERDICT_LABEL[r['verdict']]}"
        if r["detail"]:
            line += f"  — {r['detail']}"
        print(line)

    broken = [r for r in results if r["verdict"] in (PARSE_MISS, FAIL)]
    empty = [r for r in results if r["verdict"] == EMPTY]
    print()
    if broken:
        print(f"🚨 {len(broken)}개 지표에 문제가 있습니다.")
        if any(r["verdict"] == PARSE_MISS for r in broken):
            print("   PARSE_MISS는 Garmin이 데이터를 줬는데 파서가 못 읽은 경우입니다 —")
            print("   스키마가 바뀌었을 가능성이 높습니다. 실응답을 tests/fixtures/garmin/에")
            print("   다시 캡처하고 파서를 맞춰주세요.")
        return 1
    if empty:
        print(f"✅ 파싱 정상. ({len(empty)}개 지표는 데이터 없음 — 워치 미동기화 또는 미지원)")
    else:
        print("✅ 모든 지표 정상.")
    return 0


__all__ = [
    "EMPTY",
    "FAIL",
    "OK",
    "PARSE_MISS",
    "classify",
    "diagnose",
    "has_parsed_values",
    "has_substantive_data",
    "run_doctor",
]
