"""CLI entry point for garmin-personal-coach."""

import sys
import argparse
from pprint import pprint

from garmin_coach._version import __version__
from garmin_coach.update_check import check_for_updates, get_update_message


def main():
    parser = argparse.ArgumentParser(prog="garmin-coach")
    parser.add_argument("--version", "-v", action="store_true", help="Show version")
    parser.add_argument("--check-updates", action="store_true", help="Check for updates")
    parser.add_argument("--no-update-check", action="store_true", help="Skip update check")
    parser.add_argument("command", nargs="*", help="Command to run")

    args, extra = parser.parse_known_args()

    if args.version:
        print(f"garmin-personal-coach {__version__}")
        return 0

    if args.check_updates:
        info = check_for_updates(force=True)
        if info.is_update_available:
            print(f"Update available: {info.current} → {info.latest}")
            print(f"URL: {info.url}")
        else:
            print(f"You're up to date! (v{info.current})")
        return 0

    if not args.no_update_check:
        info = check_for_updates()
        msg = get_update_message(info)
        if msg:
            print(msg, file=sys.stderr)

    if args.command or extra:
        return _run_command(args.command + extra)

    parser.print_help()
    return 0


def _run_command(command):
    cmd = command[0]

    if cmd == "setup":
        from garmin_coach.wizard import run_wizard

        run_wizard()
    elif cmd == "connect-strava":
        from garmin_coach.wizard.oauth import setup_strava_oauth

        return 0 if setup_strava_oauth() else 1
    elif cmd == "oauth-status":
        from garmin_coach.wizard.oauth import check_oauth_status
        from garmin_coach.integrations.strava.sync import _load_state

        status = check_oauth_status()
        for provider, connected in status.items():
            print(f"{provider}: {'connected' if connected else 'not connected'}")

        # Show Strava sync status when Strava is connected.
        if status.get("strava"):
            state = _load_state()
            last_sync = state.get("days") and max(state["days"].keys(), default=None)
            synced_days = len(state.get("days", {}))
            print(
                f"strava-sync: {synced_days} days in state"
                + (f", last date {last_sync}" if last_sync else ", no syncs yet")
            )
    elif cmd == "strava-sync":
        from garmin_coach.integrations.strava import sync_strava_training_load

        sync_parser = argparse.ArgumentParser(prog="garmin-coach strava-sync")
        sync_parser.add_argument("--days", type=int, default=30)
        sync_parser.add_argument("--dry-run", action="store_true")
        sync_args = sync_parser.parse_args(command[1:])
        try:
            result = sync_strava_training_load(days=sync_args.days, dry_run=sync_args.dry_run)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        pprint(result)
    elif cmd == "garmin-sync":
        from garmin_coach.integrations.garmin import sync_garmin_training_load

        sync_parser = argparse.ArgumentParser(prog="garmin-coach garmin-sync")
        sync_parser.add_argument("--days", type=int, default=30)
        sync_parser.add_argument("--dry-run", action="store_true")
        sync_args = sync_parser.parse_args(command[1:])
        try:
            result = sync_garmin_training_load(days=sync_args.days, dry_run=sync_args.dry_run)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        pprint(result)
    elif cmd == "status":
        from garmin_coach.handler import process_message

        result = process_message("컨디션 어때?")
        print(result)
    elif cmd == "log":
        from garmin_coach.handler import process_message

        result = process_message("운동 끝")
        print(result)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
