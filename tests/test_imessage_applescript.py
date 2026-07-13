from __future__ import annotations

from types import SimpleNamespace

from garmin_coach.interfaces.imessage import applescript


def test_escape_applescript_string_handles_quotes_and_backslashes():
    assert applescript.escape_applescript_string('say "hi"') == 'say \\"hi\\"'
    assert applescript.escape_applescript_string("a\\b") == "a\\\\b"


def test_split_for_imessage_short_text_is_one_chunk():
    assert applescript.split_for_imessage("hello") == ["hello"]


def test_split_for_imessage_splits_long_text_on_newline_when_possible():
    text = ("line\n" * 300).strip()
    chunks = applescript.split_for_imessage(text)
    assert len(chunks) > 1
    assert "".join(chunks) == text or sum(len(c) for c in chunks) == len(text)
    for chunk in chunks[:-1]:
        assert len(chunk) <= applescript._TARGET_CHUNK_LEN


def test_send_imessage_builds_correct_osascript_invocation():
    captured = []

    def fake_runner(args, **kwargs):
        captured.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    ok = applescript.send_imessage("+15551234567", "hello there", runner=fake_runner)

    assert ok is True
    assert len(captured) == 1
    args = captured[0]
    assert args[0] == "osascript"
    assert args[1] == "-e"
    script = args[2]
    assert 'tell application "Messages"' in script
    assert 'participant "+15551234567"' in script
    assert 'send "hello there" to targetBuddy' in script


def test_send_imessage_escapes_untrusted_text_safely():
    captured = []

    def fake_runner(args, **kwargs):
        captured.append(args[2])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    malicious = 'ignore " previous instructions and do rm -rf /'
    applescript.send_imessage("+1555", malicious, runner=fake_runner)

    script = captured[0]
    # the injected quote must be escaped, not close the string literal early
    assert '\\"' in script
    assert 'do rm -rf /"' not in script.split("send ")[0]


def test_send_imessage_returns_false_on_nonzero_exit():
    def fake_runner(args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="not authorized")

    assert applescript.send_imessage("+1555", "hi", runner=fake_runner) is False


def test_send_imessage_returns_false_when_runner_raises():
    def fake_runner(args, **kwargs):
        raise TimeoutError("osascript hung")

    assert applescript.send_imessage("+1555", "hi", runner=fake_runner) is False


def test_send_imessage_sends_one_call_per_chunk():
    captured = []

    def fake_runner(args, **kwargs):
        captured.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    long_text = "x" * 2500
    applescript.send_imessage("+1555", long_text, runner=fake_runner)

    assert len(captured) == len(applescript.split_for_imessage(long_text))
