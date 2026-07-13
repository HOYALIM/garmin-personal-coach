"""iMessage polling loop: chat.db → coaching reply → AppleScript send.

Wires the channel-agnostic pieces together:
- chat_db.ChatDBReader for inbound messages (per §chat_db.py docstring, needs
  Full Disk Access)
- IMessageAdapter for any flow currently awaiting this handle's input
- garmin_coach.handler.MessageHandler (same free-text engine CLI/Telegram/MCP
  already use) for everything else, so "text anything, get coached" works
  immediately without a bespoke NL layer per channel

NOT wired yet: the full conversational onboarding flow (OnboardingFlow +
"connect your Garmin/Strava" Q&A). That flow's `onboarding_service` today
lives as `_UserProfileService`, a private class inside the legacy
`telegram_bot.py` — reusing it here as-is would import across a channel
boundary the project's own architecture rule forbids (flows/ must not
depend on any one interface's internals). Extracting it into a shared
`garmin_coach/services/` module is the correct next step (tracked in
work-orders-5stream.md §S-F) rather than a quick coupling-violating import.
Until then, a brand-new contact gets a one-time "run `garmin-coach setup`
first" nudge instead of an in-chat onboarding flow.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from garmin_coach.interfaces.imessage.adapter import IMessageAdapter
from garmin_coach.interfaces.imessage.applescript import send_imessage
from garmin_coach.interfaces.imessage.chat_db import ChatDBPermissionError, ChatDBReader
from garmin_coach.logging_config import log_error, log_info, log_warning

STATE_DIR = os.path.expanduser("~/.config/garmin_coach/integrations")
STATE_FILE = os.path.join(STATE_DIR, "imessage_state.json")
DEFAULT_POLL_INTERVAL_SECONDS = 5
FIRST_CONTACT_NUDGE = (
    "안녕하세요! 아직 이 번호로 온보딩된 프로필이 없어요.\n"
    "터미널에서 `garmin-coach setup`을 먼저 실행해 Garmin 계정을 연결해주세요.\n"
    "(대화형 온보딩은 곧 지원 예정입니다.)"
)


def _load_state() -> dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {"last_rowid": 0, "known_handles": []}
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {
                    "last_rowid": int(data.get("last_rowid", 0)),
                    "known_handles": list(data.get("known_handles", [])),
                }
    except Exception as exc:
        log_warning(f"Failed to read iMessage poller state: {exc}")
    return {"last_rowid": 0, "known_handles": []}


def _save_state(state: dict[str, Any]) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.chmod(STATE_FILE, 0o600)


class IMessagePoller:
    def __init__(
        self,
        reader: ChatDBReader | None = None,
        adapter: IMessageAdapter | None = None,
        message_handler: Any = None,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        sender: Any = None,
    ):
        self.reader = reader or ChatDBReader()
        # A single sender shared with the adapter — every outbound path
        # (adapter flows, onboarding nudge, coaching replies) must go through
        # this one callable so tests can fully fake it out, and so an
        # explicitly-passed adapter's sender can never silently diverge from
        # this class's own. Calling the module-level send_imessage directly
        # anywhere in this class is a bug: it bypasses injection and fires
        # real osascript/Messages.app.
        if adapter is not None:
            self.adapter = adapter
            self.sender = sender or adapter.sender
        else:
            self.sender = sender or send_imessage
            self.adapter = IMessageAdapter(sender=self.sender)
        if message_handler is None:
            from garmin_coach.handler import MessageHandler

            message_handler = MessageHandler()
        self.message_handler = message_handler
        self.poll_interval_seconds = poll_interval_seconds
        self.state = _load_state()

    def bootstrap_if_first_run(self) -> None:
        """On a brand-new state file, start from the current high-water mark
        instead of replaying the user's entire Messages history."""
        if self.state.get("last_rowid", 0) == 0:
            self.state["last_rowid"] = self.reader.max_rowid()
            _save_state(self.state)

    def poll_once(self) -> int:
        """Process one batch of new messages. Returns how many were handled."""
        messages = self.reader.poll_new_messages(self.state["last_rowid"])
        for msg in messages:
            self._handle_message(msg.handle, msg.text or "")
            self.state["last_rowid"] = msg.rowid
        if messages:
            _save_state(self.state)
        return len(messages)

    def _handle_message(self, handle: str, text: str) -> None:
        if self.adapter.deliver_input(handle, text):
            return  # an active flow was awaiting this reply; it takes it from here

        known = set(self.state.get("known_handles", []))
        if handle not in known:
            known.add(handle)
            self.state["known_handles"] = sorted(known)
            self.sender(handle, FIRST_CONTACT_NUDGE)
            return

        try:
            reply = self.message_handler.handle(text, client_key=handle)
        except Exception as exc:
            log_error(f"iMessage handler failed for {handle}", exc=exc)
            reply = "죄송해요, 잠시 문제가 생겼어요. 다시 시도해주세요."
        self.sender(handle, reply)

    def run_forever(self) -> None:
        try:
            self.reader.max_rowid()
        except ChatDBPermissionError as exc:
            log_error(str(exc))
            raise
        self.bootstrap_if_first_run()
        log_info(f"iMessage poller started (interval={self.poll_interval_seconds}s)")
        while True:
            try:
                self.poll_once()
            except ChatDBPermissionError:
                raise
            except Exception as exc:
                log_error("iMessage poll iteration failed", exc=exc)
            time.sleep(self.poll_interval_seconds)


def main() -> int:
    poller = IMessagePoller()
    try:
        poller.run_forever()
    except ChatDBPermissionError as exc:
        print(f"\n{exc}\n")
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


__all__ = ["IMessagePoller", "main"]
