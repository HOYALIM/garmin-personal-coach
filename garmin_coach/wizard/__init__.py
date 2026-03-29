import sys
import os
from datetime import datetime
from typing import Optional

import yaml

from garmin_coach.profile_manager import (
    ProfileManager,
    ProfileData,
    FitnessData,
    GarminConfig,
    AICoachConfig,
    ScheduleConfig,
    UserProfile,
    Sport,
    FitnessLevel,
    Sex,
    AIFlexibility,
    AITone,
)


CONFIG_DIR = os.path.expanduser("~/.config/garmin_coach")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.yaml")


def prompt_non_empty(prompt_text: str) -> str:
    while True:
        value = input(prompt_text).strip()
        if value:
            return value
        print("This field is required.")


def prompt_yes_no(prompt_text: str, default: bool = False) -> bool:
    default_str = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt_text} [{default_str}]: ").strip().lower()
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        if not value:
            return default
        print("Please answer y or n.")


def prompt_choice(prompt_text: str, options: list, default: int = 0) -> str:
    for i, opt in enumerate(options):
        print(f"  {i + 1}. {opt}")
    while True:
        value = input(f"{prompt_text} [default: {default + 1}]: ").strip()
        if not value:
            return options[default]
        try:
            idx = int(value) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        print(f"Please enter a number 1-{len(options)}.")


def prompt_number(
    prompt_text: str,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None,
    default: Optional[int] = None,
) -> Optional[int]:
    default_str = f" (default: {default})" if default is not None else ""
    while True:
        value = input(f"{prompt_text}{default_str}: ").strip()
        if not value and default is not None:
            return default
        try:
            num = int(value)
            if min_val is not None and num < min_val:
                print(f"Must be at least {min_val}.")
                continue
            if max_val is not None and num > max_val:
                print(f"Must be at most {max_val}.")
                continue
            return num
        except ValueError:
            print("Please enter a valid number.")


def prompt_optional(prompt_text: str, default: Optional[str] = None) -> Optional[str]:
    value = input(f"{prompt_text}").strip()
    if not value:
        return default
    return value


def _check_garmin_connection() -> bool:
    try:
        import garth

        GARTH_HOME = os.getenv("GARTH_HOME", "~/.garth")
        garth.resume(os.path.expanduser(GARTH_HOME))
        garth.connectapi("/usersettings", max_retries=1)
        return True
    except Exception:
        return False


def _migrate_legacy_config(config: dict) -> dict:
    """Migrate legacy flat config to ProfileManager nested format."""
    if "profile" in config:
        return config

    return {
        "version": "1.0",
        "created_at": config.get("setup_date", datetime.now().isoformat()),
        "updated_at": datetime.now().isoformat(),
        "profile": {
            "name": config.get("name", ""),
            "age": config.get("age", 30),
            "sex": config.get("sex", "other"),
            "height_cm": config.get("height_cm", 170.0),
            "weight_kg": config.get("weight_kg", 70.0),
            "sports": config.get("sports", ["running"]),
            "goal_event": config.get("target_event", ""),
            "goal_date": config.get("race_date", ""),
            "fitness_level": config.get("fitness_level", "intermediate"),
            "available_days": config.get("training_days_per_week", 4),
        },
        "fitness": {
            "fetch_race_times": True,
            "fetch_hr_baseline": True,
        },
        "garmin": {
            "connected": config.get("garmin_connected", False),
        },
        "schedule": config.get(
            "schedule",
            {
                "morning_checkin": {"enabled": True, "time": "06:00"},
                "final_check": {"enabled": True, "time": "06:30"},
                "evening_checkin": {"enabled": True, "time": "22:00"},
                "weekly_review": {"enabled": True, "day": "sunday", "time": "21:00"},
            },
        ),
        "ai_coach": config.get(
            "ai",
            {
                "enabled": False,
                "tone": "encouraging",
                "flexibility": "moderate",
            },
        ),
    }


def load_config() -> dict:
    """Load config, migrating legacy format if needed."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f) or {}
        if "profile" not in config:
            config = _migrate_legacy_config(config)
            with open(CONFIG_FILE, "w") as f:
                yaml.safe_dump(config, f, default_flow_style=False)
        return config
    except Exception:
        return {}


def save_config(config: dict):
    """Save config in ProfileManager format."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)
    os.chmod(CONFIG_FILE, 0o600)


def run_wizard():
    print("\n=== Garmin Personal Coach Setup ===\n")

    pm = ProfileManager()
    existing_profile = pm.load()

    if existing_profile:
        print("Setup already completed. Updating configuration...\n")

    print("--- About You ---")
    name = prompt_non_empty("Your name: ")
    age = prompt_number("Age", 10, 100, default=30)
    sex_str = prompt_choice("Sex", ["male", "female", "other"], default=0)
    height = prompt_number("Height (cm)", 100, 250, default=170)
    weight = prompt_number("Weight (kg)", 30, 200, default=70)

    print("\n--- Sports ---")
    print("Select sports you do (space-separated numbers):")
    sports_options = ["running", "cycling", "swimming", "triathlon"]
    for i, s in enumerate(sports_options):
        print(f"  {i + 1}. {s}")
    while True:
        sel = input("Sports [default: 1]: ").strip()
        if not sel:
            selected = [Sport.RUNNING]
            break
        try:
            indices = [int(x) - 1 for x in sel.split()]
            selected = [Sport(sports_options[i]) for i in indices if 0 <= i < len(sports_options)]
            if selected:
                break
        except (ValueError, IndexError):
            pass
        print("Please enter numbers like: 1 2 3")

    print("\n--- Goals ---")
    target_event = input("Target event (e.g., 'Marathon', 'Ironman') [optional]: ").strip()
    race_date_str = input("Race date (YYYY-MM-DD) [optional]: ").strip()
    race_date = None
    if race_date_str:
        try:
            race_date = datetime.strptime(race_date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            print("Invalid date format, skipping.")

    fitness_level_str = prompt_choice(
        "Fitness level", ["beginner", "intermediate", "advanced"], default=1
    )
    available_days = prompt_number("Training days per week", 1, 7, default=4)

    print("\n--- Garmin Connection ---")
    garmin_connected = _check_garmin_connection()
    if garmin_connected:
        print("✅ Garmin account connected!")
    else:
        print("⚠️  Garmin not connected. Run 'garth login your@email.com' after setup.")

    print("\n--- Schedule ---")
    morning_time = input("Morning check-in time (HH:MM) [default: 06:00]: ").strip() or "06:00"
    evening_time = input("Evening check-in time (HH:MM) [default: 22:00]: ").strip() or "22:00"
    enable_morning = prompt_yes_no("Enable morning check-in?", default=True)
    enable_evening = prompt_yes_no("Enable evening check-in?", default=True)
    enable_weekly = prompt_yes_no("Enable weekly review?", default=True)

    print("\n--- AI Coach (Optional) ---")
    enable_ai = prompt_yes_no("Enable AI coach?", default=False)

    ai_api_key = None
    ai_tone = AITone.ENCOURAGING
    ai_flexibility = AIFlexibility.MODERATE

    if enable_ai:
        print("\nTo use AI coaching, you need an API key:")
        print("  - OpenAI: https://platform.openai.com/api-keys")
        print("  - Anthropic: https://console.anthropic.com/settings/keys")
        api_key_input = input(
            "API key (will use env vars OPENAI_API_KEY or ANTHROPIC_API_KEY if empty): "
        ).strip()

        if api_key_input:
            ai_api_key = api_key_input
            print("API key saved securely.")

        print("\nAI coaching style:")
        ai_tone_str = prompt_choice(
            "AI response tone", ["encouraging", "direct", "analytical"], default=0
        )
        ai_tone = AITone(ai_tone_str)

        ai_flexibility_str = prompt_choice(
            "AI flexibility", ["conservative", "moderate", "flexible"], default=1
        )
        ai_flexibility = AIFlexibility(ai_flexibility_str)
    else:
        print(
            "\nSkipping AI setup. You can enable it later by setting OPENAI_API_KEY or ANTHROPIC_API_KEY."
        )

    profile = UserProfile(
        profile=ProfileData(
            name=name,
            age=age,
            sex=Sex(sex_str),
            height_cm=float(height),
            weight_kg=float(weight),
            sports=selected,
            goal_event=target_event or "",
            goal_date=race_date or "",
            fitness_level=FitnessLevel(fitness_level_str),
            available_days=available_days,
        ),
        fitness=FitnessData(),
        garmin=GarminConfig(
            connected=garmin_connected,
        ),
        schedule=ScheduleConfig(
            morning_checkin={"enabled": enable_morning, "time": morning_time},
            evening_checkin={"enabled": enable_evening, "time": evening_time},
            weekly_review={"enabled": enable_weekly, "day": "sunday", "time": "21:00"},
        ),
        ai_coach=AICoachConfig(
            enabled=enable_ai,
            api_key=ai_api_key,
            tone=ai_tone,
            flexibility=ai_flexibility,
        ),
    )

    pm.save(profile)
    print("\n--- Setup Complete! ---")
    print(f"Config saved to: {CONFIG_FILE}")
    print("\nNext steps:")
    if not garmin_connected:
        print("  1. Run 'garth login your@email.com' to connect Garmin")
    print("  2. Run 'garmin-coach status' to check your training status")
    print("  3. (Optional) Set up Telegram bot for mobile notifications")
    print()


if __name__ == "__main__":
    run_wizard()
