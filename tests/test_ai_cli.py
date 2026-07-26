"""Zero-config LLM via local AI CLIs (claude/gemini/codex)."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

from garmin_coach import ai_cli
from garmin_coach.ai_simple import AICoach


def _which_factory(available: dict[str, str]):
    return lambda name: available.get(name)


def test_detect_prefers_claude_then_gemini_then_codex(monkeypatch):
    monkeypatch.delenv("GARMIN_COACH_AI_CLI", raising=False)
    monkeypatch.setattr(
        ai_cli.shutil, "which", _which_factory({"gemini": "/bin/gemini", "codex": "/bin/codex"})
    )
    assert ai_cli.detect_cli() == ("gemini", "/bin/gemini")
    monkeypatch.setattr(ai_cli.shutil, "which", _which_factory({"codex": "/bin/codex"}))
    assert ai_cli.detect_cli() == ("codex", "/bin/codex")
    monkeypatch.setattr(ai_cli.shutil, "which", _which_factory({}))
    assert ai_cli.detect_cli() is None


def test_detect_env_override_wins(monkeypatch):
    monkeypatch.setenv("GARMIN_COACH_AI_CLI", "codex")
    monkeypatch.setattr(
        ai_cli.shutil,
        "which",
        _which_factory({"claude": "/bin/claude", "codex": "/bin/codex"}),
    )
    assert ai_cli.detect_cli() == ("codex", "/bin/codex")


def test_detect_preferred_argument_beats_env(monkeypatch):
    monkeypatch.setenv("GARMIN_COACH_AI_CLI", "codex")
    monkeypatch.setattr(
        ai_cli.shutil,
        "which",
        _which_factory({"claude": "/bin/claude", "codex": "/bin/codex"}),
    )
    assert ai_cli.detect_cli(preferred="claude") == ("claude", "/bin/claude")


def test_generate_builds_headless_command(monkeypatch):
    monkeypatch.delenv("GARMIN_COACH_AI_CLI", raising=False)
    monkeypatch.setattr(ai_cli.shutil, "which", _which_factory({"claude": "/bin/claude"}))
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return SimpleNamespace(returncode=0, stdout="coaching text\n", stderr="")

    monkeypatch.setattr(ai_cli.subprocess, "run", fake_run)
    coach = ai_cli.CLICoach()
    assert coach.generate("hello") == "coaching text"
    assert captured["args"] == [
        "/bin/claude",
        "-p",
        "hello",
        "--output-format",
        "text",
        "--safe-mode",
        "--allowedTools",
        "",
    ]


def test_generate_handles_failure_and_timeout(monkeypatch):
    monkeypatch.delenv("GARMIN_COACH_AI_CLI", raising=False)
    monkeypatch.setattr(ai_cli.shutil, "which", _which_factory({"claude": "/bin/claude"}))

    monkeypatch.setattr(
        ai_cli.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    assert ai_cli.CLICoach().generate("x") is None

    def raise_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1)

    monkeypatch.setattr(ai_cli.subprocess, "run", raise_timeout)
    assert ai_cli.CLICoach().generate("x") is None


def test_aicoach_detects_cli_without_api_keys(monkeypatch):
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("GARMIN_COACH_AI_CLI", raising=False)
    monkeypatch.setattr(ai_cli.shutil, "which", _which_factory({"claude": "/bin/claude"}))
    coach = AICoach()
    assert coach.provider == "cli"

    monkeypatch.setattr(
        ai_cli.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="ride easy today", stderr=""),
    )
    assert coach.generate_response("how should I train?", {"tsb": -5}) == "ride easy today"


def test_aicoach_api_key_still_wins_over_cli(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(ai_cli.shutil, "which", _which_factory({"claude": "/bin/claude"}))
    assert AICoach().provider == "anthropic"


# -- trust: staleness disclosure + language pinning ---------------------------


def test_stale_load_is_labelled_and_flagged_to_the_model():
    """Live bug: the coach cited April data as "my current data" in July."""
    coach = AICoach(api_key="x", provider="anthropic")
    prompt = coach._build_system_prompt(
        {"ctl": 50, "atl": 40, "tsb": 2.4, "date": "2026-04-09", "load_age_days": 107}
    )
    assert "107 DAYS OLD" in prompt
    assert "2026-04-09" in prompt
    assert "never present it as today's condition" in prompt
    assert "Current training metrics" not in prompt


def test_fresh_load_has_no_staleness_warning():
    coach = AICoach(api_key="x", provider="anthropic")
    prompt = coach._build_system_prompt(
        {"ctl": 50, "atl": 40, "tsb": 2.4, "date": "2026-07-26", "load_age_days": 0}
    )
    assert "Current training metrics (as of 2026-07-26)" in prompt
    assert "DAYS OLD" not in prompt


def test_language_rule_is_always_present():
    """User asked in Korean and got English back; nothing pinned the language."""
    coach = AICoach(api_key="x", provider="anthropic")
    for ctx in ({}, {"load_age_days": 107, "date": "2026-04-09"}):
        assert "same language the user writes in" in coach._build_system_prompt(ctx)


def test_stale_load_suppresses_canned_tsb_hint():
    coach = AICoach(api_key="x", provider="anthropic")
    stale = coach._build_user_prompt("how do I feel?", {"tsb": -30, "load_age_days": 107})
    assert "very fatigued" not in stale
    fresh = coach._build_user_prompt("how do I feel?", {"tsb": -30, "load_age_days": 0})
    assert "very fatigued" in fresh


def test_handler_context_carries_load_age(monkeypatch):
    from datetime import date, timedelta

    import garmin_coach.handler as handler

    six_days_ago = (date.today() - timedelta(days=6)).isoformat()
    monkeypatch.setattr(
        handler,
        "get_training_load_manager",
        lambda: SimpleNamespace(
            get_context=lambda: {
                "ctl": 1,
                "atl": 2,
                "tsb": 3,
                # snapshot date is always ~today; only last_data_date shows age
                "date": date.today().isoformat(),
                "last_data_date": six_days_ago,
            }
        ),
    )
    assert handler._get_real_context()["load_age_days"] == 6


def test_handler_context_tolerates_missing_or_bad_date(monkeypatch):
    import garmin_coach.handler as handler

    for bad in (None, "not-a-date"):
        monkeypatch.setattr(
            handler,
            "get_training_load_manager",
            lambda bad=bad: SimpleNamespace(
                get_context=lambda: {"ctl": 1, "atl": 2, "tsb": 3, "last_data_date": bad}
            ),
        )
        assert handler._get_real_context()["load_age_days"] is None
