import json
import runpy
import types
from datetime import datetime
from types import SimpleNamespace

import pytest


def test_i18n_translation_and_detection():
    from garmin_coach.i18n import Locale, detect_locale, get_i18n

    assert detect_locale("안녕") == Locale.KO
    assert detect_locale("你好") == Locale.ZH
    assert detect_locale("hello") == Locale.EN
    assert "Hi Bob" in get_i18n(Locale.EN).t("start.welcome").format(name="Bob")


def test_rate_limiter_window_and_reset(monkeypatch):
    from garmin_coach.rate_limit import RateLimiter

    now = {"value": 1000.0}
    monkeypatch.setattr("garmin_coach.rate_limit.time.time", lambda: now["value"])

    limiter = RateLimiter(max_requests=2, window_seconds=10)
    assert limiter.is_allowed("u") is True
    assert limiter.is_allowed("u") is True
    assert limiter.is_allowed("u") is False
    assert limiter.get_remaining("u") == 0
    assert limiter.get_reset_time("u") == pytest.approx(10.0)

    now["value"] += 11
    assert limiter.is_allowed("u") is True
    limiter.reset("u")
    assert limiter.get_remaining("u") == 2


def test_logging_config_exports():
    from garmin_coach import logging_config

    logger = logging_config.get_logger("tests")
    logging_config.log_info("hello", scope="tests")
    logging_config.log_warning("warn")
    logging_config.log_error("error")
    logging_config.log_debug("debug")

    assert logger.name.startswith("garmin_coach")
    assert logging_config.std_logger is logging_config.logger


def test_update_check_uses_cache_and_network(monkeypatch, tmp_path):
    import garmin_coach.update_check as update_check

    cache_file = tmp_path / ".update_cache"
    monkeypatch.setattr(update_check, "CACHE_FILE", str(cache_file))

    response = SimpleNamespace(
        status_code=200,
        json=lambda: {"tag_name": "v0.2.0", "html_url": "https://example", "body": "notes"},
    )
    monkeypatch.setattr(
        update_check, "requests", SimpleNamespace(get=lambda *args, **kwargs: response)
    )

    fresh = update_check.check_for_updates(force=True)
    assert fresh.is_update_available is True
    assert fresh.latest == "0.2.0"

    cached = update_check.check_for_updates(force=False)
    assert cached.latest == "v0.2.0"
    assert cache_file.exists()


def test_update_check_without_requests(monkeypatch):
    import garmin_coach.update_check as update_check

    monkeypatch.setattr(update_check, "requests", None)
    info = update_check.check_for_updates(force=True)
    assert info.is_update_available is False
    assert update_check.get_update_message(info) is None
    assert update_check._compare_versions("1.0.0", "1.0.1") == -1


def test_training_load_manager_load_save_and_context(monkeypatch, tmp_path):
    import garmin_coach.training_load_manager as tlm

    config_dir = tmp_path / "config"
    load_file = config_dir / "training_load.json"
    profile_file = config_dir / "config.yaml"
    config_dir.mkdir()
    profile_file.write_text("sex: female\n")

    monkeypatch.setattr(tlm, "DATA_DIR", str(config_dir))
    monkeypatch.setattr(tlm, "LOAD_FILE", str(load_file))
    monkeypatch.setattr(tlm, "PROFILE_FILE", str(profile_file))
    tlm.TrainingLoadManager.reset()

    manager = tlm.TrainingLoadManager.get_instance()
    manager.add_activity(
        datetime.now().date(), trimp=50, sport="running", duration_min=30, description="easy"
    )
    context = manager.get_context()

    assert context["date"]
    assert load_file.exists()
    assert manager.calculator.session_calculator.metabolic_factor == 1.3

    tlm.TrainingLoadManager.reset()
    manager2 = tlm.get_training_load_manager()
    assert manager2.get_context()["date"]


def test_scheduler_dispatch_and_install(monkeypatch):
    import garmin_coach.scheduler as scheduler

    ran = []
    schedule = SimpleNamespace(
        morning_checkin={"enabled": True, "time": "06:00"},
        final_check={"enabled": True, "time": "06:30"},
        evening_checkin={"enabled": False, "time": "22:00"},
        weekly_review={
            "enabled": True,
            "day": datetime.now().strftime("%A").lower(),
            "time": "21:00",
        },
    )
    profile = SimpleNamespace(schedule=schedule)
    monkeypatch.setattr(scheduler, "_register_signal_handlers", lambda: None)
    monkeypatch.setattr(scheduler, "resume_garth", lambda: False)
    monkeypatch.setattr(scheduler, "should_run_now", lambda *args, **kwargs: True)
    monkeypatch.setattr(scheduler, "run_job", lambda name: ran.append(name) or 0)
    monkeypatch.setattr(scheduler.ProfileManager, "load", lambda self: profile)
    scheduler._shutdown_requested = False

    scheduler.dispatch_scheduled()
    cron = scheduler.install_cron()

    assert ran == ["morning_checkin", "final_check", "weekly_review"]
    assert "scheduler.py --dispatch" in cron


def test_ai_simple_openai_and_anthropic(monkeypatch):
    from garmin_coach.ai_simple import AICoach

    class FakeOpenAIClient:
        def __init__(self, api_key):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="openai ok"))]
                    )
                )
            )

    class FakeAnthropicClient:
        def __init__(self, api_key):
            self.messages = SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    content=[SimpleNamespace(text="anthropic ok")]
                )
            )

    monkeypatch.setitem(
        __import__("sys").modules, "openai", SimpleNamespace(OpenAI=FakeOpenAIClient)
    )
    monkeypatch.setitem(
        __import__("sys").modules, "anthropic", SimpleNamespace(Anthropic=FakeAnthropicClient)
    )

    openai_coach = AICoach(api_key="x", provider="openai", model="gpt-4o-mini")
    assert openai_coach.generate_response("hey", {"tsb": 5, "ctl": 10, "atl": 5}) == "openai ok"

    anthropic_coach = AICoach(api_key="x", provider="anthropic", model="claude-sonnet")
    assert anthropic_coach.model == "claude-sonnet-4-20250514"
    assert (
        anthropic_coach.generate_response("hey", {"tsb": -20, "ctl": 10, "atl": 15})
        == "anthropic ok"
    )


def test_handler_templates_and_main_entry(monkeypatch, capsys):
    from garmin_coach.handler.templates import ResponseTemplate, get_form_description

    template = ResponseTemplate("analytical")
    rendered = template.get("status", tsb=-20, ctl=55, atl=70)
    fallback = template.get("missing_key", name="Pat")

    assert "Training Stress Balance" in rendered
    assert get_form_description(30).startswith("You're fresh")
    assert fallback

    monkeypatch.setattr(
        "garmin_coach.handler.process_message", lambda message: f"processed:{message}"
    )
    monkeypatch.setattr("sys.argv", ["handler", "--message", "hello"])
    runpy.run_module("garmin_coach.handler.__main__", run_name="__main__")
    assert "processed:hello" in capsys.readouterr().out


def test_mcp_server_main_entry(monkeypatch):
    import asyncio
    import mcp_server.__main__ as mcp_main

    captured = {}

    class FakeServer:
        def __init__(self, name):
            captured["name"] = name

        def list_tools(self):
            def decorator(fn):
                captured["list_tools"] = fn
                return fn

            return decorator

        def call_tool(self):
            def decorator(fn):
                captured["call_tool"] = fn
                return fn

            return decorator

        def create_initialization_options(self):
            return {"ok": True}

        async def run(self, read_stream, write_stream, options):
            captured["run"] = (read_stream, write_stream, options)

    class FakeStdio:
        async def __aenter__(self):
            return ("read", "write")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(mcp_main, "Server", FakeServer)
    monkeypatch.setattr(mcp_main, "stdio_server", lambda: FakeStdio())
    monkeypatch.setattr(
        mcp_main,
        "handle_tool_call",
        lambda name, arguments: {"name": name, "arguments": arguments},
    )

    asyncio.run(mcp_main.main())

    assert captured["name"] == "garmin-personal-coach"
    assert captured["run"] == ("read", "write", {"ok": True})


def test_mcp_entrypoint_version_and_run(monkeypatch, capsys):
    import mcp_server.entrypoint as entry

    called = []

    async def fake_async_main():
        called.append("ran")

    monkeypatch.setattr(entry.sys, "argv", ["garmin-coach-mcp", "--version"])
    assert entry.main() == 0
    assert "garmin-coach-mcp" in capsys.readouterr().out

    monkeypatch.setitem(
        __import__("sys").modules,
        "mcp_server.__main__",
        SimpleNamespace(main=fake_async_main),
    )
    monkeypatch.setattr(entry.sys, "argv", ["garmin-coach-mcp"])
    assert entry.main() == 0
    assert called == ["ran"]


def test_cli_strava_commands(monkeypatch, capsys):
    import garmin_coach.cli as cli

    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.wizard.oauth",
        SimpleNamespace(
            setup_strava_oauth=lambda: True,
            check_oauth_status=lambda: {"garmin": True, "strava": False},
        ),
    )

    assert cli._run_command(["connect-strava"]) == 0
    assert cli._run_command(["oauth-status"]) == 0
    out = capsys.readouterr().out
    assert "garmin: connected" in out
    assert "strava: not connected" in out


def test_cli_strava_sync_command(monkeypatch, capsys):
    import garmin_coach.cli as cli

    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.integrations.strava",
        SimpleNamespace(
            sync_strava_training_load=lambda days=30, dry_run=False: {
                "days": days,
                "dry_run": dry_run,
                "added": 1,
            }
        ),
    )

    assert cli._run_command(["strava-sync", "--days", "14", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "'days': 14" in out
    assert "'dry_run': True" in out


def test_cli_main_accepts_subcommand_flags(monkeypatch, capsys):
    import garmin_coach.cli as cli

    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.integrations.strava",
        SimpleNamespace(
            sync_strava_training_load=lambda days=30, dry_run=False: {
                "days": days,
                "dry_run": dry_run,
            }
        ),
    )
    monkeypatch.setattr(
        cli.sys, "argv", ["garmin-coach", "strava-sync", "--days", "5", "--dry-run"]
    )

    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "'days': 5" in out
    assert "'dry_run': True" in out


def test_cli_strava_sync_handles_runtime_error(monkeypatch, capsys):
    import garmin_coach.cli as cli

    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.integrations.strava",
        SimpleNamespace(
            sync_strava_training_load=lambda days=30, dry_run=False: (_ for _ in ()).throw(
                RuntimeError(
                    "Strava is not authenticated. Run 'garmin-coach connect-strava' first."
                )
            )
        ),
    )

    assert cli._run_command(["strava-sync"]) == 1
    assert "Strava is not authenticated" in capsys.readouterr().err
