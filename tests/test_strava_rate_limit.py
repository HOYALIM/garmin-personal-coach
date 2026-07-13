"""Strava full-history backfill must survive 429s instead of silently truncating."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from garmin_coach.adapters import strava as strava_module
from garmin_coach.adapters.strava import StravaAdapter


def _resp(status_code, payload=None, headers=None):
    return SimpleNamespace(
        status_code=status_code,
        headers=headers or {},
        json=lambda: payload if payload is not None else [],
    )


def _activity(activity_id):
    return {
        "id": activity_id,
        "name": "Run",
        "type": "Run",
        "start_date": "2026-01-01T06:00:00Z",
        "distance": 5000,
        "elapsed_time": 1800,
        "average_speed": 2.8,
    }


def _make_adapter(monkeypatch, responses):
    adapter = StravaAdapter()
    monkeypatch.setattr(adapter, "_get_headers", lambda: {"Authorization": "Bearer x"})
    calls = {"n": 0}

    def fake_request(path, params=None):
        resp = responses[calls["n"]]
        calls["n"] += 1
        return resp

    monkeypatch.setattr(adapter, "_request", fake_request)
    return adapter, calls


def test_get_activities_retries_after_429_then_succeeds(monkeypatch):
    sleeps = []
    monkeypatch.setattr(strava_module.time, "sleep", lambda s: sleeps.append(s))

    responses = [
        _resp(429, headers={"Retry-After": "5"}),
        _resp(200, payload=[_activity(1)]),
    ]
    adapter, calls = _make_adapter(monkeypatch, responses)

    activities = adapter.get_activities(datetime(2026, 1, 1))

    assert len(activities) == 1
    assert sleeps == [5]
    assert calls["n"] == 2


def test_get_activities_gives_up_after_max_retries_but_keeps_partial_results(monkeypatch):
    monkeypatch.setattr(strava_module.time, "sleep", lambda s: None)
    monkeypatch.setattr(strava_module, "RATE_LIMIT_MAX_RETRIES", 2)

    full_page = [_activity(i) for i in range(100)]
    responses = [
        _resp(200, payload=full_page),  # page 1 succeeds, full page -> pagination continues
        _resp(429, headers={"Retry-After": "1"}),
        _resp(429, headers={"Retry-After": "1"}),
        _resp(429, headers={"Retry-After": "1"}),
    ]
    adapter, calls = _make_adapter(monkeypatch, responses)

    activities = adapter.get_activities(datetime(2026, 1, 1))

    assert len(activities) == 100  # page 1 succeeded before rate limiting hit on page 2
    assert calls["n"] == 4  # 1 success + 3 rate-limited attempts (2 retries + give up)


def test_get_activities_defaults_wait_when_no_retry_after_header(monkeypatch):
    sleeps = []
    monkeypatch.setattr(strava_module.time, "sleep", lambda s: sleeps.append(s))

    responses = [_resp(429, headers={}), _resp(200, payload=[])]
    adapter, _ = _make_adapter(monkeypatch, responses)

    adapter.get_activities(datetime(2026, 1, 1))

    assert sleeps == [strava_module.RATE_LIMIT_DEFAULT_WAIT_SECONDS]


def test_get_activities_logs_and_stops_on_other_error_status(monkeypatch):
    warnings = []
    monkeypatch.setattr(
        strava_module, "log_warning", lambda msg: warnings.append(msg)
    )
    responses = [_resp(500)]
    adapter, calls = _make_adapter(monkeypatch, responses)

    activities = adapter.get_activities(datetime(2026, 1, 1))

    assert activities == []
    assert calls["n"] == 1
    assert any("500" in w for w in warnings)


def test_get_activities_paginates_across_many_pages_for_full_history(monkeypatch):
    # 3 full pages (100 each) + 1 partial page confirms multi-year backfills paginate correctly.
    full_page = [_activity(i) for i in range(100)]
    responses = [
        _resp(200, payload=full_page),
        _resp(200, payload=full_page),
        _resp(200, payload=full_page),
        _resp(200, payload=[_activity(9999)]),
    ]
    adapter, calls = _make_adapter(monkeypatch, responses)

    activities = adapter.get_activities(datetime(2016, 1, 1))

    assert len(activities) == 301
    assert calls["n"] == 4
