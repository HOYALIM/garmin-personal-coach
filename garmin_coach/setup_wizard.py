"""CLI setup wizard — interactive profile configuration."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from garmin_coach.profile_manager import (
    AICoachConfig,
    AIFlexibility,
    AIProvider,
    AITone,
    DietaryStyle,
    FitnessLevel,
    FitnessData,
    GarminConfig,
    GarMiniAuthMethod,
    NutritionCoachingStyle,
    NutritionPreferences,
    NotificationMethod,
    ProfileData,
    ProfileManager,
    ScheduleConfig,
    Sport,
    UserProfile,
)
from garmin_coach.wizard.oauth import setup_strava_oauth


def ask(prompt: str, default: str = "") -> str:
    val = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return val or default


def ask_int(prompt: str, default: int, lo: int, hi: int) -> int:
    while True:
        raw = ask(prompt, str(default))
        try:
            val = int(raw)
            if lo <= val <= hi:
                return val
            print(f"Must be between {lo}–{hi}")
        except ValueError:
            print("Enter a number")


def ask_float(prompt: str, default: float, lo: float, hi: float) -> float:
    while True:
        raw = ask(prompt, str(default))
        try:
            val = float(raw)
            if lo <= val <= hi:
                return val
            print(f"Must be between {lo}–{hi}")
        except ValueError:
            print("Enter a number")


def ask_bool(prompt: str, default: bool) -> bool:
    raw = ask(f"{prompt} (y/N)", "y" if default else "n").lower()
    return raw in ("y", "yes")


def ask_choice(prompt: str, options: list[str], default_idx: int = 0) -> str:
    print(f"{prompt}")
    for i, opt in enumerate(options):
        marker = " (default)" if i == default_idx else ""
        print(f"  [{i + 1}] {opt}{marker}")
    while True:
        raw = ask("Choice", str(default_idx + 1))
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        print(f"Enter 1–{len(options)}")


def ask_multi_choice(prompt: str, options: list[str]) -> list[str]:
    print(f"{prompt} (comma-separated, e.g. 1,3)")
    for i, opt in enumerate(options):
        print(f"  [{i + 1}] {opt}")
    while True:
        raw = ask("Select")
        try:
            indices = [int(x.strip()) - 1 for x in raw.split(",")]
            selected = [options[i] for i in indices if 0 <= i < len(options)]
            if selected:
                return selected
        except ValueError:
            pass
        print("Enter numbers like 1,3")


def test_garth_login(email: str) -> bool:
    try:
        result = subprocess.run(
            ["garth", "whoami"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def run() -> UserProfile:
    print("\n" + "=" * 60)
    print("  Garmin Personal Coach — Setup Wizard")
    print("=" * 60)
    print("\nAnswer the questions below to configure your coach.\n")

    print("─── 1. About You ────────────────────────────────────")
    name = ask("Name")
    age = ask_int("Age", 30, 10, 100)
    sex_raw = ask_choice(
        "Sex",
        ["male", "female", "other"],
        default_idx=0,
    )
    height = ask_float("Height (cm)", 170.0, 100.0, 220.0)
    weight = ask_float("Weight (kg)", 70.0, 30.0, 200.0)

    print("\n─── 2. Sports ─────────────────────────────────────────")
    sports_raw = ask_multi_choice(
        "Which sports are you training for?",
        ["running", "cycling", "swimming", "triathlon"],
    )
    sports = [Sport(s) for s in sports_raw]
    primary = ask_choice(
        "Primary sport",
        sports_raw,
        default_idx=0,
    )

    print("\n─── 3. Goal Event ────────────────────────────────────")
    goal_event = ask("Target event name (e.g. Seoul Marathon 2026)")
    goal_date = ask("Target date (YYYY-MM-DD)", "")

    level_raw = ask_choice(
        "Current fitness level",
        ["beginner", "intermediate", "advanced"],
        default_idx=1,
    )
    available_days = ask_int("Training days per week", 5, 1, 7)
    max_hours = ask_float("Max training hours per week", 10.0, 1.0, 30.0)

    profile_data = ProfileData(
        name=name,
        age=age,
        height_cm=height,
        weight_kg=weight,
        sports=sports,
        primary_sport=Sport(primary),
        goal_event=goal_event,
        goal_date=goal_date,
        fitness_level=FitnessLevel(level_raw),
        available_days=available_days,
        max_weekly_hours=max_hours,
    )

    print("\n─── 4. Fitness Assessment ────────────────────────────")
    print("(Press Enter for 'auto' to fetch from Garmin, or 'unknown')")

    def race_time(q: str, default: str = "") -> str:
        val = ask(f"Recent {q} time (e.g. 25:00 for 5K)", default)
        return val.strip() or "unknown"

    fitness_data = FitnessData(
        recent_5k=race_time("5K", "unknown"),
        recent_10k=race_time("10K", "unknown"),
        recent_half=race_time("Half marathon", "unknown"),
        recent_marathon=race_time("Marathon", "unknown"),
        resting_hr=ask_int("Resting HR (bpm, skip if unknown)", 50, 30, 120),
        max_hr=ask_int("Max HR (bpm, skip if unknown)", 190, 120, 220),
        cycling_ftp_w=ask_int("FTP in Watts (cycling, 0 if N/A)", 0, 0, 500),
        swim_100m_pace=ask("100m swim pace (e.g. 1:50)", "unknown"),
        fetch_race_times=ask_bool("Fetch race times from Garmin automatically?", True),
        fetch_hr_baseline=ask_bool("Fetch HR baseline from Garmin automatically?", True),
        fetch_cycling_data=ask_bool("Fetch cycling data from Garmin?", "cycling" in sports_raw),
        fetch_swimming_data=ask_bool("Fetch swimming data from Garmin?", "swimming" in sports_raw),
    )

    print("\n─── 5. Garmin Connection ──────────────────────────────")
    print("Run 'garth login your@email.com' in another terminal, then come back.")
    garmin_email = ask("Garmin email (for reference)")
    garmin_connected = test_garth_login(garmin_email)
    if garmin_connected:
        print("✓ garth login verified")
    else:
        print("⚠ garth not logged in yet — run 'garth login email' first")

    garmin_data = GarminConfig(
        email=garmin_email or None,
        connected=garmin_connected,
        auth_method=GarMiniAuthMethod.GARTH,
    )

    print("\n─── 6. Schedule ──────────────────────────────────────")
    print("Configure when each coaching module runs.")

    def schedule_job(name: str, default_time: str, default_enabled: bool = True) -> dict:
        enabled = ask_bool(f"Enable {name}?", default_enabled)
        time_str = ask("Time (HH:MM)", default_time) if enabled else "00:00"
        return {"enabled": enabled, "time": time_str}

    schedule_data = ScheduleConfig(
        morning_checkin=schedule_job("Morning precheck", "06:00"),
        final_check=schedule_job("Final check (pre-workout)", "06:30"),
        evening_checkin=schedule_job("Evening check-in", "22:00"),
        weekly_review={
            "enabled": ask_bool("Enable weekly review?", True),
            "day": ask_choice(
                "Weekly review day",
                [
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                ],
                default_idx=6,
            ),
            "time": ask("Weekly review time (HH:MM)", "21:00"),
        },
    )

    print("\n─── 7. AI Coach ──────────────────────────────────────")
    ai_provider = AIProvider.AUTO
    ai_model = None
    ai_data = AICoachConfig(
        enabled=ask_bool("Enable AI coach (advice, plan modification)?", True),
        flexibility=AIFlexibility.MODERATE,
        tone=AITone.ENCOURAGING,
        can_modify_plan=True,
        notification_method=NotificationMethod.PRINT,
        notification_target="",
    )

    if ai_data.enabled:
        ai_provider = AIProvider(
            ask_choice(
                "AI provider",
                ["auto", "openai", "anthropic", "gemini"],
                default_idx=0,
            )
        )
        ai_model = (
            ask(
                "AI model (leave blank for provider default)",
                "",
            ).strip()
            or None
        )
        api_key_input = ask(
            "AI API key (leave blank to use provider environment variable)",
            "",
        ).strip()
        ai_data.api_key = api_key_input or None
        ai_data.flexibility = AIFlexibility(
            ask_choice(
                "AI flexibility",
                ["conservative", "moderate", "flexible"],
                default_idx=1,
            )
        )
        ai_data.tone = AITone(
            ask_choice(
                "AI coaching tone",
                ["encouraging", "direct", "analytical", "motivational"],
                default_idx=0,
            )
        )
        ai_data.can_modify_plan = ask_bool("Allow AI to modify your training plan?", True)
        ai_data.notification_method = NotificationMethod(
            ask_choice(
                "Notification method",
                ["print", "notify-send", "telegram", "discord"],
                default_idx=0,
            )
        )
        ai_data.notification_target = ask(
            "Notification target (channel/chat ID, skip for print)", ""
        )

    ai_data.provider = ai_provider
    ai_data.model = ai_model

    print("\n─── 8. Nutrition Preferences (Optional) ─────────────────")
    nutrition_data = NutritionPreferences(
        weight_goal=ask_choice(
            "Weight / body-composition goal",
            ["maintain", "lose", "gain"],
            default_idx=0,
        ),
        dietary_style=ask_choice(
            "Dietary style",
            ["omnivore", "vegetarian", "vegan", "other"],
            default_idx=0,
        ),
        food_restrictions=[
            r.strip()
            for r in ask(
                "Food restrictions / avoidances (comma-separated, optional)",
                "",
            ).split(",")
            if r.strip()
        ],
        coaching_style=ask_choice(
            "Nutrition advice style",
            ["brief", "detailed", "macros"],
            default_idx=0,
        ),
    )

    if ask_bool("Connect Strava now?", False):
        setup_strava_oauth()

    user_profile = UserProfile(
        profile=profile_data,
        fitness=fitness_data,
        garmin=garmin_data,
        schedule=schedule_data,
        ai_coach=ai_data,
        nutrition=nutrition_data,
    )

    print("\n─── Validation ────────────────────────────────────────")
    pm = ProfileManager()
    errors = pm.validate(user_profile)
    if errors:
        print("⚠ Validation warnings:")
        for e in errors:
            print(f"  - {e}")
        if not ask_bool("Save anyway?", False):
            print("Aborted.")
            sys.exit(1)

    pm.save(user_profile)
    print(f"\n✓ Profile saved to {pm.config_path}")
    print("\nRun 'garmin-coach status' to check your training status.")
    print("Run 'garmin-coach setup' to reconfigure.")
    print("Run 'garmin-coach-telegram' for mobile notifications.")

    return user_profile


if __name__ == "__main__":
    run()
