import io
import json
from unittest.mock import mock_open
from types import SimpleNamespace

import pytest


def test_oauth_flow_and_status(monkeypatch, tmp_path, capsys):
    import garmin_coach.wizard.oauth as oauth

    monkeypatch.setattr(oauth, "CONFIG_DIR", str(tmp_path))

    class FakeHandler:
        received_params = {"code": ["abc"]}

    next_params = {"value": {"code": ["abc"]}}

    class FakeServer:
        def __init__(self, addr, handler):
            self.closed = False

        def handle_request(self):
            FakeHandler.received_params = next_params["value"]
            return None

        def server_close(self):
            self.closed = True

    class FakeThread:
        def __init__(self, target):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(oauth, "OAuthCallbackHandler", FakeHandler)
    monkeypatch.setattr(oauth, "HTTPServer", FakeServer)
    monkeypatch.setattr(oauth.threading, "Thread", FakeThread)
    monkeypatch.setattr(oauth.time, "sleep", lambda x: None)
    monkeypatch.setattr(oauth.webbrowser, "open", lambda url: True)
    monkeypatch.setitem(
        __import__("sys").modules,
        "requests",
        SimpleNamespace(
            post=lambda *args, **kwargs: SimpleNamespace(
                status_code=200, json=lambda: {"access_token": "tok", "expires_at": 9999999999}
            )
        ),
    )
    token = oauth.OAuthFlow.strava_auth("cid", "secret", redirect_port=9999)
    assert token["access_token"] == "tok"

    next_params["value"] = {"state": ["no_code"]}
    assert oauth.OAuthFlow.strava_auth("cid", "secret", redirect_port=9999) is None

    next_params["value"] = {"code": ["abc"]}
    monkeypatch.setitem(
        __import__("sys").modules,
        "requests",
        SimpleNamespace(
            post=lambda *args, **kwargs: SimpleNamespace(status_code=500, json=lambda: {})
        ),
    )
    assert oauth.OAuthFlow.strava_auth("cid", "secret", redirect_port=9999) is None

    oauth.OAuthFlow.save_strava_token({"access_token": "tok", "expires_at": 9999999999})
    assert oauth.OAuthFlow.check_strava_token() is True
    oauth.OAuthFlow.save_strava_token({"access_token": "tok", "expires_at": 1})
    monkeypatch.setattr(oauth.time, "time", lambda: 100)
    assert oauth.OAuthFlow.check_strava_token() is False

    token_file = tmp_path / "strava_token.json"
    token_file.write_text("not json")
    assert oauth.OAuthFlow.check_strava_token() is False

    inputs = iter(["id", "secret"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    monkeypatch.setattr(
        oauth.OAuthFlow, "strava_auth", lambda client_id, client_secret: {"access_token": "tok"}
    )
    saved = []
    monkeypatch.setattr(oauth.OAuthFlow, "save_strava_token", lambda token: saved.append(token))
    assert oauth.setup_strava_oauth() is True
    assert saved[0]["access_token"] == "tok"

    inputs = iter(["id", "secret"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    monkeypatch.setattr(oauth.OAuthFlow, "strava_auth", lambda client_id, client_secret: None)
    assert oauth.setup_strava_oauth() is False

    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.adapters.garmin",
        SimpleNamespace(GarminAdapter=lambda: SimpleNamespace(is_authenticated=lambda: True)),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.adapters.strava",
        SimpleNamespace(StravaAdapter=object),
    )
    monkeypatch.setattr(oauth.OAuthFlow, "check_strava_token", lambda: True)
    assert oauth.check_oauth_status() == {"garmin": True, "strava": True}


def test_handler_paths(monkeypatch):
    import garmin_coach.handler as handler

    monkeypatch.setattr(handler, "log_warning", lambda *args, **kwargs: None)
    monkeypatch.setitem(
        __import__("sys").modules,
        "yaml",
        SimpleNamespace(
            safe_load=lambda fp: {
                "profile": {"name": "Pat", "age": 30},
                "garmin": {"connected": True},
                "ai_coach": {
                    "enabled": True,
                    "tone": "direct",
                    "flexibility": "moderate",
                    "api_key": "k",
                },
            }
        ),
    )
    monkeypatch.setattr(handler.os.path, "exists", lambda path: True)
    monkeypatch.setattr("builtins.open", mock_open(read_data="profile: {}\n"))
    cfg = handler._load_config()
    assert cfg["name"] == "Pat"
    assert handler._normalize_config({"x": 1}) == {"x": 1}

    monkeypatch.setattr(
        handler,
        "get_training_load_manager",
        lambda: SimpleNamespace(get_context=lambda: {"ctl": 0, "atl": 0, "tsb": 0}),
    )
    context = handler._get_real_context()
    assert context["has_data"] is False

    monkeypatch.setattr(
        handler, "get_training_load_manager", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    context = handler._get_real_context()
    assert context["ctl"] == 0

    class FakeLimiter:
        def __init__(self, allowed=True):
            self.allowed = allowed

        def is_allowed(self, key):
            return self.allowed

        def get_remaining(self, key):
            return 0

        def get_reset_time(self, key):
            return 9

    monkeypatch.setattr(handler, "HANDLER_LIMITER", FakeLimiter(allowed=False))
    h = handler.MessageHandler(config={"ai": {}}, user_context={})
    with pytest.raises(handler.RateLimitError):
        h.handle("hello")

    monkeypatch.setattr(handler, "HANDLER_LIMITER", FakeLimiter(allowed=True))
    monkeypatch.setattr(
        handler,
        "_get_real_context",
        lambda: {"name": "Pat", "has_data": True, "ctl": 55, "atl": 35, "tsb": 30},
    )
    monkeypatch.setattr(handler, "detect_intent", lambda message: handler.Intent.WAKE_UP)
    h = handler.MessageHandler(config={"ai": {}}, user_context={})
    assert "Good morning" in h.handle("morning")

    monkeypatch.setattr(
        handler,
        "_get_real_context",
        lambda: {"name": "Pat", "has_data": True, "ctl": 55, "atl": 35, "tsb": -30},
    )
    monkeypatch.setattr(handler, "detect_intent", lambda message: handler.Intent.WORKOUT_COMPLETE)
    assert "Recovery is crucial" in h.handle("done", client_key="x")

    monkeypatch.setattr(
        handler,
        "_get_real_context",
        lambda: {"name": "Pat", "has_data": True, "ctl": 55, "atl": 35, "tsb": 30},
    )
    monkeypatch.setattr(handler, "detect_intent", lambda message: handler.Intent.ASK_STATUS)
    assert "CTL" in h.handle("status", client_key="y")
    monkeypatch.setattr(handler, "detect_intent", lambda message: handler.Intent.ASK_PLAN)
    assert "high intensity" in h.handle("plan", client_key="z").lower()
    monkeypatch.setattr(handler, "detect_intent", lambda message: handler.Intent.ASK_HELP)
    assert "I'm your coach" in h.handle("help", client_key="a")
    monkeypatch.setattr(handler, "detect_intent", lambda message: handler.Intent.ASK_NUTRITION)
    assert "High training load" in h.handle("food", client_key="b")
    monkeypatch.setattr(handler, "detect_intent", lambda message: handler.Intent.SYMPTOM_REPORT)
    assert "Rest is training" in h.handle("tired", client_key="c")
    assert "Don't push through pain" in h._handle_symptom_report("pain", {})
    assert "Tell me more" in h._handle_symptom_report("weird", {})
    assert "coach" in h._handle_unknown({"name": "Pat"})
    assert "ready for high intensity" in h._get_form_status(30)
    assert "great training form" in h._get_form_status(15)
    assert "sweet spot" in h._get_form_status(0)
    assert "fatigue" in h._get_form_status(-15)
    assert "Rest recommended" in h._get_form_status(-30)

    monkeypatch.setattr(
        handler,
        "_get_real_context",
        lambda: {"name": "Pat", "has_data": False, "tsb": 0, "ctl": 0, "atl": 0},
    )
    monkeypatch.setattr(handler, "detect_intent", lambda message: handler.Intent.WAKE_UP)
    assert "Welcome" in h.handle("wake", client_key="d")
    monkeypatch.setattr(handler, "detect_intent", lambda message: handler.Intent.ASK_STATUS)
    assert "No training data yet" in h.handle("status", client_key="e")
    monkeypatch.setattr(handler, "detect_intent", lambda message: handler.Intent.ASK_PLAN)
    assert "Set up your profile first" in h.handle("plan", client_key="f")

    monkeypatch.setenv("OPENAI_API_KEY", "envkey")
    fake_ai_calls = []

    class FakeAI:
        def __init__(self, api_key):
            fake_ai_calls.append(api_key)

        def generate_response(self, message, context):
            return "ai ok"

    monkeypatch.setitem(
        __import__("sys").modules, "garmin_coach.ai_simple", SimpleNamespace(AICoach=FakeAI)
    )
    monkeypatch.setattr(
        handler,
        "_get_real_context",
        lambda: {"name": "Pat", "has_data": True, "tsb": 0, "ctl": 1, "atl": 1},
    )
    monkeypatch.setattr(handler, "detect_intent", lambda message: handler.Intent.UNKNOWN)
    h2 = handler.MessageHandler(config={"ai": {}}, user_context={})
    assert h2.handle("hello", client_key="g") == "ai ok"
    assert fake_ai_calls == ["envkey"]

    class BrokenAI:
        def __init__(self, api_key):
            pass

        def generate_response(self, message, context):
            raise RuntimeError("fail")

    monkeypatch.setitem(
        __import__("sys").modules, "garmin_coach.ai_simple", SimpleNamespace(AICoach=BrokenAI)
    )
    h3 = handler.MessageHandler(config={"ai": {"api_key": "k"}}, user_context={"name": "Pat"})
    assert "coach" in h3.handle("hello", client_key="h")

    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.ai_simple",
        SimpleNamespace(AICoach=lambda api_key: (_ for _ in ()).throw(RuntimeError("init fail"))),
    )
    h4 = handler.MessageHandler(config={"ai": {"api_key": "k"}}, user_context={})
    h4._init_ai_coach()
    assert h4._ai_coach is None

    monkeypatch.setattr(
        handler,
        "MessageHandler",
        lambda user_context=None: SimpleNamespace(handle=lambda message: "processed"),
    )
    assert handler.process_message("hello") == "processed"


def test_mcp_server_paths(monkeypatch, capsys):
    import mcp_server.server as server

    assert server.CoachError().to_dict()["code"] == server.ERROR_INTERNAL_ERROR
    assert server.TrainingLoadError().message == "Training load data unavailable"
    assert server.ProfileNotFoundError().code == server.ERROR_PROFILE_NOT_FOUND
    assert server.GarminNotConnectedError().code == server.ERROR_GARMIN_NOT_CONNECTED
    assert server.AINotConfiguredError().code == server.ERROR_AI_NOT_CONFIGURED
    assert server.ValidationError().code == server.ERROR_VALIDATION_FAILED

    monkeypatch.setattr(
        server,
        "get_training_load_manager",
        lambda: SimpleNamespace(
            get_context=lambda: {"tsb": 5},
            calculator=SimpleNamespace(get_sessions_in_range=lambda start, end: []),
        ),
    )
    assert server.get_training_status()["status"] == "success"
    monkeypatch.setattr(
        server,
        "get_training_load_manager",
        lambda: (_ for _ in ()).throw(server.TrainingLoadError()),
    )
    assert server.get_training_status()["code"] == server.ERROR_TRAINING_LOAD
    monkeypatch.setattr(
        server, "get_training_load_manager", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    assert server.get_training_status()["message"] == "boom"

    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.activity_fetch",
        SimpleNamespace(resume_garth=lambda: True),
    )
    assert server.check_garmin_connection() is True
    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.activity_fetch",
        SimpleNamespace(resume_garth=lambda: (_ for _ in ()).throw(RuntimeError("no"))),
    )
    assert server.check_garmin_connection() is False
    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.training_load_manager",
        SimpleNamespace(TrainingLoadManager=object),
    )
    assert server.check_training_load_manager() is True

    monkeypatch.setattr(server, "check_garmin_connection", lambda: False)
    monkeypatch.setattr(server, "check_training_load_manager", lambda: True)
    assert server.handle_health({})["status"] == "degraded"

    monkeypatch.setitem(
        __import__("sys").modules, "garmin_coach.wizard", SimpleNamespace(load_config=lambda: {})
    )
    assert server.get_user_profile()["code"] == server.ERROR_PROFILE_NOT_FOUND
    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.wizard",
        SimpleNamespace(
            load_config=lambda: {
                "name": "Pat",
                "age": 30,
                "sports": ["run"],
                "fitness_level": "mid",
                "setup_complete": True,
            }
        ),
    )
    assert server.get_user_profile()["data"]["name"] == "Pat"

    daily = SimpleNamespace(
        date=SimpleNamespace(isoformat=lambda: "2026-03-29"),
        trimp=88,
        sport=SimpleNamespace(value="running"),
        duration_min=45,
        description="easy",
    )
    monkeypatch.setattr(
        server,
        "get_training_load_manager",
        lambda: SimpleNamespace(
            get_context=lambda: {"tsb": 30},
            calculator=SimpleNamespace(get_sessions_in_range=lambda start, end: [daily]),
        ),
    )
    assert server.get_recent_activities(3)["data"][0]["trimp"] == 88
    monkeypatch.setattr(
        server, "get_training_load_manager", lambda: (_ for _ in ()).throw(RuntimeError("bad"))
    )
    assert server.get_recent_activities(3)["code"] == server.ERROR_TRAINING_LOAD

    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.handler",
        SimpleNamespace(process_message=lambda message: f"handled:{message}"),
    )
    assert server.handle_natural_language("hi")["response"] == "handled:hi"
    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.handler",
        SimpleNamespace(
            process_message=lambda message: (_ for _ in ()).throw(RuntimeError("oops"))
        ),
    )
    assert server.handle_natural_language("hi")["code"] == server.ERROR_INTERNAL_ERROR

    monkeypatch.setattr(
        server,
        "get_training_load_manager",
        lambda: SimpleNamespace(get_context=lambda: {"tsb": -30}),
    )
    assert "Rest day" in server.get_training_plan()["data"]["recommended_plan"]
    monkeypatch.setattr(
        server,
        "get_training_load_manager",
        lambda: SimpleNamespace(get_context=lambda: {"tsb": -15}),
    )
    assert "Easy day" in server.get_training_plan()["data"]["recommended_plan"]
    monkeypatch.setattr(
        server,
        "get_training_load_manager",
        lambda: SimpleNamespace(get_context=lambda: {"tsb": 30}),
    )
    assert "High intensity" in server.get_training_plan()["data"]["recommended_plan"]
    monkeypatch.setattr(
        server, "get_training_load_manager", lambda: SimpleNamespace(get_context=lambda: {"tsb": 0})
    )
    assert "Steady training" in server.get_training_plan()["data"]["recommended_plan"]
    monkeypatch.setattr(
        server, "get_training_load_manager", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    assert server.get_training_plan()["code"] == server.ERROR_TRAINING_LOAD

    class FakeLimiter:
        def __init__(self, allowed=True):
            self.allowed = allowed

        def is_allowed(self, client_id):
            return self.allowed

        def get_remaining(self, client_id):
            return 0

        def get_reset_time(self, client_id):
            return 10

    monkeypatch.setattr(server, "MCP_LIMITER", FakeLimiter(False))
    assert server.handle_tool_call("health", {})["code"] == server.ERROR_RATE_LIMITED
    monkeypatch.setattr(server, "MCP_LIMITER", FakeLimiter(True))
    assert server.handle_tool_call("unknown", {})["code"] == server.ERROR_METHOD_NOT_FOUND
    monkeypatch.setattr(server, "handle_health", lambda params: {"status": "ok"})
    monkeypatch.setitem(server.TOOL_HANDLERS, "health", lambda: {"status": "ok"})
    assert server.handle_tool_call("health", {})["status"] == "ok"
    monkeypatch.setitem(server.TOOL_HANDLERS, "get_recent_activities", lambda days: {"days": days})
    assert server.handle_tool_call("get_recent_activities", {"days": 4})["days"] == 4
    monkeypatch.setitem(
        server.TOOL_HANDLERS, "handle_natural_language", lambda message: {"msg": message}
    )
    assert server.handle_tool_call("handle_natural_language", {"message": "hi"})["msg"] == "hi"

    server.send_response(1, {"ok": True})
    server.send_error(2, server.ERROR_PARSE_ERROR, "bad")
    out = capsys.readouterr().out
    assert '"result": {"ok": true}' in out
    assert '"code": -32700' in out

    monkeypatch.setattr(
        server, "send_response", lambda request_id, result: sent.append((request_id, result))
    )
    monkeypatch.setattr(
        server,
        "send_error",
        lambda request_id, code, message: errors.append((request_id, code, message)),
    )
    sent = []
    errors = []
    lines = iter(
        [
            json.dumps({"method": "initialize", "id": 1, "params": {}}) + "\n",
            json.dumps({"method": "tools/list", "id": 2, "params": {}}) + "\n",
            json.dumps(
                {"method": "tools/call", "id": 3, "params": {"name": "health", "arguments": {}}}
            )
            + "\n",
            json.dumps({"method": "health", "id": 4, "params": {}}) + "\n",
            json.dumps({"method": "notifications/initialized", "id": 5, "params": {}}) + "\n",
            "not-json\n",
            "",
        ]
    )
    monkeypatch.setattr(server.sys, "stdin", SimpleNamespace(readline=lambda: next(lines)))
    monkeypatch.setattr(server.sys, "argv", ["mcp_server.server"])
    monkeypatch.setattr(server, "handle_tool_call", lambda name, arguments: {"called": name})
    monkeypatch.setattr(server, "handle_health", lambda params: {"status": "healthy"})
    server.main()
    assert sent[0][0] == 1
    assert sent[1][1]["tools"] == server.TOOLS
    assert sent[2][1]["content"][0]["text"] == json.dumps({"called": "health"}, ensure_ascii=False)
    assert sent[3][1]["status"] == "healthy"
    assert errors[-1][1] == server.ERROR_PARSE_ERROR

    monkeypatch.setattr(server.sys, "argv", ["mcp_server.server", "--version"])
    server.main()
    assert "garmin-personal-coach-mcp" in capsys.readouterr().out

    sent = []
    errors = []
    monkeypatch.setattr(
        server, "send_response", lambda request_id, result: sent.append((request_id, result))
    )
    monkeypatch.setattr(
        server,
        "send_error",
        lambda request_id, code, message: errors.append((request_id, code, message)),
    )
    lines = iter(
        [
            json.dumps(
                {"method": "tools/call", "id": 7, "params": {"name": "health", "arguments": {}}}
            )
            + "\n",
            "",
        ]
    )
    monkeypatch.setattr(server.sys, "stdin", SimpleNamespace(readline=lambda: next(lines)))
    monkeypatch.setattr(server.sys, "argv", ["mcp_server.server"])
    monkeypatch.setattr(
        server,
        "handle_tool_call",
        lambda name, arguments: (_ for _ in ()).throw(RuntimeError("tool boom")),
    )
    server.main()
    assert errors[-1][1] == server.ERROR_INTERNAL_ERROR
