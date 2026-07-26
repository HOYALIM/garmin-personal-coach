from __future__ import annotations

import sqlite3

import pytest

from garmin_coach.interfaces.imessage.adapter import IMessageAdapter
from garmin_coach.interfaces.imessage.chat_db import ChatDBPermissionError, ChatDBReader
from garmin_coach.interfaces.imessage.poller import FIRST_CONTACT_NUDGE, IMessagePoller


def _make_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT, service TEXT)")
    conn.execute(
        """CREATE TABLE message (
            ROWID INTEGER PRIMARY KEY, guid TEXT, text TEXT, attributedBody BLOB,
            handle_id INTEGER, is_from_me INTEGER, date INTEGER
        )"""
    )
    conn.execute("INSERT INTO handle (ROWID, id, service) VALUES (1, '+15551234567', 'iMessage')")
    conn.commit()
    conn.close()


def _insert(db_path, rowid, text, is_from_me=0):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO message (ROWID, guid, text, handle_id, is_from_me, date) "
        "VALUES (?, ?, ?, 1, ?, 0)",
        (rowid, f"g{rowid}", text, is_from_me),
    )
    conn.commit()
    conn.close()


class FakeMessageHandler:
    def __init__(self, response="coached reply"):
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def handle(self, message, client_key="default"):
        self.calls.append((message, client_key))
        return self.response


class RecordingSender:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def __call__(self, handle, text):
        self.sent.append((handle, text))
        return True


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "chat.db"
    _make_db(path)
    state_dir = tmp_path / "state"
    monkeypatch.setattr("garmin_coach.interfaces.imessage.poller.STATE_DIR", str(state_dir))
    monkeypatch.setattr(
        "garmin_coach.interfaces.imessage.poller.STATE_FILE",
        str(state_dir / "imessage_state.json"),
    )
    return path


def _make_poller(db_path, sender, handler):
    reader = ChatDBReader(str(db_path))
    adapter = IMessageAdapter(sender=sender)
    return IMessagePoller(reader=reader, adapter=adapter, message_handler=handler)


def test_first_message_from_new_handle_gets_onboarding_nudge_not_coaching(db_path):
    sender = RecordingSender()
    handler = FakeMessageHandler()
    poller = _make_poller(db_path, sender, handler)
    poller.bootstrap_if_first_run()

    _insert(db_path, 1, "hi there")
    handled = poller.poll_once()

    assert handled == 1
    assert handler.calls == []  # not routed to coaching yet
    assert sender.sent == [("+15551234567", FIRST_CONTACT_NUDGE)]


def test_known_handle_gets_routed_to_message_handler(db_path):
    sender = RecordingSender()
    handler = FakeMessageHandler(response="run 5k easy today")
    poller = _make_poller(db_path, sender, handler)
    poller.bootstrap_if_first_run()

    _insert(db_path, 1, "first contact")
    poller.poll_once()
    sender.sent.clear()

    _insert(db_path, 2, "how should I train today?")
    poller.poll_once()

    assert handler.calls == [("how should I train today?", "+15551234567")]
    assert sender.sent == [("+15551234567", "run 5k easy today")]


def test_outbound_messages_are_never_routed_or_replied_to(db_path):
    sender = RecordingSender()
    handler = FakeMessageHandler()
    poller = _make_poller(db_path, sender, handler)
    poller.bootstrap_if_first_run()

    _insert(db_path, 1, "message I sent myself", is_from_me=1)
    handled = poller.poll_once()

    assert handled == 0
    assert sender.sent == []
    assert handler.calls == []


def test_bootstrap_on_first_run_skips_pre_existing_history(db_path):
    _insert(db_path, 1, "old message before bot started")
    sender = RecordingSender()
    handler = FakeMessageHandler()
    poller = _make_poller(db_path, sender, handler)

    poller.bootstrap_if_first_run()  # should fast-forward past rowid 1
    handled = poller.poll_once()

    assert handled == 0
    assert sender.sent == []


def test_state_persists_across_poller_instances(db_path, tmp_path):
    sender = RecordingSender()
    handler = FakeMessageHandler()
    poller1 = _make_poller(db_path, sender, handler)
    poller1.bootstrap_if_first_run()
    _insert(db_path, 1, "hello")
    poller1.poll_once()  # onboarding nudge for new handle
    _insert(db_path, 2, "second message")
    poller1.poll_once()

    poller2 = _make_poller(db_path, RecordingSender(), FakeMessageHandler())
    poller2.bootstrap_if_first_run()  # must not re-fast-forward past existing state
    assert poller2.state["last_rowid"] == 2
    assert "+15551234567" in poller2.state["known_handles"]


def test_message_handler_exception_sends_friendly_error_not_crash(db_path):
    class BoomHandler:
        def handle(self, message, client_key="default"):
            raise RuntimeError("boom")

    sender = RecordingSender()
    poller = _make_poller(db_path, sender, BoomHandler())
    poller.bootstrap_if_first_run()
    _insert(db_path, 1, "first")
    poller.poll_once()
    sender.sent.clear()

    _insert(db_path, 2, "trigger the boom")
    poller.poll_once()  # must not raise

    assert len(sender.sent) == 1
    assert "문제" in sender.sent[0][1]


def test_missing_chat_db_raises_permission_error_on_run_forever(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "garmin_coach.interfaces.imessage.poller.STATE_DIR", str(tmp_path / "state")
    )
    monkeypatch.setattr(
        "garmin_coach.interfaces.imessage.poller.STATE_FILE",
        str(tmp_path / "state" / "imessage_state.json"),
    )
    reader = ChatDBReader(str(tmp_path / "nonexistent.db"))
    poller = IMessagePoller(reader=reader, adapter=IMessageAdapter(sender=lambda h, t: True), message_handler=FakeMessageHandler())

    with pytest.raises(ChatDBPermissionError):
        poller.run_forever()


def test_pending_flow_input_bypasses_message_handler(db_path):
    sender = RecordingSender()
    handler = FakeMessageHandler()
    adapter = IMessageAdapter(sender=sender)
    poller = IMessagePoller(reader=ChatDBReader(str(db_path)), adapter=adapter, message_handler=handler)
    poller.bootstrap_if_first_run()

    # simulate an in-flight flow awaiting this handle's input
    import asyncio

    from garmin_coach.ports import Option

    async def scenario():
        task = asyncio.create_task(
            adapter.request_select("+15551234567", "choose", [Option("Rest", "rest")])
        )
        while "+15551234567" not in adapter._pending:
            await asyncio.sleep(0.001)
        _insert(db_path, 1, "1")
        poller.poll_once()
        return await task

    result = asyncio.run(scenario())
    assert result == "rest"
    assert handler.calls == []  # never touched the free-text coaching path


# -- conversational onboarding (async runtime) --------------------------------


class FakeOnboarding:
    """Asks one question through the adapter, like the real OnboardingFlow."""

    def __init__(self, adapter):
        self.adapter = adapter
        self.calls = 0
        self.answers: list[str] = []

    async def execute(self, user_id):
        self.calls += 1
        answer = await self.adapter.request_text(user_id, "👋 이름을 알려주세요.")
        self.answers.append(answer)


class BoomOnboarding:
    def __init__(self):
        self.calls = 0

    async def execute(self, user_id):
        self.calls += 1
        raise RuntimeError("onboarding exploded")


def _make_onboarding_poller(db_path, onboarding_factory=None):
    sender = RecordingSender()
    handler = FakeMessageHandler()
    adapter = IMessageAdapter(sender=sender)
    onboarding = onboarding_factory(adapter) if onboarding_factory else FakeOnboarding(adapter)
    poller = IMessagePoller(
        reader=ChatDBReader(str(db_path)),
        adapter=adapter,
        message_handler=handler,
        onboarding=onboarding,
    )
    poller.bootstrap_if_first_run()
    return poller, adapter, sender, handler, onboarding


async def _wait_for_pending(adapter, handle, timeout=2.0):
    import asyncio

    async def wait():
        while handle not in adapter._pending:
            await asyncio.sleep(0.001)

    await asyncio.wait_for(wait(), timeout=timeout)


def test_first_contact_in_async_runtime_starts_onboarding(db_path):
    import asyncio

    poller, adapter, sender, handler, onboarding = _make_onboarding_poller(db_path)

    async def scenario():
        _insert(db_path, 1, "안녕하세요")
        poller.poll_once()  # spawns the onboarding task
        await _wait_for_pending(adapter, "+15551234567")
        _insert(db_path, 2, "Ho")
        poller.poll_once()  # routed into the awaiting flow, not MessageHandler
        await poller._onboarding_tasks["+15551234567"]

    asyncio.run(scenario())

    assert onboarding.calls == 1
    assert onboarding.answers == ["Ho"]
    assert handler.calls == []  # nothing leaked to free-text coaching
    assert any("이름" in text for _, text in sender.sent)
    assert all(text != FIRST_CONTACT_NUDGE for _, text in sender.sent)


def test_restart_keyword_respawns_onboarding_for_known_handle(db_path):
    import asyncio

    poller, adapter, sender, handler, onboarding = _make_onboarding_poller(db_path)
    poller.state["known_handles"] = ["+15551234567"]  # e.g. process restarted mid-onboarding

    async def scenario():
        _insert(db_path, 1, "시작")
        poller.poll_once()
        await _wait_for_pending(adapter, "+15551234567")
        _insert(db_path, 2, "Ho")
        poller.poll_once()
        await poller._onboarding_tasks["+15551234567"]

    asyncio.run(scenario())

    assert onboarding.calls == 1
    assert handler.calls == []


def test_onboarding_crash_sends_recovery_hint(db_path):
    import asyncio

    from garmin_coach.interfaces.imessage.poller import ONBOARDING_FAILED_MESSAGE

    poller, adapter, sender, handler, onboarding = _make_onboarding_poller(
        db_path, onboarding_factory=lambda adapter: BoomOnboarding()
    )

    async def scenario():
        _insert(db_path, 1, "hi")
        poller.poll_once()
        await poller._onboarding_tasks["+15551234567"]

    asyncio.run(scenario())

    assert onboarding.calls == 1
    assert sender.sent == [("+15551234567", ONBOARDING_FAILED_MESSAGE)]


def test_sync_poll_without_loop_still_falls_back_to_nudge(db_path):
    poller, adapter, sender, handler, onboarding = _make_onboarding_poller(db_path)

    _insert(db_path, 1, "hi")
    poller.poll_once()  # no running event loop here

    assert onboarding.calls == 0
    assert sender.sent == [("+15551234567", FIRST_CONTACT_NUDGE)]
