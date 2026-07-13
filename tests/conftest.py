from __future__ import annotations

import pytest

from garmin_coach import ai_cli


@pytest.fixture(autouse=True)
def no_real_ai_cli(monkeypatch):
    """Never let tests shell out to a real local AI CLI (claude/gemini/codex).

    Zero-config CLI detection would otherwise activate on any dev machine with
    an AI CLI installed, making tests slow, non-deterministic, and billable.
    Tests that exercise detection re-patch ai_cli.shutil.which themselves.
    """
    monkeypatch.setattr(ai_cli.shutil, "which", lambda name: None)
    monkeypatch.delenv("GARMIN_COACH_AI_CLI", raising=False)
