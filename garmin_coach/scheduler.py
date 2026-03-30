"""Scheduler — runs coaching jobs at user-configured times."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from datetime import datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from garmin_coach.activity_fetch import resume_garth
from garmin_coach.logging_config import log_error, log_info, log_warning


_shutdown_requested = False


def _request_shutdown(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    log_warning(f"Shutdown signal received ({signum}), finishing current job...")


def _register_signal_handlers():
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)


def _is_shutdown_requested() -> bool:
    return _shutdown_requested


from garmin_coach.profile_manager import ProfileManager, ScheduleConfig


SCRIPT_DIR = Path(__file__).resolve().parent


JOBS = {
    "morning_checkin": "morning_checkin.py",
    "final_check": "final_check.py",
    "evening_checkin": "evening_checkin.py",
    "weekly_review": "weekly_review.py",
}


def parse_time(time_str: str) -> time:
    h, m = time_str.split(":")
    return time(int(h), int(m))


def should_run_now(job_time: time, margin_minutes: int = 5) -> bool:
    now = datetime.now()
    current = now.time()
    target = job_time
    diff = (current.hour * 60 + current.minute) - (target.hour * 60 + target.minute)
    return -margin_minutes <= diff <= margin_minutes


def run_job(name: str) -> int:
    if _is_shutdown_requested():
        log_warning(f"Scheduler: Skipping job {name} due to shutdown")
        return -1
    script = SCRIPT_DIR / JOBS[name]
    log_info(f"Scheduler: Running {name}", job=name, time=f"{datetime.now():%H:%M}")
    print(f"[scheduler] Running {name} at {datetime.now():%H:%M}")
    return subprocess.run([sys.executable, str(script)]).returncode


def dispatch_scheduled() -> None:
    _register_signal_handlers()
    pm = ProfileManager()
    profile = pm.load()
    if not profile:
        log_error("Scheduler: No profile found")
        print("[scheduler] No profile. Run setup_wizard first.")
        sys.exit(1)

    if not resume_garth():
        log_warning("Scheduler: No Garmin session available at startup")
        print("[scheduler] Warning: No Garmin session. Some jobs may be degraded.")

    schedule: ScheduleConfig = profile.schedule
    now = datetime.now()

    for job_name, job_config in [
        ("morning_checkin", schedule.morning_checkin),
        ("final_check", schedule.final_check),
        ("evening_checkin", schedule.evening_checkin),
    ]:
        if _is_shutdown_requested():
            log_info("Scheduler: Shutdown requested, stopping dispatch loop")
            break
        if not job_config.get("enabled", False):
            continue
        job_time = parse_time(job_config.get("time", "00:00"))
        if should_run_now(job_time):
            run_job(job_name)

    wr = schedule.weekly_review
    if wr.get("enabled", False):
        today_name = now.strftime("%A").lower()
        if today_name == wr.get("day", "sunday"):
            wr_time = parse_time(wr.get("time", "21:00"))
            if should_run_now(wr_time) and not _is_shutdown_requested():
                log_info("Scheduler: Running weekly review")
                run_job("weekly_review")

    log_info("Scheduler: Dispatch complete")
    print("[scheduler] Done. No jobs due right now.")


def install_cron(profile_path: Path | None = None) -> str:
    profile_path = profile_path or ProfileManager().config_path
    cron_line = (
        f"*/5 * * * * "
        f"cd {SCRIPT_DIR} && "
        f"{sys.executable} scheduler.py --dispatch "
        f"--profile {profile_path} "
        f">>/tmp/garmin_coach_cron.log 2>&1\n"
    )
    return cron_line


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Garmin Coach scheduler")
    p.add_argument("--dispatch", action="store_true", help="Run due jobs")
    p.add_argument("--install-cron", action="store_true", help="Print cron line")
    p.add_argument("--profile", default=None)
    args = p.parse_args()

    if args.install_cron:
        print(install_cron(Path(args.profile) if args.profile else None))
        print("\nAdd the above line to your crontab:")
        print("  crontab -e")
    elif args.dispatch:
        dispatch_scheduled()
    else:
        print("Usage:")
        print("  scheduler.py --dispatch        Run any jobs due now")
        print("  scheduler.py --install-cron    Print cron setup line")


if __name__ == "__main__":
    main()
