"""CLI entry point for garmin-personal-coach."""

import sys
import argparse

from garmin_coach._version import __version__
from garmin_coach.update_check import check_for_updates, get_update_message


def main():
    parser = argparse.ArgumentParser(prog="garmin-coach")
    parser.add_argument("--version", "-v", action="store_true", help="Show version")
    parser.add_argument("--check-updates", action="store_true", help="Check for updates")
    parser.add_argument("--no-update-check", action="store_true", help="Skip update check")
    parser.add_argument("command", nargs="*", help="Command to run")

    args = parser.parse_args()

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

    if args.command:
        return _run_command(args.command)

    parser.print_help()
    return 0


def _run_command(command):
    cmd = command[0]

    if cmd == "setup":
        from garmin_coach.wizard import run_wizard

        run_wizard()
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
