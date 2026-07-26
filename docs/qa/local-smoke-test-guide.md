# Local Smoke Test Guide (v3.0 stream)

Hands-on guide for trying this session's changes yourself, right now, on your
own Mac. Not a PRD-fidelity checklist (see `manual-verification-runbook.md`
for that) — just "does it actually work on my machine."

Run everything from the repo root with the project venv active:

```bash
cd ~/code/garmin-personal-coach
source .venv/bin/activate
```

## 0. Current machine state (checked 2026-07-14)

- **Garmin**: not connected. `~/.garminconnect/` (the CLI/MCP token path) is
  empty, and the one Telegram-scoped token directory found
  (`~/.config/garmin_coach/telegram_states/garth/<telegram_user_id>/`) is also
  empty with no saved profile — an onboarding attempt started but never
  completed. Start fresh with step 2 below.
- **Strava**: a token file exists at
  `~/.config/garmin_coach/strava_token.json`. Not verified working — confirm
  with step 4. ⚠️ Its prefix appeared partially in this session's transcript
  while diagnosing the Garmin issue; if you want to be careful, disconnect
  and reconnect Strava (step 4) to rotate it.
- **iMessage**: Full Disk Access not yet granted (step 5 covers this).
- **AI chat**: confirmed working end-to-end via the local Claude CLI, no API
  key needed.

## 1. AI chat — works with zero setup

```bash
gc chat "TSB -5인데 오늘 인터벌 해도 될까?"
```

Uses whatever local AI CLI you have installed (claude/gemini/codex) — no API
key required. If this prints a coaching reply, the zero-config LLM chain is
working.

## 2. Connect Garmin (do this first — most things below depend on it)

```bash
garmin-coach connect-garmin --email your@email.com
```

Enter your password when prompted; if MFA is enabled you'll be prompted for a
code too. On success you'll see `✓ Garmin connected! Tokens saved to
~/.garminconnect`.

⚠️ **If this fails, do not immediately retry.** Garmin rate-limits failed
login attempts per account (not per IP) — repeated attempts can lock you out
for longer. Paste me the exact error output instead and I'll diagnose it.

Verify it actually took:

```bash
garmin-coach garmin-sync --dry-run
```

Should print real activity/training-load data pulled from your account, not
an authentication error.

## 3. Ask about today's real data

```bash
gc status
gc chat "오늘 컨디션 어때?"
```

These read from the same snapshot cache this session's Data Plane work
added — first call may take a couple seconds (cold fetch), repeat calls
should be near-instant (cache hit).

## 4. Strava (optional — only if you have a subscription/API app)

```bash
garmin-coach connect-strava        # only if you want to (re)do this
garmin-coach strava-sync --dry-run
```

If dry-run prints real activities, the token is good. To pull your entire
history (paginated, with 429 backoff — see this session's fix):

```bash
garmin-coach strava-sync --days 3650 --dry-run
```

## 5. iMessage channel

**a. Grant Full Disk Access** (one-time):
System Settings → Privacy & Security → Full Disk Access → add your terminal
app (Terminal.app / iTerm / whatever you're running this from) → restart the
terminal.

Confirm it took:

```bash
python -c "
from garmin_coach.interfaces.imessage.chat_db import ChatDBReader
print('max_rowid:', ChatDBReader().max_rowid())
"
```

Should print a number, not a permission error.

**b. Run the poller:**

```bash
garmin-coach-imessage
```

First send may trigger a one-time macOS popup asking to let Terminal control
Messages — allow it.

**c. Test from a different device/number** (not this Mac's own Apple ID —
messages `is_from_me=1` are intentionally ignored):
Text this Mac's iMessage-registered number anything. You should get back an
onboarding question ("Garmin Connect 이메일을 입력해주세요"). Answer a few and
it should walk through the same flow Telegram runs. If it stalls or errors,
send `시작` to restart from saved progress.

## 6. Telegram bot (if you want the original channel too)

Requires `TELEGRAM_BOT_TOKEN` set:

```bash
export TELEGRAM_BOT_TOKEN=your_token
garmin-coach-telegram
```

## What to report back

For each step: did it work, and if not, the exact error text (not a
paraphrase — exact tracebacks help). Priority order if you're short on time:
**step 2 (Garmin) matters most** — most other features depend on it.
