"""Update checker for garmin-personal-coach."""

import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

from garmin_coach._version import __version__


GITHUB_API = "https://api.github.com/repos/HOYALIM/garmin-personal-coach/releases/latest"
CACHE_FILE = os.path.expanduser("~/.config/garmin_coach/.update_cache")
CHECK_INTERVAL = timedelta(hours=6)


@dataclass
class UpdateInfo:
    current: str
    latest: str
    url: str
    is_update_available: bool
    release_notes: Optional[str] = None


def _read_cache() -> Optional[dict]:
    try:
        if os.path.exists(CACHE_FILE):
            mtime = os.path.getmtime(CACHE_FILE)
            if datetime.now() - datetime.fromtimestamp(mtime) < CHECK_INTERVAL:
                with open(CACHE_FILE) as f:
                    import json

                    return json.load(f)
    except Exception:
        pass
    return None


def _write_cache(data: dict):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            import json

            json.dump(data, f)
    except Exception:
        pass


def check_for_updates(force: bool = False) -> UpdateInfo:
    current = __version__

    if not force:
        cached = _read_cache()
        if cached:
            return UpdateInfo(
                current=current,
                latest=cached.get("tag_name", current),
                url=cached.get("html_url", ""),
                is_update_available=_compare_versions(current, cached.get("tag_name", current)) < 0,
                release_notes=cached.get("body"),
            )

    if requests is None:
        return UpdateInfo(
            current=current,
            latest=current,
            url="",
            is_update_available=False,
        )

    try:
        response = requests.get(
            GITHUB_API,
            headers={"Accept": "application/vnd.github+json"},
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            _write_cache(data)
            latest = data.get("tag_name", current).lstrip("v")
            return UpdateInfo(
                current=current,
                latest=latest,
                url=data.get("html_url", ""),
                is_update_available=_compare_versions(current, latest) < 0,
                release_notes=data.get("body"),
            )
    except Exception:
        pass

    return UpdateInfo(
        current=current,
        latest=current,
        url="",
        is_update_available=False,
    )


def _compare_versions(current: str, latest: str) -> int:
    try:
        cur_parts = tuple(int(x) for x in current.split("."))
        lat_parts = tuple(int(x) for x in latest.split("."))
        if cur_parts < lat_parts:
            return -1
        elif cur_parts > lat_parts:
            return 1
        return 0
    except (ValueError, AttributeError):
        return 0


def get_update_message(info: UpdateInfo) -> Optional[str]:
    if not info.is_update_available:
        return None

    lines = [
        f"🔔 Update available: {info.current} → {info.latest}",
        f"   {info.url}",
    ]

    return "\n".join(lines)
