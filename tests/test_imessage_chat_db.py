from __future__ import annotations

import sqlite3

import pytest

from garmin_coach.interfaces.imessage.chat_db import (
    ChatDBPermissionError,
    ChatDBReader,
    _extract_text_from_attributed_body,
    apple_time_to_datetime,
)


def _make_synthetic_chat_db(path):
    """Build a minimal chat.db-shaped sqlite file for tests.

    Real chat.db is far larger; this mirrors only the columns our reader
    actually queries so tests exercise the real join/filter logic without
    ever touching a live Messages database.
    """
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT, service TEXT)")
    conn.execute(
        """CREATE TABLE message (
            ROWID INTEGER PRIMARY KEY, guid TEXT, text TEXT, attributedBody BLOB,
            handle_id INTEGER, is_from_me INTEGER, date INTEGER
        )"""
    )
    conn.execute("INSERT INTO handle (ROWID, id, service) VALUES (1, '+15551234567', 'iMessage')")
    conn.execute("INSERT INTO handle (ROWID, id, service) VALUES (2, 'friend@example.com', 'iMessage')")
    conn.commit()
    conn.close()
    return conn


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "chat.db"
    _make_synthetic_chat_db(path)
    return path


def _insert_message(db_path, rowid, handle_rowid, text, is_from_me=0, date=0, attributed_body=None):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO message (ROWID, guid, text, attributedBody, handle_id, is_from_me, date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (rowid, f"guid-{rowid}", text, attributed_body, handle_rowid, is_from_me, date),
    )
    conn.commit()
    conn.close()


def test_poll_new_messages_returns_only_inbound_after_rowid(db_path):
    _insert_message(db_path, 1, 1, "hi from friend")
    _insert_message(db_path, 2, 1, "outbound from me", is_from_me=1)
    _insert_message(db_path, 3, 2, "hi from second friend")

    reader = ChatDBReader(str(db_path))
    messages = reader.poll_new_messages(after_rowid=0)

    assert [m.rowid for m in messages] == [1, 3]
    assert messages[0].handle == "+15551234567"
    assert messages[0].text == "hi from friend"
    assert messages[1].handle == "friend@example.com"


def test_poll_new_messages_respects_after_rowid_cursor(db_path):
    _insert_message(db_path, 1, 1, "first")
    _insert_message(db_path, 2, 1, "second")

    reader = ChatDBReader(str(db_path))
    messages = reader.poll_new_messages(after_rowid=1)

    assert [m.rowid for m in messages] == [2]


def test_max_rowid_reflects_current_table_state(db_path):
    _insert_message(db_path, 5, 1, "hi")
    reader = ChatDBReader(str(db_path))
    assert reader.max_rowid() == 5


def test_max_rowid_is_zero_for_empty_table(db_path):
    reader = ChatDBReader(str(db_path))
    assert reader.max_rowid() == 0


def test_missing_db_raises_permission_error_not_generic_exception(tmp_path):
    reader = ChatDBReader(str(tmp_path / "does-not-exist.db"))
    with pytest.raises(ChatDBPermissionError):
        reader.max_rowid()


def test_message_with_no_text_and_no_attributed_body_is_skipped(db_path):
    _insert_message(db_path, 1, 1, None)
    reader = ChatDBReader(str(db_path))
    assert reader.poll_new_messages(after_rowid=0) == []


def test_extract_text_from_attributed_body_recovers_plain_string():
    # Minimal synthetic blob mimicking the NSString-length-payload layout
    # this heuristic looks for — not a real macOS archive, just its shape.
    payload = "recovered text"
    blob = b"NSString" + b"\x00\x00\x00" + bytes([len(payload)]) + payload.encode("utf-8")
    assert _extract_text_from_attributed_body(blob) == payload


def test_extract_text_from_attributed_body_returns_none_for_garbage():
    assert _extract_text_from_attributed_body(b"not a real archive at all") is None


def test_message_falls_back_to_attributed_body_when_text_is_null(db_path):
    payload = "rich text reply"
    blob = b"NSString" + b"\x00\x00\x00" + bytes([len(payload)]) + payload.encode("utf-8")
    _insert_message(db_path, 1, 1, None, attributed_body=blob)

    reader = ChatDBReader(str(db_path))
    messages = reader.poll_new_messages(after_rowid=0)

    assert len(messages) == 1
    assert messages[0].text == payload
    assert messages[0].text_is_best_effort is True


def test_apple_time_to_datetime_handles_nanosecond_and_second_epochs():
    # ~2026-01-01 in nanoseconds since 2001-01-01
    nanos = 789_000_000 * 1_000_000_000
    dt_ns = apple_time_to_datetime(nanos)
    assert dt_ns is not None and dt_ns.year == 2026

    seconds = 789_000_000
    dt_s = apple_time_to_datetime(seconds)
    assert dt_s is not None and dt_s.year == 2026


def test_apple_time_to_datetime_handles_zero_and_garbage():
    assert apple_time_to_datetime(0) is None
    assert apple_time_to_datetime(-1) is None or apple_time_to_datetime(-1).year < 2001
