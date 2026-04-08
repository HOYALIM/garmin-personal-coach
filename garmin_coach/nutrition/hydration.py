import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from garmin_coach.models import SessionType
from garmin_coach.logging_config import log_warning


DATA_DIR = os.path.expanduser("~/.config/garmin_coach")
HYDRATION_FILE = os.path.join(DATA_DIR, "hydration.json")


@dataclass(slots=True)
class HydrationPlan:
    session_type: str
    pre: str
    during: str
    post: str
    electrolytes: str
    sodium_mg_per_liter: tuple[int, int]
    hot_weather_adjustment_ml_per_hour: int
    temperature_celsius: float | None
    rationale: str


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_hydration_data() -> dict:
    ensure_data_dir()
    if os.path.exists(HYDRATION_FILE):
        try:
            with open(HYDRATION_FILE) as f:
                return json.load(f)
        except Exception as e:
            log_warning(f"Failed to load hydration data: {e}")
            return {}
    return {}


def save_hydration_data(data: dict):
    ensure_data_dir()
    with open(HYDRATION_FILE, "w") as f:
        json.dump(data, f, indent=2)


def log_water(amount_ml: int, timestamp: Optional[datetime] = None):
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


def get_hydration_summary(target_ml: Optional[int] = None) -> dict:
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


def calculate_sweat_rate(
    pre_weight_kg: float,
    post_weight_kg: float,
    fluid_consumed_ml: float,
    duration_h: float,
) -> float:
    if duration_h <= 0:
        raise ValueError("duration_h must be positive")
    weight_loss_ml = (pre_weight_kg - post_weight_kg) * 1000
    return round((weight_loss_ml + fluid_consumed_ml) / duration_h, 1)


def _normalize_session_type(session_type: SessionType | str) -> str:
    if isinstance(session_type, SessionType):
        return session_type.value
    return str(session_type).lower()


def get_hydration_plan(
    session_type: SessionType | str,
    duration_min: int,
    temp_celsius: float | None = None,
) -> HydrationPlan:
    session = _normalize_session_type(session_type)
    hot_weather = temp_celsius is not None and temp_celsius >= 30
    long_session = duration_min >= 60
    extra_ml_hour = 250 if hot_weather else 0
    during_ml = "15-20분마다 150-250ml"
    if hot_weather:
        during_ml = "15-20분마다 250-350ml"

    electrolytes = "선택 사항"
    sodium = (0, 0)
    if long_session or hot_weather:
        electrolytes = "60분 이상 또는 고온 환경이므로 나트륨 보충 권장"
        sodium = (500, 1000)

    rationale = "기본 수분 계획"
    if session in {"long", "race"}:
        rationale = (
            "장거리/레이스 세션은 탈수와 나트륨 손실 위험이 높아 보수적으로 수분을 잡습니다."
        )
    elif hot_weather:
        rationale = "고온 환경에서는 같은 세션이라도 수분과 전해질 필요량을 상향합니다."

    return HydrationPlan(
        session_type=session,
        pre="운동 2-3시간 전 500ml, 직전 200-300ml",
        during=during_ml,
        post="체중 손실 1kg당 1.5L",
        electrolytes=electrolytes,
        sodium_mg_per_liter=sodium,
        hot_weather_adjustment_ml_per_hour=extra_ml_hour,
        temperature_celsius=temp_celsius,
        rationale=rationale,
    )
