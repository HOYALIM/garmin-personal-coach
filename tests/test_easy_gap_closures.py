import runpy
from types import SimpleNamespace


def test_easy_gap_closures(monkeypatch, capsys, tmp_path):
    import garmin_coach.activity_fetch as af
    import garmin_coach.ai_coach as ai
    import garmin_coach.garmin_writeback as writeback
    import garmin_coach.training_log as training_log
    import garmin_coach.update_check as update_check
    import garmin_coach.weekly_review as weekly
    import garmin_coach.wizard.validation as validation
    import garmin_coach.scheduler as scheduler
    import mcp_server.server as mcp_server
    from garmin_coach.profile_manager import AICoachConfig, ProfileData, UserProfile

    monkeypatch.setattr(af, "_execute_garth_call", lambda operation, fn: True)
    assert af.resume_garth() is True
    assert af.extract_sleep_hours([]) is None

    monkeypatch.setattr(ai.ProfileManager, "load", lambda self: None)
    engine = ai.AICoachEngine(config=AICoachConfig(enabled=False))
    ctx = ai.CoachContext(
        date="2026-03-29", user_profile=UserProfile(profile=ProfileData(name="Pat"))
    )
    assert "good shape" in engine._fallback_text("q", ctx)
    assert "All metrics look good" in engine._rule_advice(ctx)

    monkeypatch.setattr(writeback, "GARMIN_EMAIL", "user")
    monkeypatch.setattr(writeback, "GARMIN_PASSWORD", "pass")
    monkeypatch.setitem(__import__("sys").modules, "garminconnect", SimpleNamespace())
    assert writeback._garminconnect_available() is True

    monkeypatch.setattr("sys.argv", ["training_log"])
    runpy.run_module("garmin_coach.training_log", run_name="__main__")
    assert "Saved:" in capsys.readouterr().out

    monkeypatch.setattr(
        update_check,
        "requests",
        SimpleNamespace(get=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))),
    )
    assert update_check.check_for_updates(force=True).is_update_available is False
    assert update_check._compare_versions("1.0.0", "1.0.0") == 0

    monkeypatch.setattr(
        weekly, "run_weekly", lambda target=None: capsys.writeouterr if False else None
    )
    monkeypatch.setattr("sys.argv", ["weekly_review"])
    weekly.main()
    monkeypatch.setattr("sys.argv", ["weekly_review"])
    runpy.run_module("garmin_coach.weekly_review", run_name="__main__")
    assert "No profile found" in capsys.readouterr().out

    ok, errors = validation.validate_profile({"name": "", "sports": ["running"]})
    assert ok is False and any("name:" in e for e in errors)

    monkeypatch.setattr(scheduler.signal, "signal", lambda sig, fn: None)
    scheduler._shutdown_requested = False
    scheduler._register_signal_handlers()
    scheduler._request_shutdown(15, None)
    assert scheduler._is_shutdown_requested() is True
    monkeypatch.setattr("sys.argv", ["scheduler"])
    runpy.run_module("garmin_coach.scheduler", run_name="__main__")
    assert "Usage:" in capsys.readouterr().out

    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.training_load_manager",
        SimpleNamespace(get_training_load_manager=lambda: None),
    )
    assert mcp_server.check_training_load_manager() is False
    monkeypatch.setitem(
        __import__("sys").modules,
        "garmin_coach.wizard",
        SimpleNamespace(load_config=lambda: (_ for _ in ()).throw(RuntimeError("bad"))),
    )
    assert mcp_server.get_user_profile()["code"] == mcp_server.ERROR_PROFILE_NOT_FOUND
    monkeypatch.setattr("sys.argv", ["mcp_server.server", "--version"])
    runpy.run_module("mcp_server.server", run_name="__main__")
    assert "garmin-personal-coach-mcp" in capsys.readouterr().out
