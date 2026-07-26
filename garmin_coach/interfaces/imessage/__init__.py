"""iMessage channel (macOS-only): chat.db polling + AppleScript send.

No official iMessage API exists. This mirrors the community-standard pattern
(BlueBubbles, imsg, Jared): read incoming messages from the local Messages
database, reply via AppleScript. Requires Full Disk Access for the terminal/
process running this, and only works for messages arriving at this Mac's own
Apple ID.

ToS note: Apple's terms prohibit automated messaging on personal accounts.
This is intended for personal use / a small circle of contacts who message
your own Mac directly — not a public-facing bot. See garmin-coach-prd.md
§Channel strategy and work-orders-5stream.md §S-F for the tradeoffs.
"""

from garmin_coach.interfaces.imessage.adapter import IMessageAdapter

__all__ = ["IMessageAdapter"]
