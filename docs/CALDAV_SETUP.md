# CalDAV Calendar Sync Setup

This guide configures calendar sync using CalDAV — compatible with most calendar servers.

## Supported Servers

- **Nextcloud** (self-hosted)
- **Fastmail** (fastmail.com)
- **iCloud** (caldav)
- **Any RFC 4791-compliant CalDAV server**

## Setup

### 1. Get CalDAV credentials

**Nextcloud:**
```
URL: https://your-nextcloud.com/remote.php/dav/calendars/username/
Username: your@email.com
Password: App-specific password (Settings → Security → App passwords)
```

**Fastmail:**
```
URL: https://caldav.fastmail.com/dav/calendars/user/your@email.com/
Username: your@email.com
Password: App-specific password (Settings → Passwords → CalDAV)
```

**iCloud:**
```
URL: https://caldav.icloud.com/
Username: your@email.com
Password: App-specific password (appleid.apple.com → App-Specific Passwords)
```

### 2. Set environment variables

```bash
export CALDAV_URL="https://your-caldav-server.com/remote.php/dav/calendars/user/you/"
export CALDAV_USER="your@email.com"
export CALDAV_PASS="app-specific-password"
export CALENDAR_NAME="Training"  # calendar display name
```

### 3. Verify connection

```bash
python -c "
import caldav
from caldav import Calendar
client = caldav.DAVClient(
    'https://your-caldav-url.com/',
    username='user',
    password='pass'
)
principal = client.principal()
calendars = list(principal.calendars())
for c in calendars:
    print(c.name, c.url)
"
```

### 4. Test sync

```bash
python workout_review.py --date 2026-03-25 --no-calendar
```

## Workout Event Matching

The sync finds events matching these keywords:
- 러닝, 달리기, 운동, 트레이닝
- run, jog, workout, marathon
- long run, threshold

Events are matched by date + title keyword.

## Idempotent Behavior

Each sync writes a block between:
```
<!-- GARMIN_COACH_START -->
...log data...
<!-- GARMIN_COACH_END -->
```

Reruns replace the block — no duplicates.
