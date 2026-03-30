import json
from datetime import date, datetime
from types import SimpleNamespace

import pytest


def test_activity_fetch_retry_and_metrics(monkeypatch):
    import garmin_coach.activity_fetch as activity_fetch

    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ConnectionError("temporary")
        return "ok"

    assert activity_fetch._execute_garth_call("flaky", flaky) == "ok"
    assert attempts["count"] == 3

    sleep_dto = SimpleNamespace(
        sleep_time_seconds=28800,
        deep_sleep_seconds=1000,
        light_sleep_seconds=2000,
        rem_sleep_seconds=1000,
        awake_sleep_seconds=200,
        awake_count=1,
        sleep_scores=SimpleNamespace(overall=SimpleNamespace(value=80, qualifier_key="good")),
    )
    sleep_obj = SimpleNamespace(daily_sleep_dto=sleep_dto)
    readiness_obj = SimpleNamespace(score=72, hrv_factor_feedback="Balanced")
    daily_hr = SimpleNamespace(resting_heart_rate=48)
    summary = SimpleNamespace(body_battery_at_wake_time=80, resting_heart_rate=49)

    monkeypatch.setattr(activity_fetch, "safe_get_daily_summary", lambda d: summary)
    monkeypatch.setattr(activity_fetch, "safe_get_sleep", lambda d: sleep_obj)
    monkeypatch.setattr(activity_fetch, "safe_get_body_battery", lambda d: [])
    monkeypatch.setattr(activity_fetch, "safe_get_training_readiness", lambda d: readiness_obj)
    monkeypatch.setattr(activity_fetch, "safe_get_daily_hr", lambda d: daily_hr)

    metrics = activity_fetch.fetch_morning_metrics("2026-03-29")
    assert metrics["sleep_hours"] == 8.0
    assert metrics["training_readiness"] == 72
    assert metrics["resting_hr"] == 48

    act = SimpleNamespace(
        activity_type=SimpleNamespace(type_key="running"),
        start_time_local=datetime(2026, 3, 29, 7, 0, 0),
        distance=10000,
        duration=3600,
        average_speed=3.33,
        average_hr=150,
        calories=600,
        activity_name="Morning Run",
        activity_id=123,
    )
    monkeypatch.setattr(activity_fetch, "safe_get_activities", lambda limit=5: [act])
    activities = activity_fetch.fetch_recent_activities(limit=1)
    assert activities[0]["type"] == "running"
    assert activities[0]["distance_km"] == 10.0


def test_handler_rule_and_ai_paths(monkeypatch):
    import garmin_coach.handler as handler

    monkeypatch.setattr(
        handler,
        "_load_config",
        lambda: {
            "name": "Pat",
            "setup_complete": True,
            "garmin_connected": True,
            "ai": {"tone": "direct"},
        },
    )
    monkeypatch.setattr(
        handler,
        "get_training_load_manager",
        lambda: SimpleNamespace(
            get_context=lambda: {
                "ctl": 50,
                "atl": 40,
                "tsb": 10,
                "form": "prepared",
                "date": "2026-03-29",
            }
        ),
    )

    message_handler = handler.MessageHandler(user_context={"name": "Pat"})
    assert "TSB" in message_handler.handle("컨디션 어때?", client_key="a")
    assert "Today's" in message_handler.handle(
        "오늘 일정", client_key="b"
    ) or "training" in message_handler.handle("오늘 일정", client_key="b")

    class FakeAI:
        def generate_response(self, message, context):
            return "ai answer"

    message_handler._ai_coach = FakeAI()
    assert message_handler.handle("hello", client_key="c") == "ai answer"

    class BrokenAI:
        def generate_response(self, message, context):
            raise RuntimeError("boom")

    message_handler._ai_coach = BrokenAI()
    assert message_handler.handle("피곤해", client_key="d")


def test_mcp_server_handlers(monkeypatch):
    import mcp_server.server as server

    fake_manager = SimpleNamespace(
        get_context=lambda: {
            "ctl": 40,
            "atl": 35,
            "tsb": 5,
            "form": "prepared",
            "date": "2026-03-29",
        },
        calculator=SimpleNamespace(
            get_sessions_in_range=lambda start, end: [
                SimpleNamespace(
                    date=date(2026, 3, 28),
                    trimp=80,
                    sport=SimpleNamespace(value="running"),
                    duration_min=45,
                    description="easy",
                )
            ]
        ),
    )
    monkeypatch.setattr(server, "get_training_load_manager", lambda: fake_manager)
    monkeypatch.setattr(server, "check_garmin_connection", lambda: True)
    monkeypatch.setattr(server, "check_training_load_manager", lambda: True)
    monkeypatch.setattr(
        "garmin_coach.handler.process_message", lambda message: f"handled:{message}"
    )
    monkeypatch.setattr(
        "garmin_coach.wizard.load_config",
        lambda: {
            "name": "Pat",
            "age": 30,
            "sports": ["running"],
            "fitness_level": "intermediate",
            "setup_complete": True,
        },
    )

    assert server.get_training_status()["status"] == "success"
    assert server.get_user_profile()["data"]["name"] == "Pat"
    assert server.get_recent_activities(7)["data"][0]["trimp"] == 80
    assert server.handle_natural_language("hi")["response"] == "handled:hi"
    assert server.get_training_plan()["status"] == "success"
    assert server.handle_tool_call("health", {})["status"] == "healthy"
    assert server.handle_tool_call("get_recent_activities", {"days": 7})["status"] == "success"
    assert server.handle_tool_call("unknown", {})["code"] == server.ERROR_METHOD_NOT_FOUND


def test_ai_coach_rule_and_omo_paths(monkeypatch):
    from garmin_coach.ai_coach import AICoachEngine, CoachContext
    from garmin_coach.profile_manager import AICoachConfig, ProfileData, UserProfile
    from garmin_coach.training_load import FormCategory, LoadSnapshot

    class FakeProfileManager:
        def __init__(self):
            self.config_path = "config.yaml"

        def load(self):
            return None

    monkeypatch.setattr("garmin_coach.ai_coach.ProfileManager", FakeProfileManager)

    profile = UserProfile(profile=ProfileData(name="Pat"))
    ctx = CoachContext(
        date="2026-03-29",
        user_profile=profile,
        load_snapshot=LoadSnapshot(
            ctl=40, atl=30, tsb=10, form=FormCategory.FRESH, date=date(2026, 3, 29)
        ),
        self_reported={"energy": 2, "sleep_hours": 5},
        upcoming_session={"type": "easy", "sport": "running"},
    )

    engine = AICoachEngine(config=AICoachConfig(enabled=False))
    fallback = engine.ask(ctx, "How am I doing?")
    assert fallback.source == "rule_based"
    assert "Rule-based advice" in fallback.text

    def fake_run(args, **kwargs):
        if "--version" in args:
            return SimpleNamespace(returncode=0, stdout="omo 1.0")
        return SimpleNamespace(returncode=0, stdout="AI says rest")

    monkeypatch.setattr("garmin_coach.ai_coach.subprocess.run", fake_run)
    engine = AICoachEngine(config=AICoachConfig(enabled=True))
    ai_msg = engine.ask(ctx, "Need advice")
    assert ai_msg.source == "omo"
    assert ai_msg.text == "AI says rest"
    assert "Pat" in engine._context_to_json(ctx)
