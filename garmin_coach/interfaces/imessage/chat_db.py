"""Read incoming messages from macOS Messages' local chat.db.

Read-only, polling-based (no push API exists). Requires Full Disk Access
granted to whatever process runs this (Terminal, or the packaged binary) —
without it, sqlite3 raises "unable to open database file" even though the
path exists, which is the #1 support question for every project that does
this (BlueBubbles, imsg, Jared). See `ChatDBPermissionError`.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from garmin_coach.logging_config import log_warning

DEFAULT_CHAT_DB_PATH = os.path.expanduser("~/Library/Messages/chat.db")

# Apple's "Mac absolute time": nanoseconds (modern) or seconds (legacy, pre
# Big Sur) since this epoch. We only use it for human-readable logging.
_APPLE_EPOCH = datetime(2001, 1, 1)


class ChatDBPermissionError(RuntimeError):
    """Raised when chat.db can't be opened — almost always missing Full Disk Access."""


@dataclass
class IncomingMessage:
    rowid: int
    handle: str  # sender's phone number or email, as Messages stores it
    text: str | None
    date: datetime | None
    text_is_best_effort: bool = False  # True if recovered via attributedBody heuristic


def apple_time_to_datetime(raw: int) -> datetime | None:
    if not raw:
        return None
    # Big Sur+ stores nanoseconds; older macOS stored seconds. A nanosecond
    # value is ~10^18 for recent dates vs ~10^9 for a seconds value.
    seconds = raw / 1_000_000_000 if raw > 10**12 else raw
    try:
        return _APPLE_EPOCH + timedelta(seconds=seconds)
    except (OverflowError, OSError):
        return None


def _extract_text_from_attributed_body(blob: bytes) -> str | None:
    """Best-effort plain-text recovery from an NSAttributedString archive.

    NOT a full NSKeyedArchiver/typedstream parser — those formats vary across
    macOS versions and are substantial to implement correctly. This looks for
    the "NSString" marker used by both the legacy `streamtyped` format and
    modern keyed-archive format, then reads the UTF-8 run that follows a
    length byte. Returns None (not a guess) rather than risk misreading a
    reply if the shape doesn't match what we expect.
    """
    marker = b"NSString"
    idx = blob.find(marker)
    if idx == -1:
        return None
    # Layout after the marker in both known formats: a few framing bytes,
    # then a length byte, then the UTF-8 payload of that length.
    cursor = idx + len(marker)
    # Skip framing bytes (class metadata) up to a reasonable bound.
    for offset in range(cursor, min(cursor + 12, len(blob) - 1)):
        length = blob[offset]
        if length == 0 or length > 200:
            continue
        start = offset + 1
        end = start + length
        if end > len(blob):
            continue
        candidate = blob[start:end]
        try:
            text = candidate.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if text.isprintable() and text.strip():
            return text
    return None


class ChatDBReader:
    def __init__(self, db_path: str = DEFAULT_CHAT_DB_PATH):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        try:
            # uri=True + mode=ro: never risk a write to the user's live Messages db.
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            conn.execute("SELECT 1 FROM message LIMIT 1")
            return conn
        except sqlite3.OperationalError as exc:
            raise ChatDBPermissionError(
                f"Cannot read {self.db_path}: {exc}. "
                "Grant Full Disk Access to the process running this "
                "(System Settings → Privacy & Security → Full Disk Access)."
            ) from exc

    def max_rowid(self) -> int:
        """Current high-water mark — call once at startup so a fresh poller
        doesn't replay a Messages history instead of watching only new mail."""
        conn = self._connect()
        try:
            row = conn.execute("SELECT COALESCE(MAX(ROWID), 0) FROM message").fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def poll_new_messages(self, after_rowid: int) -> list[IncomingMessage]:
        """Return inbound (not-from-me) messages with ROWID > after_rowid, ascending."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT message.ROWID, handle.id, message.text, message.attributedBody, message.date
                FROM message
                JOIN handle ON message.handle_id = handle.ROWID
                WHERE message.ROWID > ? AND message.is_from_me = 0
                ORDER BY message.ROWID ASC
                """,
                (after_rowid,),
            ).fetchall()
        finally:
            conn.close()

        messages: list[IncomingMessage] = []
        for rowid, handle, text, attributed_body, raw_date in rows:
            best_effort = False
            if not text and attributed_body:
                text = _extract_text_from_attributed_body(bytes(attributed_body))
                best_effort = text is not None
            if not text:
                log_warning(
                    f"iMessage row {rowid} from {handle} has no recoverable text; skipping."
                )
                continue
            messages.append(
                IncomingMessage(
                    rowid=rowid,
                    handle=handle,
                    text=text,
                    date=apple_time_to_datetime(raw_date),
                    text_is_best_effort=best_effort,
                )
            )
        return messages


__all__ = [
    "DEFAULT_CHAT_DB_PATH",
    "ChatDBPermissionError",
    "ChatDBReader",
    "IncomingMessage",
    "apple_time_to_datetime",
]
