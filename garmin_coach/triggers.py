"""Trigger layer — intent detection from message text."""

import re
from dataclasses import dataclass
from enum import Enum


class TriggerType(str, Enum):
    WAKE = "wake"
    WORKOUT_COMPLETE = "workout_complete"
    PRECHECK = "precheck"


@dataclass
class TriggerResult:
    trigger_type: TriggerType
    confidence: float = 1.0
    matched_phrase: str | None = None


def _build_wake_patterns() -> list[re.Pattern]:
    return [
        re.compile(r"^(coach[：:]\s*)?일어났", re.IGNORECASE),
        re.compile(r"^(coach[：:]\s*)?기상", re.IGNORECASE),
        re.compile(r"^(coach[：:]\s*)?(woke\s?up|awake)", re.IGNORECASE),
    ]


def _build_workout_patterns() -> list[re.Pattern]:
    return [
        re.compile(r"^(coach[：:]\s*)?운동\s*(끝|끝났|완료|했어?)", re.IGNORECASE),
        re.compile(r"^(coach[：:]\s*)?러닝\s*(끝|끝났|완료|했어?)", re.IGNORECASE),
        re.compile(r"^(coach[：:]\s*)?수영\s*(끝|끝났|완료|했어?)", re.IGNORECASE),
        re.compile(r"^(coach[：:]\s*)?달리기\s*(끝|끝났|완료|했어?)", re.IGNORECASE),
        re.compile(r"^(coach[：:]\s*)?조깅\s*(끝|끝났|완료|했어?)", re.IGNORECASE),
        re.compile(r"^(coach[：:]\s*)?오늘\s*(운동|러닝|달리기|수영)", re.IGNORECASE),
        re.compile(
            r"^(coach[：:]\s*)?(run|jog|swim|ride|workout)\s*(done|finished|complete)",
            re.IGNORECASE,
        ),
    ]


WAKE_PATTERNS = _build_wake_patterns()
WORKOUT_PATTERNS = _build_workout_patterns()


def detect_trigger(text: str) -> TriggerResult | None:
    text = text.strip()
    if not text:
        return None
    for pattern in WAKE_PATTERNS:
        if pattern.search(text):
            return TriggerResult(
                trigger_type=TriggerType.WAKE, matched_phrase=text[:50]
            )
    for pattern in WORKOUT_PATTERNS:
        if pattern.search(text):
            return TriggerResult(
                trigger_type=TriggerType.WORKOUT_COMPLETE, matched_phrase=text[:50]
            )
    return None
