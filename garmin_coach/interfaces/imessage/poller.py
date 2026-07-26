"""iMessage polling loop: chat.db → onboarding/coaching → AppleScript send.

Wires the channel-agnostic pieces together:
- chat_db.ChatDBReader for inbound messages (per §chat_db.py docstring, needs
  Full Disk Access)
- IMessageAdapter for any flow currently awaiting this handle's input
- flows.onboarding.OnboardingFlow + services.user_profile.UserProfileService
  for first-contact conversational onboarding ("text this number, answer a
  few questions, Garmin connected") — the same flow Telegram runs, reused
  through CoachingPort with zero flow-layer changes
- garmin_coach.handler.MessageHandler (same free-text engine CLI/Telegram/MCP
  already use) for everything else, so "text anything, get coached" works
  without a bespoke NL layer per channel

Message routing order per inbound text:
1. an in-flight flow awaiting this handle's reply (adapter.deliver_input)
2. first contact ever → spawn OnboardingFlow as a background asyncio task
3. otherwise → MessageHandler free-text coaching

Onboarding requires the async runtime (`run_forever`); if poll_once is
driven synchronously with no event loop (tests, one-shot scripts), first
contact falls back to a "run garmin-coach setup" nudge instead.
"""

from __future__ import annotations

import asyncio
import json
import os
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
    "터미널에서 `garmin-coach setup`을 먼저 실행해 Garmin 계정을 연결해주세요."
)
ONBOARDING_FAILED_MESSAGE = (
    "온보딩 중 문제가 생겼어요. '시작'이라고 보내시면 이어서 다시 진행할게요."
)
RESTART_KEYWORDS = {"/start", "start", "시작", "온보딩", "다시"}


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


def _build_default_onboarding(adapter: IMessageAdapter) -> Any:
    try:
        from garmin_coach.flows.onboarding import OnboardingFlow
        from garmin_coach.services.user_profile import UserProfileService

        return OnboardingFlow(adapter, onboarding_service=UserProfileService())
    except Exception as exc:
        log_warning(f"iMessage onboarding flow unavailable: {exc}")
        return None


class IMessagePoller:
    def __init__(
        self,
        reader: ChatDBReader | None = None,
        adapter: IMessageAdapter | None = None,
        message_handler: Any = None,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        sender: Any = None,
        onboarding: Any = None,
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
        self.onboarding = (
            onboarding if onboarding is not None else _build_default_onboarding(self.adapter)
        )
        self.poll_interval_seconds = poll_interval_seconds
        self.state = _load_state()
        self._onboarding_tasks: dict[str, asyncio.Task] = {}

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
            if not self._spawn_onboarding(handle):
                self.sender(handle, FIRST_CONTACT_NUDGE)
            return

        # Explicit restart: covers a crashed/timed-out onboarding AND a
        # process restart mid-onboarding (known_handles persists, so the
        # first-contact branch won't fire again). OnboardingFlow resumes
        # from its own saved progress, so no answers are lost.
        if text.strip().lower() in RESTART_KEYWORDS and self._spawn_onboarding(handle):
            return

        try:
            reply = self.message_handler.handle(text, client_key=handle)
        except Exception as exc:
            log_error(f"iMessage handler failed for {handle}", exc=exc)
            reply = "죄송해요, 잠시 문제가 생겼어요. 다시 시도해주세요."
        self.sender(handle, reply)

    def _spawn_onboarding(self, handle: str) -> bool:
        """Start OnboardingFlow as a background task. Returns False when there
        is no flow or no running event loop (sync poll_once callers)."""
        if self.onboarding is None:
            return False
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False

        async def run() -> None:
            async with self.adapter.get_user_lock(handle):
                try:
                    await self.onboarding.execute(handle)
                except Exception as exc:
                    log_error(f"iMessage onboarding failed for {handle}", exc=exc)
                    await asyncio.to_thread(self.sender, handle, ONBOARDING_FAILED_MESSAGE)

        self._onboarding_tasks[handle] = loop.create_task(run())
        return True

    async def run_async(self) -> None:
        self.reader.max_rowid()  # fail fast on missing Full Disk Access
        self.bootstrap_if_first_run()
        log_info(f"iMessage poller started (interval={self.poll_interval_seconds}s)")
        while True:
            try:
                self.poll_once()
            except ChatDBPermissionError:
                raise
            except Exception as exc:
                log_error("iMessage poll iteration failed", exc=exc)
            await asyncio.sleep(self.poll_interval_seconds)

    def run_forever(self) -> None:
        try:
            asyncio.run(self.run_async())
        except ChatDBPermissionError as exc:
            log_error(str(exc))
            raise


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
