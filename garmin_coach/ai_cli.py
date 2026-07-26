"""Zero-config LLM via locally installed AI CLIs.

If the user already runs Claude Code / Codex / Gemini CLI, those tools carry
their own logged-in (subscription) auth. Instead of asking for an API key we
detect the binary and pipe prompts through its headless mode:

    claude -p "<prompt>" --output-format text
    gemini -p "<prompt>"
    codex exec "<prompt>"

Priority: GARMIN_COACH_AI_CLI env var > config > detection order below.
This is the lowest-friction provider; API keys (ai_simple) still win when set.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional

from garmin_coach.logging_config import log_warning

CLI_TIMEOUT_SECONDS = 120

# Detection order: plain-text output quality first.
CLI_COMMANDS: dict[str, list[str]] = {
    # --safe-mode: disables CLAUDE.md/hooks/skills/plugins/MCP so the user's
    # own dev config never bleeds into a coaching reply, while still using
    # normal OAuth/keychain auth (unlike --bare, which requires an API key
    # and would defeat the point of this zero-config path).
    # --allowedTools "": belt-and-suspenders — no tool call should ever fire
    # for a plain coaching prompt, but this guarantees it can't block on a
    # permission prompt in a non-interactive subprocess.
    "claude": [
        "-p",
        "{prompt}",
        "--output-format",
        "text",
        "--safe-mode",
        "--allowedTools",
        "",
    ],
    "gemini": ["-p", "{prompt}"],
    # --sandbox read-only + --ask-for-approval never: guarantees the call
    # can't hang waiting for an approval prompt that will never come.
    "codex": ["exec", "--sandbox", "read-only", "--ask-for-approval", "never", "{prompt}"],
}


def detect_cli(preferred: Optional[str] = None) -> Optional[tuple[str, str]]:
    """Return (name, executable path) of the first usable AI CLI, or None."""
    env_choice = os.getenv("GARMIN_COACH_AI_CLI")
    order = list(CLI_COMMANDS)
    # Applied last wins the front slot: env var first, explicit preferred last.
    for choice in (env_choice, preferred):
        if choice and choice in order:
            order.remove(choice)
            order.insert(0, choice)
    for name in order:
        path = shutil.which(name)
        if path:
            return name, path
    return None


class CLICoach:
    """Generate coaching text through a local AI CLI subprocess."""

    def __init__(self, preferred: Optional[str] = None):
        self._detected = detect_cli(preferred)

    @property
    def available(self) -> bool:
        return self._detected is not None

    @property
    def name(self) -> Optional[str]:
        return self._detected[0] if self._detected else None

    def generate(self, prompt: str) -> Optional[str]:
        if self._detected is None:
            return None
        name, path = self._detected
        args = [path] + [
            part.format(prompt=prompt) if "{prompt}" in part else part
            for part in CLI_COMMANDS[name]
        ]
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=CLI_TIMEOUT_SECONDS,
                # Never inherit the repo cwd: coding CLIs may scan the project.
                cwd=os.path.expanduser("~"),
            )
        except Exception as exc:
            log_warning(f"AI CLI '{name}' failed: {exc}")
            return None
        if result.returncode != 0:
            log_warning(
                f"AI CLI '{name}' exited {result.returncode}: {result.stderr.strip()[:200]}"
            )
            return None
        output = result.stdout.strip()
        return output or None


__all__ = ["CLI_COMMANDS", "CLI_TIMEOUT_SECONDS", "CLICoach", "detect_cli"]
