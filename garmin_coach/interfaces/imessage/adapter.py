"""IMessageAdapter — CoachingPort implementation for iMessage.

No native buttons exist on this channel, so `Button`/`Option` lists are
rendered as a numbered list appended to the message text, and the adapter
resolves the user's next plain-text reply against that list (accepting the
number, or a case-insensitive match against the label) before falling back
to treating it as raw text. This mirrors TelegramAdapter's pending-input/
asyncio.Event pattern so the same Flow-layer code works unmodified.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

from garmin_coach.interfaces.imessage.applescript import send_imessage
from garmin_coach.ports import (
    Button,
    CoachingPort,
    InputAborted,
    InputAbortReason,
    InputType,
    Option,
    Report,
)

logger = logging.getLogger(__name__)

_INPUT_TIMEOUT = 600  # seconds — texting is slower-paced than tapping a button
CANCEL_KEYWORDS = {"취소", "cancel", "그만"}
SKIP_KEYWORDS = {"건너뛰기", "skip", "패스"}


class _PendingInput:
    def __init__(self) -> None:
        self.event = asyncio.Event()
        self.value: Any = None


class IMessageAdapter(CoachingPort):
    """iMessage implementation of CoachingPort.

    `user_id` is the sender's iMessage handle (phone number or email, exactly
    as Messages/chat.db stores it) — this doubles as the multi-user key, so
    several different contacts texting this same Mac get independent sessions.
    """

    def __init__(self, sender: Any = send_imessage) -> None:
        # Public so IMessagePoller can share the exact same callable rather
        # than risk wiring a second, different sender for its own direct sends.
        self.sender = sender
        self._pending: dict[str, _PendingInput] = {}
        self._last_choices: dict[str, list[tuple[str, str]]] = {}
        self._user_locks: dict[str, asyncio.Lock] = {}

    def get_user_lock(self, user_id: str) -> asyncio.Lock:
        if user_id not in self._user_locks:
            self._user_locks[user_id] = asyncio.Lock()
        return self._user_locks[user_id]

    # -- inbound entrypoint, called by the chat.db poller ----------------

    def deliver_input(self, user_id: str, raw_text: str) -> bool:
        """Resolve an inbound text against a pending request. Returns True
        if something was awaiting this user's input (poller uses the return
        value to decide whether to instead route it as a fresh message)."""
        pending = self._pending.get(user_id)
        if pending is None:
            return False
        resolved = self._resolve_choice(user_id, raw_text)
        pending.value = resolved if resolved is not None else raw_text
        pending.event.set()
        return True

    def _resolve_choice(self, user_id: str, raw_text: str) -> str | None:
        choices = self._last_choices.get(user_id)
        if not choices:
            return None
        stripped = raw_text.strip()
        if stripped.isdigit():
            index = int(stripped) - 1
            if 0 <= index < len(choices):
                return choices[index][1]
        lowered = stripped.lower()
        for label, value in choices:
            if lowered == label.lower():
                return value
        return None

    async def _wait_for_input(self, user_id: str) -> Any:
        pending = _PendingInput()
        self._pending[user_id] = pending
        try:
            await asyncio.wait_for(pending.event.wait(), timeout=_INPUT_TIMEOUT)
            return pending.value
        except asyncio.TimeoutError:
            logger.warning("iMessage input timeout for %s", user_id)
            return None
        finally:
            self._pending.pop(user_id, None)
            self._last_choices.pop(user_id, None)

    # -- outbound ----------------------------------------------------------

    def _render_choices(self, text: str, choices: list[tuple[str, str]]) -> str:
        lines = [text, ""]
        for i, (label, _value) in enumerate(choices, start=1):
            lines.append(f"{i}) {label}")
        return "\n".join(lines)

    async def send_message(
        self,
        user_id: str,
        text: str,
        buttons: list[Button] | None = None,
    ) -> None:
        body = text
        if buttons:
            choices = [(b.label, b.callback_data) for b in buttons]
            self._last_choices[user_id] = choices
            body = self._render_choices(text, choices)
        await asyncio.to_thread(self.sender, user_id, body)

    async def send_image(
        self,
        user_id: str,
        image: bytes,
        caption: str | None = None,
    ) -> None:
        # AppleScript can attach a file (`send <file> to buddy`), not raw
        # bytes — sending images requires writing to a temp path first.
        # Roadmap item; for now, degrade to a text notice so a chart request
        # doesn't silently vanish.
        note = caption or "차트를 준비했지만 iMessage 이미지 전송은 아직 지원되지 않습니다."
        await asyncio.to_thread(self.sender, user_id, note)

    async def send_report(self, user_id: str, report: Report) -> None:
        if report.title:
            await self.send_message(user_id, f"📊 {report.title}")
        for section in report.sections:
            if section.content_type == "text" and section.text:
                await self.send_message(user_id, section.text)
            elif section.content_type == "image" and section.image:
                await self.send_image(user_id, section.image, caption=section.caption)

    # -- inbound requests ----------------------------------------------------

    async def request_text(self, user_id: str, prompt: str) -> str:
        if prompt:
            await self.send_message(user_id, prompt)
        result = await self._wait_for_input(user_id)
        if result is None:
            raise InputAborted(InputType.TEXT, InputAbortReason.TIMEOUT)
        if str(result).strip().lower() in CANCEL_KEYWORDS:
            raise InputAborted(InputType.TEXT, InputAbortReason.CANCELLED)
        return str(result)

    async def request_number(
        self,
        user_id: str,
        prompt: str,
        min_val: float | None = None,
        max_val: float | None = None,
    ) -> float:
        bounds = ""
        if min_val is not None and max_val is not None:
            bounds = f" ({min_val}-{max_val})"
        elif min_val is not None:
            bounds = f" ({min_val} 이상)"
        elif max_val is not None:
            bounds = f" ({max_val} 이하)"

        while True:
            await self.send_message(user_id, f"{prompt}{bounds}")
            raw = await self._wait_for_input(user_id)
            if raw is None:
                raise InputAborted(InputType.NUMBER, InputAbortReason.TIMEOUT)
            if str(raw).strip().lower() in CANCEL_KEYWORDS:
                raise InputAborted(InputType.NUMBER, InputAbortReason.CANCELLED)
            try:
                val = float(str(raw))
            except ValueError:
                await self.send_message(user_id, "⚠️ 숫자를 입력해주세요.")
                continue
            if min_val is not None and val < min_val:
                await self.send_message(user_id, f"⚠️ {min_val} 이상 값을 입력해주세요.")
                continue
            if max_val is not None and val > max_val:
                await self.send_message(user_id, f"⚠️ {max_val} 이하 값을 입력해주세요.")
                continue
            return val

    async def request_date(self, user_id: str, prompt: str) -> date:
        while True:
            await self.send_message(user_id, f"{prompt}\n(형식: YYYY-MM-DD)")
            raw = await self._wait_for_input(user_id)
            if raw is None:
                raise InputAborted(InputType.DATE, InputAbortReason.TIMEOUT)
            if str(raw).strip().lower() in CANCEL_KEYWORDS:
                raise InputAborted(InputType.DATE, InputAbortReason.CANCELLED)
            try:
                return date.fromisoformat(str(raw).strip())
            except ValueError:
                await self.send_message(user_id, "⚠️ 날짜 형식이 올바르지 않습니다. (예: 2026-04-06)")

    async def request_select(
        self,
        user_id: str,
        prompt: str,
        options: list[Option],
    ) -> str:
        choices = [
            (f"{opt.emoji} {opt.label}" if opt.emoji else opt.label, opt.value)
            for opt in options
        ]
        self._last_choices[user_id] = choices
        await asyncio.to_thread(self.sender, user_id, self._render_choices(prompt, choices))
        result = await self._wait_for_input(user_id)
        if result is None:
            raise InputAborted(InputType.SELECT, InputAbortReason.TIMEOUT)
        if str(result).strip().lower() in CANCEL_KEYWORDS:
            raise InputAborted(InputType.SELECT, InputAbortReason.CANCELLED)
        return str(result)

    async def request_multi_select(
        self,
        user_id: str,
        prompt: str,
        options: list[Option],
    ) -> list[str]:
        selected: set[str] = set()
        while True:
            choices = [
                (
                    f"{'✅ ' if opt.value in selected else ''}"
                    f"{(opt.emoji + ' ') if opt.emoji else ''}{opt.label}",
                    opt.value,
                )
                for opt in options
            ]
            choices.append(("완료", "__done__"))
            self._last_choices[user_id] = choices
            await asyncio.to_thread(
                self.sender,
                user_id,
                self._render_choices(
                    f"{prompt}\n(번호로 토글, '완료'로 끝내기)", choices
                ),
            )
            result = await self._wait_for_input(user_id)
            if result is None:
                raise InputAborted(InputType.MULTI_SELECT, InputAbortReason.TIMEOUT)
            raw = str(result)
            if raw.strip().lower() in CANCEL_KEYWORDS:
                raise InputAborted(InputType.MULTI_SELECT, InputAbortReason.CANCELLED)
            if raw == "__done__":
                break
            if raw in selected:
                selected.discard(raw)
            else:
                selected.add(raw)
        return list(selected)

    async def request_photo(self, user_id: str, prompt: str) -> bytes | None:
        # Reading inbound attachment bytes from chat.db is a roadmap item
        # (requires resolving the attachment file path + Full Disk Access
        # read of ~/Library/Messages/Attachments/). For now this always skips
        # rather than hanging or guessing.
        await self.send_message(user_id, f"{prompt}\n(현재 iMessage에서는 사진 첨부를 지원하지 않아요 — 건너뜁니다)")
        raise InputAborted(InputType.PHOTO, InputAbortReason.SKIPPED)


__all__ = ["CANCEL_KEYWORDS", "SKIP_KEYWORDS", "IMessageAdapter"]
