from __future__ import annotations

import asyncio

import pytest

from garmin_coach.interfaces.imessage.adapter import IMessageAdapter
from garmin_coach.ports import Button, InputAborted, Option


class FakeSender:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def __call__(self, handle, text):
        self.sent.append((handle, text))
        return True


async def _deliver_when_pending(adapter, handle, text, timeout=2.0):
    """Wait until the adapter is actually awaiting `handle`'s input, then
    deliver it. A bare `await asyncio.sleep(0)` races with the real thread
    dispatch inside send_message/request_select's `asyncio.to_thread` call —
    the task may not have reached `_wait_for_input` yet, so `deliver_input`
    would silently no-op and the awaiting task would hang forever."""
    async def wait_until_registered():
        while handle not in adapter._pending:
            await asyncio.sleep(0.001)

    await asyncio.wait_for(wait_until_registered(), timeout=timeout)
    adapter.deliver_input(handle, text)


def test_send_message_without_buttons_sends_plain_text():
    sender = FakeSender()
    adapter = IMessageAdapter(sender=sender)

    asyncio.run(adapter.send_message("+1555", "hello"))

    assert sender.sent == [("+1555", "hello")]


def test_send_message_with_buttons_renders_numbered_choices():
    sender = FakeSender()
    adapter = IMessageAdapter(sender=sender)

    asyncio.run(
        adapter.send_message(
            "+1555",
            "pick one",
            buttons=[Button("Easy", "easy"), Button("Hard", "hard")],
        )
    )

    body = sender.sent[0][1]
    assert "1) Easy" in body
    assert "2) Hard" in body


def test_request_select_resolves_numeric_reply():
    sender = FakeSender()
    adapter = IMessageAdapter(sender=sender)

    async def scenario():
        task = asyncio.create_task(
            adapter.request_select(
                "+1555", "choose", [Option("Rest", "rest"), Option("Interval", "interval")]
            )
        )
        await _deliver_when_pending(adapter, "+1555", "2")
        return await task

    result = asyncio.run(scenario())
    assert result == "interval"


def test_request_select_resolves_label_text_case_insensitive():
    sender = FakeSender()
    adapter = IMessageAdapter(sender=sender)

    async def scenario():
        task = asyncio.create_task(
            adapter.request_select("+1555", "choose", [Option("Rest Day", "rest")])
        )
        await _deliver_when_pending(adapter, "+1555", "rest day")
        return await task

    assert asyncio.run(scenario()) == "rest"


def test_request_select_falls_back_to_raw_text_when_no_choice_matches():
    sender = FakeSender()
    adapter = IMessageAdapter(sender=sender)

    async def scenario():
        task = asyncio.create_task(
            adapter.request_select("+1555", "choose", [Option("Rest", "rest")])
        )
        await _deliver_when_pending(adapter, "+1555", "something unrelated")
        return await task

    assert asyncio.run(scenario()) == "something unrelated"


def test_request_select_cancel_keyword_raises_cancelled():
    sender = FakeSender()
    adapter = IMessageAdapter(sender=sender)

    async def scenario():
        task = asyncio.create_task(
            adapter.request_select("+1555", "choose", [Option("Rest", "rest")])
        )
        await _deliver_when_pending(adapter, "+1555", "취소")
        return await task

    with pytest.raises(InputAborted):
        asyncio.run(scenario())


def test_deliver_input_returns_false_when_nothing_pending():
    adapter = IMessageAdapter(sender=FakeSender())
    assert adapter.deliver_input("+1555", "hi") is False


def test_request_number_validates_bounds_before_returning():
    sender = FakeSender()
    adapter = IMessageAdapter(sender=sender)

    async def scenario():
        task = asyncio.create_task(adapter.request_number("+1555", "weight?", min_val=30, max_val=200))
        await _deliver_when_pending(adapter, "+1555", "5")  # out of bounds, should re-prompt
        await _deliver_when_pending(adapter, "+1555", "70")
        return await task

    assert asyncio.run(scenario()) == 70.0


def test_request_photo_always_skips_with_notice():
    sender = FakeSender()
    adapter = IMessageAdapter(sender=sender)

    with pytest.raises(InputAborted):
        asyncio.run(adapter.request_photo("+1555", "send a photo"))

    assert any("사진" in text for _, text in sender.sent)


def test_different_handles_get_independent_pending_state():
    sender = FakeSender()
    adapter = IMessageAdapter(sender=sender)

    async def scenario():
        task_a = asyncio.create_task(
            adapter.request_select("+1555", "a", [Option("X", "x")])
        )
        task_b = asyncio.create_task(
            adapter.request_select("+1666", "b", [Option("Y", "y")])
        )
        await _deliver_when_pending(adapter, "+1666", "1")
        await _deliver_when_pending(adapter, "+1555", "1")
        return await task_a, await task_b

    result_a, result_b = asyncio.run(scenario())
    assert result_a == "x"
    assert result_b == "y"
