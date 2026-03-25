"""Training plan library and session lookup."""

import os
from datetime import date, datetime

from garmin_coach.models import SessionClass


PLAN_START_DATE = os.getenv("GARMIN_PLAN_START_DATE", "2026-01-01")


# Replace this with your actual 14-week plan.
# Format: PLAN_LIBRARY[week_number][weekday] = "session description"
# weekday: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
PLAN_LIBRARY: dict[int, dict[int, str]] = {
    1: {
        0: "5 km easy",
        1: "5 km easy",
        2: "5 km easy",
        3: "5 km easy",
        4: "Rest",
        5: "5 km easy",
        6: "8 km easy",
    },
    2: {
        0: "Rest",
        1: "5 km easy",
        2: "5 km easy",
        3: "5 km easy",
        4: "Rest",
        5: "5 km easy",
        6: "10 km easy",
    },
    3: {
        0: "Rest",
        1: "6 km easy",
        2: "6 km easy",
        3: "6 km easy",
        4: "Rest",
        5: "6 km easy",
        6: "12 km easy",
    },
    4: {
        0: "Rest",
        1: "6 km easy",
        2: "6 km easy",
        3: "6 km easy",
        4: "Rest",
        5: "6 km easy",
        6: "14 km easy",
    },
    5: {
        0: "Rest",
        1: "7 km easy",
        2: "7 km easy",
        3: "7 km easy",
        4: "Rest",
        5: "7 km easy",
        6: "16 km easy",
    },
    6: {
        0: "Rest",
        1: "7 km easy",
        2: "7 km easy",
        3: "7 km easy",
        4: "Rest",
        5: "7 km easy",
        6: "18 km easy",
    },
    7: {
        0: "Rest",
        1: "8 km easy",
        2: "8 km easy",
        3: "8 km easy",
        4: "Rest",
        5: "8 km easy",
        6: "20 km easy",
    },
    8: {
        0: "Rest",
        1: "8 km easy",
        2: "8 km easy",
        3: "8 km easy",
        4: "Rest",
        5: "8 km easy",
        6: "22 km easy",
    },
    9: {
        0: "Rest",
        1: "9 km easy",
        2: "9 km easy",
        3: "9 km easy",
        4: "Rest",
        5: "9 km easy",
        6: "24 km easy",
    },
    10: {
        0: "Rest",
        1: "9 km easy",
        2: "9 km easy",
        3: "9 km easy",
        4: "Rest",
        5: "9 km easy",
        6: "26 km easy",
    },
    11: {
        0: "Rest",
        1: "10 km easy",
        2: "10 km easy",
        3: "10 km easy",
        4: "Rest",
        5: "10 km easy",
        6: "20 km easy",
    },
    12: {
        0: "Rest",
        1: "8 km easy",
        2: "8 km easy",
        3: "8 km easy",
        4: "Rest",
        5: "8 km easy",
        6: "15 km easy",
    },
    13: {
        0: "Rest",
        1: "5 km easy",
        2: "5 km easy",
        3: "5 km easy",
        4: "Rest",
        5: "5 km easy",
        6: "10 km easy",
    },
    14: {
        0: "Rest",
        1: "5 km easy",
        2: "Rest",
        3: "Rest",
        4: "Rest",
        5: "Rest",
        6: "Race day!",
    },
}


def get_week_number(target_date: str) -> int:
    start = date.fromisoformat(PLAN_START_DATE)
    current = date.fromisoformat(target_date)
    delta_days = (current - start).days
    if delta_days < 0:
        return 1
    return min(14, (delta_days // 7) + 1)


def get_planned_session(target_date: str) -> tuple[int, str]:
    weekday = datetime.fromisoformat(target_date).weekday()
    week = get_week_number(target_date)
    return week, PLAN_LIBRARY.get(week, PLAN_LIBRARY[1]).get(weekday, "Easy run")


def get_week_brief(week: int) -> str:
    briefs = {
        1: "Base building — focus on consistency.",
        2: "Volume builds — keep easy days easy.",
        3: "Aerobic base — consistency matters most.",
        4: "Cutback week — recover and maintain form.",
        5: "Build continues — easy runs stay easy.",
        6: "Building endurance — watch for fatigue.",
        7: "Peak build — recovery is key.",
        8: "Recovery phase — absorb the training.",
        9: "Strength build — the hard weeks are coming.",
        10: "Peak volume — manage fatigue carefully.",
        11: "Taper begins — reduce, don't stop.",
        12: "Taper deepens — trust your training.",
        13: "Pre-race — very light, stay fresh.",
        14: "Race week — you're ready.",
    }
    return briefs.get(week, "Stay consistent.")


def classify_session(planned: str) -> SessionClass:
    lower = planned.lower()
    if any(w in lower for w in ("threshold", "interval", "fartlek", "tempo")):
        return SessionClass.THRESHOLD
    if any(w in lower for w in ("mp", "marathon-pace", "marathon")):
        return SessionClass.MP
    if "long run" in lower:
        return SessionClass.LONG_RUN
    if "aerobic" in lower or "medium-long" in lower:
        return SessionClass.AEROBIC
    if "easy" in lower:
        return SessionClass.EASY
    if "recovery" in lower or "shakedown" in lower:
        return SessionClass.RECOVERY
    if any(w in lower for w in ("rest", "off", "walk")):
        return SessionClass.REST
    if "strength" in lower:
        return SessionClass.STRENGTH_SUPPORTED
    return SessionClass.UNKNOWN


def get_session_purpose(planned: str) -> str:
    lower = planned.lower()
    if "threshold" in lower or "tempo" in lower:
        return "Build lactate threshold. Sustain a comfortably hard pace."
    if "mp" in lower or "marathon" in lower:
        return "Practice marathon pace. Efficiency over speed."
    if "long run" in lower:
        return "Build endurance. Fuel strategy and mental resilience."
    if "aerobic" in lower or "medium-long" in lower:
        return "Build aerobic base. Recovery-friendly volume."
    if "easy" in lower or "recovery" in lower:
        return "Recovery run. Keep the rhythm, stay fresh."
    if any(w in lower for w in ("rest", "off")):
        return "Rest day. Recovery is training."
    return "Stay consistent. Don't break the chain."
