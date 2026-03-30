import asyncio
import runpy
from datetime import date, datetime
from types import SimpleNamespace

import pytest


def test_activity_fetch_remaining_branches(monkeypatch):
    import garmin_coach.activity_fetch as af

    monkeypatch.setattr(
        af, "_execute_garth_call", lambda operation, fn: (_ for _ in ()).throw(RuntimeError("no"))
    )
    assert af.resume_garth() is False
    assert af.safe_get_daily_summary("2026-03-29") is None
    assert af.safe_get_sleep("2026-03-29") is None
    assert af.safe_get_body_battery("2026-03-29") is None
    assert af.safe_get_training_readiness("2026-03-29") is None
    assert af.safe_get_daily_hr("2026-03-29") is None
    assert af.safe_get_activities(limit=2) == []

    assert af.extract_sleep_hours({"sleepTime": 3600}) == 1.0
    assert af.extract_sleep_hours({"totalSleepSeconds": 7200}) == 2.0
    assert af.extract_sleep_hours({"sleepTimeSeconds": 0}) is None
    assert af.mps_to_pace_str(0) == ""

    sleep_obj = SimpleNamespace(daily_sleep_dto=None)
    metrics = af.fetch_morning_metrics("2026-03-29") if False else None
    monkeypatch.setattr(
        af,
        "safe_get_daily_summary",
        lambda d: SimpleNamespace(body_battery_at_wake_time=None, resting_heart_rate=44),
    )
    monkeypatch.setattr(af, "safe_get_sleep", lambda d: sleep_obj)
    monkeypatch.setattr(
        af,
        "safe_get_body_battery",
        lambda d: [SimpleNamespace(event=SimpleNamespace(body_battery_impact=None))],
    )
    monkeypatch.setattr(af, "safe_get_training_readiness", lambda d: None)
    monkeypatch.setattr(af, "safe_get_daily_hr", lambda d: None)
    out = af.fetch_morning_metrics("2026-03-29")
    assert out["sleep_hours"] is None
    assert out["resting_hr"] == 44
    assert out["body_battery"] is None
    assert out["training_readiness"] is None

    acts = [
        SimpleNamespace(
            activity_type=None,
            start_time_local="2026-03-29T07:00:00",
            distance=None,
            duration=None,
            average_speed=None,
            average_hr=123,
            calories=50,
            activity_id=None,
            activity_name=None,
        )
    ]
    monkeypatch.setattr(af, "safe_get_activities", lambda limit=5: acts)
    got = af.fetch_recent_activities(limit=1)
    assert got[0]["type"] == ""
    assert got[0]["distance_km"] is None
    assert got[0]["duration_min"] is None
    assert got[0]["avg_pace"] is None
    assert got[0]["activity_name"] == ""


def test_ai_coach_remaining_branches(monkeypatch):
    import garmin_coach.ai_coach as ai
    from garmin_coach.profile_manager import (
        AICoachConfig,
        AIFlexibility,
        AITone,
        ProfileData,
        UserProfile,
    )
    from garmin_coach.training_load import FormCategory, LoadSnapshot

    monkeypatch.setattr(ai.ProfileManager, "load", lambda self: None)
    msg = ai.CoachMessage(text="hi", timestamp="now", source="rule")
    assert msg.to_dict()["text"] == "hi"

    engine = ai.AICoachEngine(
        config=AICoachConfig(
            enabled=True, tone=AITone.MOTIVATIONAL, flexibility=AIFlexibility.CONSERVATIVE
        )
    )
    monkeypatch.setattr(
        ai.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError())
    )
    assert engine.is_available is False
    monkeypatch.setattr(
        ai.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ai.subprocess.TimeoutExpired(cmd="omo", timeout=1)
        ),
    )
    assert engine.is_available is False

    profile = UserProfile(profile=ProfileData(name="Pat"))
    ctx = ai.CoachContext(
        date="2026-03-29",
        user_profile=profile,
        load_snapshot=LoadSnapshot(
            ctl=10, atl=20, tsb=-10, form=FormCategory.TIRED, date=date(2026, 3, 29)
        ),
        self_reported={"energy": 1, "sleep_hours": 5},
        upcoming_session={"type": "easy", "sport": "run"},
        last_session={"type": "run", "distance_km": 5},
        week_number=3,
    )
    assert "Current form" in engine._build_evening_prompt(ctx)
    assert "week 3" in engine._build_weekly_prompt(ctx)
    assert "Pat" in engine._context_to_json(ctx)
    advice = engine._rule_advice(ctx)
    assert "Low energy reported" in advice
    assert "Low sleep" in advice
    assert engine.format_message(ai.CoachMessage(text="x", timestamp="n", source="omo")).startswith(
        "🤖"
    )
    assert engine.format_message(
        ai.CoachMessage(text="x", timestamp="n", source="rule_based")
    ).startswith("⚙️")
    assert "science-based" in engine._build_system_prompt(ctx, "mode")

    monkeypatch.setattr(
        ai.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="")
    )
    msg = engine._omo_ask(ctx, "question", "advice")
    assert msg.source == "omo"
    monkeypatch.setattr(
        ai.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    msg = engine._omo_ask(ctx, "question", "advice")
    assert msg.text
    monkeypatch.setattr(
        ai.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="")
    )
    assert engine.plan_adjustment_advice(ctx, "fatigue").text
    assert engine.daily_evening_advice(ctx).text
    assert engine.weekly_review_advice(ctx).text


def test_weekly_review_garmin_writeback_validation_mcp_entry(monkeypatch, capsys, tmp_path):
    import garmin_coach.weekly_review as weekly
    import garmin_coach.garmin_writeback as writeback
    import garmin_coach.wizard.validation as validation
    import mcp_server.__main__ as mcp_main

    assert weekly.get_week_start(date(2026, 3, 30)).isoformat() == "2026-03-30"
    calc = SimpleNamespace(
        get_weekly_stats=lambda ws: SimpleNamespace(
            to_dict=lambda: {
                "week_start": ws.isoformat(),
                "session_count": 0,
                "total_hours": 0,
                "total_trimp": 0,
                "ctl_change": 0,
                "sport_breakdown": {},
            }
        ),
        get_snapshot=lambda d: None,
    )
    assert weekly.get_week_stats(date(2026, 3, 24), calc)["week_start"] == "2026-03-24"
    assert "Weekly Summary" in weekly.format_weekly_summary(
        {
            "week_start": "2026-03-24",
            "session_count": 1,
            "total_hours": 1.5,
            "total_trimp": 100,
            "ctl_change": 2,
            "sport_breakdown": {"run": 50},
        },
        [],
    )

    pm = SimpleNamespace(load=lambda: None)
    with pytest.raises(RuntimeError):
        weekly.build_weekly_context(date(2026, 3, 24), pm, calc)

    monkeypatch.setattr(weekly, "resume_garth", lambda: True)
    monkeypatch.setattr(weekly, "ProfileManager", lambda: SimpleNamespace(exists=lambda: False))
    weekly.run_weekly(date(2026, 3, 24))
    assert "No profile found" in capsys.readouterr().out

    monkeypatch.setattr(
        weekly, "run_weekly", lambda target=None: capsys.writeouterr if False else None
    )
    monkeypatch.setattr("sys.argv", ["weekly_review", "--date", "2026-03-24"])
    weekly.main()

    monkeypatch.setattr(writeback, "GARMIN_EMAIL", "")
    monkeypatch.setattr(writeback, "GARMIN_PASSWORD", "")
    assert writeback._garminconnect_available() is False
    assert writeback.set_activity_name("1", "Title")["success"] is False
    monkeypatch.setattr(writeback, "_garminconnect_available", lambda: True)
    monkeypatch.setitem(
        __import__("sys").modules,
        "garminconnect",
        SimpleNamespace(
            Garmin=lambda e, p: SimpleNamespace(set_activity_name=lambda activity_id, title: True)
        ),
    )
    assert writeback.set_activity_name("1", "Title")["success"] is True
    monkeypatch.setitem(
        __import__("sys").modules,
        "garminconnect",
        SimpleNamespace(Garmin=lambda e, p: (_ for _ in ()).throw(RuntimeError("bad"))),
    )
    assert writeback.set_activity_name("1", "Title")["success"] is False

    assert validation.validate_age(None) == (True, "")
    assert validation.validate_age("x")[0] is False
    assert validation.validate_weight(None) == (True, "")
    assert validation.validate_weight(10)[0] is False
    assert validation.validate_height(None) == (True, "")
    assert validation.validate_height("x")[0] is False
    assert validation.validate_height(300)[0] is False
    assert validation.validate_max_hr(None) == (True, "")
    assert validation.validate_max_hr("x")[0] is False
    assert validation.validate_resting_hr(None) == (True, "")
    assert validation.validate_resting_hr("x")[0] is False
    assert validation.validate_resting_hr(10)[0] is False
    assert validation.validate_ftp(None) == (True, "")
    assert validation.validate_ftp("x")[0] is False
    assert validation.validate_ftp(10)[0] is False
    assert validation.validate_training_days(None) == (True, "")
    assert validation.validate_training_days("x")[0] is False
    assert validation.validate_name(None) == (True, "")
    assert validation.validate_name(123)[0] is False
    assert validation.validate_name("x" * 101)[0] is False
    assert validation.validate_sports([])[0] is False
    assert validation.validate_sports(["bad"])[0] is False
    ok, errors = validation.validate_profile({"sports": []})
    assert ok is False and errors

    captured = {}

    class FakeTool:
        def __init__(self, **kwargs):
            captured.setdefault("tools", []).append(kwargs)

    class FakeTextContent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeServer:
        def __init__(self, name):
            captured["name"] = name

        def list_tools(self):
            def deco(fn):
                captured["list_tools"] = fn
                return fn

            return deco

        def call_tool(self):
            def deco(fn):
                captured["call_tool"] = fn
                return fn

            return deco

        def create_initialization_options(self):
            return {"ok": True}

        async def run(self, read_stream, write_stream, options):
            captured["ran"] = (read_stream, write_stream, options)

    class FakeStdio:
        async def __aenter__(self):
            return ("r", "w")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(mcp_main, "Server", FakeServer)
    monkeypatch.setattr(mcp_main, "Tool", FakeTool)
    monkeypatch.setattr(mcp_main, "TextContent", FakeTextContent)
    monkeypatch.setattr(mcp_main, "stdio_server", lambda: FakeStdio())
    monkeypatch.setattr(
        mcp_main, "handle_tool_call", lambda name, arguments: {"status": "ok", "name": name}
    )
    asyncio.run(mcp_main.main())
    tools = asyncio.run(captured["list_tools"]())
    contents = asyncio.run(captured["call_tool"]("health", {}))
    assert tools
    assert contents[0].kwargs["text"]
    monkeypatch.setattr("asyncio.run", lambda coro: captured.setdefault("asyncio_called", True))
    runpy.run_module("mcp_server.__main__", run_name="__main__")
    assert captured["asyncio_called"] is True
