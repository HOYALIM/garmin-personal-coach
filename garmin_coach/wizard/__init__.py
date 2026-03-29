import sys
import os
from datetime import datetime
from typing import Optional

import yaml


CONFIG_DIR = os.path.expanduser("~/.config/garmin_coach")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.yaml")


def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config() -> dict:
    ensure_config_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    return {}


def save_config(config: dict):
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)


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


def run_wizard():
    print("\n=== Garmin Personal Coach Setup ===\n")

    config = load_config()
    if config.get("setup_complete"):
        print("Setup already completed. Updating configuration...\n")

    print("--- About You ---")
    name = prompt_non_empty("Your name: ")
    age = prompt_number("Age", 10, 100, default=30)
    sex = prompt_choice("Sex", ["male", "female", "other"], default=0)
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
            selected = ["running"]
            break
        try:
            indices = [int(x) - 1 for x in sel.split()]
            selected = [sports_options[i] for i in indices if 0 <= i < len(sports_options)]
            if selected:
                break
        except ValueError:
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

    fitness_level = prompt_choice(
        "Fitness level", ["beginner", "intermediate", "advanced"], default=1
    )
    available_days = prompt_number("Training days per week", 1, 7, default=4)

    print("\n--- Garmin Connection ---")
    if _check_garmin_connection():
        print("✅ Garmin account connected!")
        garmin_connected = True
    else:
        print("⚠️  Garmin not connected. Run 'garth login your@email.com' after setup.")
        garmin_connected = False

    print("\n--- Schedule ---")
    morning_time = input("Morning check-in time (HH:MM) [default: 06:00]: ").strip() or "06:00"
    evening_time = input("Evening check-in time (HH:MM) [default: 22:00]: ").strip() or "22:00"
    enable_morning = prompt_yes_no("Enable morning check-in?", default=True)
    enable_evening = prompt_yes_no("Enable evening check-in?", default=True)
    enable_weekly = prompt_yes_no("Enable weekly review?", default=True)

    print("\n--- AI Coach (Optional) ---")
    print("Enable AI-powered personalized coaching?")
    enable_ai = prompt_yes_no("Enable AI coach?", default=False)

    ai_api_key = None
    ai_tone = "encouraging"
    ai_flexibility = "moderate"

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
        ai_tone = prompt_choice(
            "AI response tone", ["encouraging", "direct", "analytical"], default=0
        )
        ai_flexibility = prompt_choice(
            "AI flexibility", ["conservative", "moderate", "flexible"], default=1
        )
    else:
        print(
            "\nSkipping AI setup. You can enable it later by setting OPENAI_API_KEY or ANTHROPIC_API_KEY."
        )

    config.update(
        {
            "name": name,
            "age": age,
            "sex": sex,
            "height_cm": height,
            "weight_kg": weight,
            "sports": selected,
            "target_event": target_event or None,
            "race_date": race_date,
            "fitness_level": fitness_level,
            "training_days_per_week": available_days,
            "setup_complete": True,
            "setup_date": datetime.now().isoformat(),
            "garmin_connected": garmin_connected,
            "schedule": {
                "morning_time": morning_time,
                "evening_time": evening_time,
                "enable_morning": enable_morning,
                "enable_evening": enable_evening,
                "enable_weekly": enable_weekly,
            },
            "ai": {
                "enabled": enable_ai,
                "api_key": ai_api_key,
                "tone": ai_tone,
                "flexibility": ai_flexibility,
            },
        }
    )

    save_config(config)
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
