from __future__ import annotations

import pytest

from garmin_coach import ai_cli
from garmin_coach.interfaces.imessage import applescript


@pytest.fixture(autouse=True)
def no_real_ai_cli(monkeypatch):
    """Never let tests shell out to a real local AI CLI (claude/gemini/codex).

    Zero-config CLI detection would otherwise activate on any dev machine with
    an AI CLI installed, making tests slow, non-deterministic, and billable.
    Tests that exercise detection re-patch ai_cli.shutil.which themselves.
    """
    monkeypatch.setattr(ai_cli.shutil, "which", lambda name: None)
    monkeypatch.delenv("GARMIN_COACH_AI_CLI", raising=False)


@pytest.fixture(autouse=True)
def no_real_osascript(monkeypatch):
    """Never let tests invoke real osascript / Messages.app.

    A wiring bug once let IMessagePoller call the module-level send_imessage
    directly instead of its injected sender, so tests silently fired real
    osascript calls against Messages.app (each blocking ~15-35s waiting on a
    bogus test phone number). This is the backstop: any test that forgets to
    inject a fake sender fails loudly and fast instead of touching the real
    app. Tests that genuinely exercise send_imessage's subprocess plumbing
    pass their own `runner=` and are unaffected.
    """

    def _refuse(*args, **kwargs):
        raise AssertionError(
            "A test tried to invoke the real osascript/subprocess.run path. "
            "Inject a fake sender/runner instead of relying on the default."
        )

    monkeypatch.setattr(applescript.subprocess, "run", _refuse)
