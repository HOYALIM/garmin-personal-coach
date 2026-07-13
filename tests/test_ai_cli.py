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
