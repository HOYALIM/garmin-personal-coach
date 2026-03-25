"""Garmin write-back — feasibility and limited implementation.

STATUS:
  garth — read-only OAuth1/SSO session. No activity write methods.
  garminconnect — supports set_activity_name, create_manual_activity
    but requires separate email/password auth (not shared with garth).

WHAT WORKS:
  - garth connectapi GET — read activity details
  - garminconnect.set_activity_name() — rename activity (needs GARMIN_EMAIL+PASSWORD)
  - garminconnect.create_manual_activity() — create manual entry

WHAT DOESN'T WORK:
  - Direct activity note/description update via garth
  - Garmin Connect activity annotation via garth

RECOMMENDATION: Use local logs + calendar as durable truth.
"""

import os
from typing import Any


GARMIN_EMAIL = os.getenv("GARMIN_EMAIL", "")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD", "")


def _garminconnect_available() -> bool:
    try:
        import garminconnect

        return bool(GARMIN_EMAIL and GARMIN_PASSWORD)
    except ImportError:
        return False


def set_activity_name(activity_id: str, title: str) -> dict[str, Any]:
    if not _garminconnect_available():
        return {
            "success": False,
            "reason": "set GARMIN_EMAIL and GARMIN_PASSWORD",
            "activity_id": activity_id,
        }
    try:
        import garminconnect

        client = garminconnect.Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
        result = client.set_activity_name(activity_id, title)
        return {"success": True, "activity_id": activity_id, "new_name": title}
    except Exception as e:
        return {"success": False, "reason": str(e), "activity_id": activity_id}


GARMIN_WRITEBACK_STATUS = {
    "garth_read_only": True,
    "garminconnect_writeback": _garminconnect_available(),
    "activity_name_update": True,
    "activity_description_update": False,
    "manual_activity_create": True,
    "durable_source": ["data/training_logs/", "data/training_log_json/", "calendar"],
    "recommendation": "Use local md/json + calendar. Garmin app for manual annotation.",
}
