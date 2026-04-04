import asyncio
import sys

from garmin_coach._version import __version__


def main() -> int:
    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"garmin-coach-mcp {__version__}")
        return 0

    from mcp_server.__main__ import main as async_main

    asyncio.run(async_main())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
