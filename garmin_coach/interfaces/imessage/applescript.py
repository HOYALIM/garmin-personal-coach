"""Send outbound iMessages via AppleScript (the only send path — no API)."""

from __future__ import annotations

import subprocess
from typing import Callable

APPLESCRIPT_TIMEOUT_SECONDS = 15
# iMessage has no hard length limit like Telegram's 4096, but very long single
# bubbles are hard to read and slower to render; split for readability.
_TARGET_CHUNK_LEN = 1000


def escape_applescript_string(text: str) -> str:
    """Escape a string for safe interpolation into a double-quoted AppleScript literal.

    AppleScript string literals only need backslash and double-quote escaped;
    unlike POSIX shell, there is no separate injection surface for `;`, `` ` ``,
    `$`, etc. because the string never re-enters a shell parser — it's passed
    as a single -e script argument to osascript via subprocess (no shell=True).
    """
    return text.replace("\\", "\\\\").replace('"', '\\"')


def split_for_imessage(text: str) -> list[str]:
    if len(text) <= _TARGET_CHUNK_LEN:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= _TARGET_CHUNK_LEN:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, _TARGET_CHUNK_LEN)
        if split_at <= 0:
            split_at = _TARGET_CHUNK_LEN
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
    return chunks


def _build_script(handle: str, text: str) -> str:
    safe_handle = escape_applescript_string(handle)
    safe_text = escape_applescript_string(text)
    return (
        'tell application "Messages"\n'
        "  set targetService to 1st account whose service type = iMessage\n"
        f'  set targetBuddy to participant "{safe_handle}" of targetService\n'
        f'  send "{safe_text}" to targetBuddy\n'
        "end tell"
    )


def send_imessage(
    handle: str,
    text: str,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> bool:
    """Send `text` to `handle` (phone number or email). Returns success.

    One osascript call per chunk — a failed later chunk doesn't retract
    earlier ones (AppleScript has no transaction semantics here), so this
    can partially deliver a long message; callers should keep messages short.

    `runner` defaults to `None` and resolves to `subprocess.run` *inside* the
    function body rather than as a bound default-argument value — a default
    of `subprocess.run` would capture that function object once at import
    time, permanently immune to `monkeypatch.setattr(applescript.subprocess,
    "run", ...)` in tests (a real bug this project hit: tests silently fired
    real osascript calls against Messages.app because of exactly this).
    """
    run = runner or subprocess.run
    ok = True
    for chunk in split_for_imessage(text):
        script = _build_script(handle, chunk)
        try:
            result = run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=APPLESCRIPT_TIMEOUT_SECONDS,
            )
        except Exception:
            ok = False
            continue
        if result.returncode != 0:
            ok = False
    return ok


__all__ = [
    "APPLESCRIPT_TIMEOUT_SECONDS",
    "escape_applescript_string",
    "send_imessage",
    "split_for_imessage",
]
