import json
import os
from datetime import datetime, timedelta
from typing import Optional


DATA_DIR = os.path.expanduser("~/.config/garmin_coach")
HYDRATION_FILE = os.path.join(DATA_DIR, "hydration.json")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_hydration_data() -> dict:
    ensure_data_dir()
    if os.path.exists(HYDRATION_FILE):
        try:
            with open(HYDRATION_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_hydration_data(data: dict):
    ensure_data_dir()
    with open(HYDRATION_FILE, "w") as f:
        json.dump(data, f, indent=2)


def log_water(amount_ml: int, timestamp: datetime = None):
    if timestamp is None:
        timestamp = datetime.now()
    date_key = timestamp.strftime("%Y-%m-%d")

    data = load_hydration_data()
    if date_key not in data:
        data[date_key] = {"entries": [], "total_ml": 0}

    data[date_key]["entries"].append(
        {
            "time": timestamp.strftime("%H:%M"),
            "amount_ml": amount_ml,
        }
    )
    data[date_key]["total_ml"] += amount_ml

    save_hydration_data(data)


def get_today_intake() -> int:
    date_key = datetime.now().strftime("%Y-%m-%d")
    data = load_hydration_data()
    return data.get(date_key, {}).get("total_ml", 0)


def get_daily_intake(date: datetime) -> int:
    date_key = date.strftime("%Y-%m-%d")
    data = load_hydration_data()
    return data.get(date_key, {}).get("total_ml", 0)


def get_weekly_average() -> float:
    today = datetime.now()
    total = 0
    days = 0
    for i in range(7):
        day = today - timedelta(days=i)
        intake = get_daily_intake(day)
        if intake > 0:
            total += intake
            days += 1
    return total / days if days > 0 else 0


def check_hydration_status(target_ml: int) -> str:
    current = get_today_intake()
    if current >= target_ml:
        return "goal_reached"
    percentage = (current / target_ml) * 100
    if percentage >= 75:
        return "almost_there"
    elif percentage >= 50:
        return "half_way"
    elif percentage >= 25:
        return "getting_started"
    else:
        return "just_started"


def get_hydration_summary(target_ml: int = None) -> dict:
    today_intake = get_today_intake()
    if target_ml is None:
        target_ml = 2500
    status = check_hydration_status(target_ml)
    weekly_avg = get_weekly_average()

    return {
        "today_ml": today_intake,
        "target_ml": target_ml,
        "percentage": round((today_intake / target_ml) * 100, 1),
        "status": status,
        "weekly_average_ml": round(weekly_avg, 0),
    }


def reset_daily():
    date_key = datetime.now().strftime("%Y-%m-%d")
    data = load_hydration_data()
    if date_key in data:
        data[date_key] = {"entries": [], "total_ml": 0}
        save_hydration_data(data)
