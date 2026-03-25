"""CLI dispatcher — routes messages to coaching flows."""

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def run_precheck(target_date: str) -> int:
    print(f"[dispatcher] Running precheck for {target_date}")
    return subprocess.run(
        [
            sys.executable,
            "morning_checkin.py",
            "--phase",
            "precheck",
            "--date",
            target_date,
        ],
        cwd=SCRIPT_DIR,
    ).returncode


def run_final_check(target_date: str) -> int:
    print(f"[dispatcher] Running final check for {target_date}")
    return subprocess.run(
        [sys.executable, "final_check.py", "--date", target_date],
        cwd=SCRIPT_DIR,
    ).returncode


def run_workout_review(target_date: str) -> int:
    print(f"[dispatcher] Running workout review for {target_date}")
    return subprocess.run(
        [sys.executable, "workout_review.py", "--date", target_date],
        cwd=SCRIPT_DIR,
    ).returncode


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Garmin Coach dispatcher")
    p.add_argument("--message", default="", help="User message")
    p.add_argument("--precheck", action="store_true")
    p.add_argument("--final", action="store_true")
    p.add_argument("--workout", action="store_true")
    p.add_argument("--date", default=date.today().isoformat())
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.precheck:
        sys.exit(run_precheck(args.date))
    if args.final:
        sys.exit(run_final_check(args.date))
    if args.workout:
        sys.exit(run_workout_review(args.date))
    if args.message:
        from garmin_coach.triggers import detect_trigger, TriggerType

        trigger = detect_trigger(args.message)
        if trigger and trigger.trigger_type == TriggerType.WAKE:
            sys.exit(run_final_check(args.date))
        if trigger and trigger.trigger_type == TriggerType.WORKOUT_COMPLETE:
            sys.exit(run_workout_review(args.date))
        print(f"No trigger matched: {args.message!r}")
        sys.exit(1)
    print("Usage: dispatch.py --message '일어났어' | --precheck | --final | --workout")
    sys.exit(1)


if __name__ == "__main__":
    main()
