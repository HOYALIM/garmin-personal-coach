import re
from enum import Enum


class Intent(Enum):
    WAKE_UP = "wake_up"
    WORKOUT_COMPLETE = "workout_complete"
    ASK_STATUS = "ask_status"
    ASK_PLAN = "ask_plan"
    ASK_HELP = "ask_help"
    ASK_NUTRITION = "ask_nutrition"
    SYMPTOM_REPORT = "symptom_report"
    UNKNOWN = "unknown"


WAKE_UP_PATTERNS = [
    r"일어났어|깼어|起床|起床了|woke up|good morning|morning",
    r"아침|早上|morning|утро",
]

WORKOUT_COMPLETE_PATTERNS = [
    r"운동 끝|운동完了|workout done|finished|done|running|cycling|swimming",
    r"달렸어|챗|swam| rode |완료|完了",
]

ASK_STATUS_PATTERNS = [
    r"상태|컨디션|状態|condition|status|how am i|how's my",
    r"ctl|atl|tsb|training load|form|fresh",
]

ASK_PLAN_PATTERNS = [
    r"오늘的计划|today.*plan|오늘.*계획|what.*today|schedule|일정",
]

ASK_HELP_PATTERNS = [
    r"도움|help|도와줘|帮我|help me|어떻게|how to",
]

ASK_NUTRITION_PATTERNS = [
    r"영양|식사|meal|food|eat|nutrition|diet|음식| calories|탄수화물|protein|carbs",
]

SYMPTOM_PATTERNS = [
    r"피곤|累了|tired|疲劳|fatigue|fatigado|어려|hard|힘들|辛苦",
    r"아픔|痛|pain|hurt|不舒服|not feeling|몸|body|ache|不舒服",
    r"잠| Sleep|sleep|졸리|sleepy|눈|eye|tired",
    r"headache|두통|머리|hroat|목|neck|어깨|shoulder",
]


def detect_intent(message: str) -> Intent:
    msg = message.lower()

    for pattern in WAKE_UP_PATTERNS:
        if re.search(pattern, msg, re.IGNORECASE):
            return Intent.WAKE_UP

    for pattern in WORKOUT_COMPLETE_PATTERNS:
        if re.search(pattern, msg, re.IGNORECASE):
            return Intent.WORKOUT_COMPLETE

    for pattern in ASK_STATUS_PATTERNS:
        if re.search(pattern, msg, re.IGNORECASE):
            return Intent.ASK_STATUS

    for pattern in ASK_PLAN_PATTERNS:
        if re.search(pattern, msg, re.IGNORECASE):
            return Intent.ASK_PLAN

    for pattern in ASK_HELP_PATTERNS:
        if re.search(pattern, msg, re.IGNORECASE):
            return Intent.ASK_HELP

    for pattern in ASK_NUTRITION_PATTERNS:
        if re.search(pattern, msg, re.IGNORECASE):
            return Intent.ASK_NUTRITION

    for pattern in SYMPTOM_PATTERNS:
        if re.search(pattern, msg, re.IGNORECASE):
            return Intent.SYMPTOM_REPORT

    return Intent.UNKNOWN
