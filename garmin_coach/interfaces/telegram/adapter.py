"""TelegramAdapter — CoachingPort implementation for Telegram.

Uses python-telegram-bot v20+ (async).
Handles Telegram-specific constraints:
- Message 4096 char limit (auto-split)
- Callback data 64 byte limit (short ID mapping)
- MarkdownV2 special character escaping
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import uuid
from datetime import date
from typing import Any

from garmin_coach.interfaces.telegram import renderer
from garmin_coach.ports import (
    Button,
    CoachingPort,
    InputAbortReason,
    InputAborted,
    InputType,
    Option,
    Report,
)

logger = logging.getLogger(__name__)

_MAX_MSG_LEN = 4096
_TARGET_MSG_LEN = 4000
# Timeout for waiting on user input (seconds)
_INPUT_TIMEOUT = 300  # 5 minutes
_SEND_RETRIES = 3


def _load_telegram():
    """Lazy-load telegram modules."""
    telegram = importlib.import_module("telegram")
    telegram_ext = importlib.import_module("telegram.ext")
    return telegram, telegram_ext


class _PendingInput:
    """Tracks a pending user input request."""

    def __init__(self) -> None:
        self.event = asyncio.Event()
        self.value: Any = None


class TelegramAdapter(CoachingPort):
    """Telegram implementation of CoachingPort.

    This adapter holds a reference to the telegram Bot instance and
    manages input collection via asyncio events keyed by user_id.
    """

    def __init__(self, bot: Any) -> None:
        """
        Args:
            bot: telegram.Bot instance (from python-telegram-bot).
        """
        self.bot = bot
        self._pending: dict[str, _PendingInput] = {}
        # Short callback ID → full callback_data mapping
        self._callback_map: dict[str, str] = {}
        # Per-user lock to prevent concurrent flow execution
        self._user_locks: dict[str, asyncio.Lock] = {}
        self._telegram, self._telegram_ext = _load_telegram()

    def get_user_lock(self, user_id: str) -> asyncio.Lock:
        """Get or create a per-user lock to serialize flow execution."""
        if user_id not in self._user_locks:
            self._user_locks[user_id] = asyncio.Lock()
        return self._user_locks[user_id]

    # -- Internal helpers -----------------------------------------------

    def _split_message(self, text: str) -> list[str]:
        if len(text) <= _TARGET_MSG_LEN:
            return [text]

        chunks: list[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= _TARGET_MSG_LEN:
                chunks.append(remaining)
                break
            split_at = remaining.rfind("\n", 0, _TARGET_MSG_LEN)
            if split_at <= 0:
                split_at = _TARGET_MSG_LEN
            else:
                split_at += 1
            while split_at > 0 and self._has_dangling_escape(remaining[:split_at]):
                split_at -= 1
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:]
        return chunks

    def _has_dangling_escape(self, text: str) -> bool:
        count = 0
        for ch in reversed(text):
            if ch == "\\":
                count += 1
            else:
                break
        return count % 2 == 1

    def _find_split_boundary(self, text: str) -> int:
        for separator in ("\n\n", "\n"):
            index = text.rfind(separator, 0, _TARGET_MSG_LEN)
            if index > 0:
                return index + len(separator)
        return _TARGET_MSG_LEN

    def _hard_split(self, text: str) -> list[str]:
        return [text[i : i + _TARGET_MSG_LEN] for i in range(0, len(text), _TARGET_MSG_LEN)]

    def _make_inline_keyboard(self, buttons: list[Button], cols: int = 2) -> Any:
        """Build InlineKeyboardMarkup from Button list."""
        InlineKeyboardButton = self._telegram.InlineKeyboardButton
        InlineKeyboardMarkup = self._telegram.InlineKeyboardMarkup

        rows: list[list[Any]] = []
        row: list[Any] = []
        for btn in buttons:
            # Map short ID for callback data > 64 bytes
            cb_data = btn.callback_data
            if len(cb_data.encode("utf-8")) > 64:
                short_id = uuid.uuid4().hex[:12]
                self._callback_map[short_id] = cb_data
                cb_data = short_id

            row.append(InlineKeyboardButton(text=btn.label, callback_data=cb_data))
            if len(row) >= cols:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        return InlineKeyboardMarkup(rows)

    def _options_to_keyboard(self, options: list[Option], cols: int = 2) -> Any:
        """Build InlineKeyboardMarkup from Option list."""
        buttons = []
        for opt in options:
            label = f"{opt.emoji} {opt.label}" if opt.emoji else opt.label
            buttons.append(Button(label=label, callback_data=f"opt:{opt.value}"))
        return self._make_inline_keyboard(buttons, cols=cols)

    def resolve_callback(self, callback_data: str) -> str:
        """Resolve short callback ID back to full data."""
        return self._callback_map.pop(callback_data, callback_data)

    async def _wait_for_input(self, user_id: str) -> Any:
        """Block until user provides input, with timeout."""
        pending = _PendingInput()
        self._pending[user_id] = pending
        try:
            await asyncio.wait_for(pending.event.wait(), timeout=_INPUT_TIMEOUT)
            return pending.value
        except asyncio.TimeoutError:
            logger.warning("Input timeout for user %s", user_id)
            return None
        finally:
            self._pending.pop(user_id, None)

    def deliver_input(self, user_id: str, value: Any) -> bool:
        """Called by handlers when user provides input.

        Returns True if there was a pending request.
        """
        pending = self._pending.get(user_id)
        if pending:
            pending.value = value
            pending.event.set()
            return True
        return False

    async def _call_with_retry(self, func: Any, **kwargs: Any) -> None:
        last_error: Exception | None = None
        for attempt in range(_SEND_RETRIES):
            try:
                await func(**kwargs)
                return
            except Exception as exc:
                last_error = exc
                logger.warning("Telegram send attempt %s failed", attempt + 1, exc_info=exc)
                if attempt < _SEND_RETRIES - 1:
                    await asyncio.sleep(0.2 * (attempt + 1))
        if last_error:
            raise last_error

    # -- CoachingPort implementation ------------------------------------

    async def send_message(
        self,
        user_id: str,
        text: str,
        buttons: list[Button] | None = None,
    ) -> None:
        escaped_text = renderer.escape_markdown_v2(text)
        chunks = self._split_message(escaped_text)
        for i, chunk in enumerate(chunks):
            if len(chunk) > _MAX_MSG_LEN:
                raise ValueError(f"Telegram message chunk exceeded limit: {len(chunk)}")
            reply_markup = None
            if buttons and i == len(chunks) - 1:
                reply_markup = self._make_inline_keyboard(buttons)
            await self._call_with_retry(
                self.bot.send_message,
                chat_id=int(user_id),
                text=chunk,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup,
            )

    async def send_image(
        self,
        user_id: str,
        image: bytes,
        caption: str | None = None,
    ) -> None:
        await self._call_with_retry(
            self.bot.send_photo,
            chat_id=int(user_id),
            photo=image,
            caption=caption,
        )

    async def send_report(
        self,
        user_id: str,
        report: Report,
    ) -> None:
        # Send title
        if report.title:
            await self.send_message(user_id, f"📊 {report.title}")

        # Send each section
        for section in report.sections:
            if section.content_type == "text" and section.text:
                await self.send_message(user_id, section.text)
            elif section.content_type == "image" and section.image:
                await self.send_image(user_id, section.image, caption=section.caption)

    async def request_text(self, user_id: str, prompt: str) -> str:
        if prompt:
            await self.send_message(
                user_id,
                prompt,
                buttons=[Button(label="❌ 취소", callback_data="input:cancel")],
            )
        result = await self._wait_for_input(user_id)
        if result is None:
            raise InputAborted(InputType.TEXT, InputAbortReason.TIMEOUT)
        if result == "input:cancel":
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
            if raw == "input:cancel":
                raise InputAborted(InputType.NUMBER, InputAbortReason.CANCELLED)
            try:
                val = float(str(raw))
                if min_val is not None and val < min_val:
                    await self.send_message(user_id, f"⚠️ {min_val} 이상 값을 입력해주세요.")
                    continue
                if max_val is not None and val > max_val:
                    await self.send_message(user_id, f"⚠️ {max_val} 이하 값을 입력해주세요.")
                    continue
                return val
            except ValueError:
                await self.send_message(user_id, "⚠️ 숫자를 입력해주세요.")

    async def request_date(self, user_id: str, prompt: str) -> date:
        while True:
            await self.send_message(
                user_id,
                f"{prompt}\n(형식: YYYY-MM-DD)",
                buttons=[Button(label="❌ 취소", callback_data="input:cancel")],
            )
            raw = await self._wait_for_input(user_id)
            if raw is None:
                raise InputAborted(InputType.DATE, InputAbortReason.TIMEOUT)
            if raw == "input:cancel":
                raise InputAborted(InputType.DATE, InputAbortReason.CANCELLED)
            try:
                return date.fromisoformat(str(raw).strip())
            except ValueError:
                await self.send_message(
                    user_id, "⚠️ 날짜 형식이 올바르지 않습니다. (예: 2026-04-06)"
                )

    async def request_select(
        self,
        user_id: str,
        prompt: str,
        options: list[Option],
    ) -> str:
        buttons = [
            Button(
                label=f"{opt.emoji} {opt.label}" if opt.emoji else opt.label,
                callback_data=f"opt:{opt.value}",
            )
            for opt in options
        ]
        buttons.append(Button(label="❌ 취소", callback_data="input:cancel"))
        keyboard = self._make_inline_keyboard(buttons, cols=2)
        await self._call_with_retry(
            self.bot.send_message,
            chat_id=int(user_id),
            text=prompt,
            reply_markup=keyboard,
        )
        result = await self._wait_for_input(user_id)
        if result is None:
            raise InputAborted(InputType.SELECT, InputAbortReason.TIMEOUT)
        raw = str(result)
        if raw == "input:cancel":
            raise InputAborted(InputType.SELECT, InputAbortReason.CANCELLED)
        if raw.startswith("opt:"):
            return raw[4:]
        return raw

    async def request_multi_select(
        self,
        user_id: str,
        prompt: str,
        options: list[Option],
    ) -> list[str]:
        selected: set[str] = set()

        while True:
            # Build toggle keyboard
            buttons = []
            for opt in options:
                prefix = "✅ " if opt.value in selected else ""
                emoji = f"{opt.emoji} " if opt.emoji else ""
                label = f"{prefix}{emoji}{opt.label}"
                buttons.append(Button(label=label, callback_data=f"msel:{opt.value}"))
            buttons.append(Button(label="✅ 완료", callback_data="msel:__done__"))
            buttons.append(Button(label="❌ 취소", callback_data="msel:__cancel__"))

            keyboard = self._make_inline_keyboard(buttons, cols=2)
            await self._call_with_retry(
                self.bot.send_message,
                chat_id=int(user_id),
                text=prompt,
                reply_markup=keyboard,
            )

            result = await self._wait_for_input(user_id)
            if result is None:
                raise InputAborted(InputType.MULTI_SELECT, InputAbortReason.TIMEOUT)

            raw = str(result)
            if raw == "msel:__done__":
                break
            if raw == "msel:__cancel__":
                raise InputAborted(InputType.MULTI_SELECT, InputAbortReason.CANCELLED)
            if raw.startswith("msel:"):
                val = raw[5:]
                if val in selected:
                    selected.discard(val)
                else:
                    selected.add(val)

        return list(selected)

    async def request_photo(self, user_id: str, prompt: str) -> bytes | None:
        await self.send_message(
            user_id,
            prompt,
            buttons=[Button(label="⏭️ 건너뛰기", callback_data="photo:skip")],
        )
        result = await self._wait_for_input(user_id)
        if result is None:
            raise InputAborted(InputType.PHOTO, InputAbortReason.TIMEOUT)
        if result == "photo:skip":
            raise InputAborted(InputType.PHOTO, InputAbortReason.SKIPPED)
        if isinstance(result, bytes):
            return result
        raise InputAborted(InputType.PHOTO, InputAbortReason.CANCELLED)
