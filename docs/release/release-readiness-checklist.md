# Release Readiness Checklist

_For early-user / beta release. Honest assessment of what must be true, what is known-limited, and what to communicate clearly._

---

## Release Gate: Must Be True Before Tagging

- [ ] `garmin-coach setup` wizard completes without errors on a clean install
- [ ] `garmin-coach status` returns meaningful output with a valid Garmin session
- [ ] MCP server responds to `initialize` and `tools/list` correctly
- [ ] Telegram bot starts and responds to `/start` and `/status`
- [ ] `pip install garmin-personal-coach` installs cleanly on Python 3.10–3.13
- [ ] No runtime errors on `garmin-coach --version` and `garmin-coach --check-updates`
- [ ] `docs/release/user-journey.md` accurately reflects the install path
- [ ] README does not claim features that are not working (see notes below)

---

## Known Limitations — Must Communicate to Early Users

### Strava
- OAuth is not a guided flow. Users must manually create and place a token file.
- CTL/ATL from Strava is placeholder math. Training load metrics should be treated as approximate.
- Strava is supplemental only — not a standalone data source.

### AI Coaching
- Requires a paid OpenAI or Anthropic API key.
- Without a key, coaching is rule-based only (TSB thresholds, no personalized language).

### No Web Dashboard
- There is no UI. All interaction is CLI, Telegram, or MCP.

### CalDAV
- Requires manual environment variable configuration. Not covered in setup wizard.

### Nike Run Club
- Not supported. Stub file exists in codebase but should not be exposed to users.
- See `docs/research/nike-run-club-feasibility.md`.

### Apple HealthKit / Apple Watch
- Not supported in this repo. Requires a separate native iOS app that does not exist yet.
- See `docs/research/healthkit-feasibility.md`.

---

## README Accuracy Issues (Do Not Ship Until Fixed)

These items in the current README are inaccurate and should be corrected before a public release:

| README claim | Reality | Action needed |
|--------------|---------|---------------|
| "Coming Soon: Strava integration" | Strava adapter exists, partial implementation | Change to "Strava (beta, manual token setup required)" |
| "Coming Soon: Nike Run Club integration" | No public API — deferred indefinitely | Remove or move to "Not planned" |
| Architecture note: "Garmin → Strava/Nike coming" | Nike is deferred | Remove Nike from coming-soon list |

---

## Future Work — Not Release Blockers

These are known gaps that do not block an early-user release but should be on the roadmap:

| Item | Priority | Notes |
|------|----------|-------|
| Strava guided OAuth wizard | High | Removes manual token setup friction |
| Real PMC math for Strava CTL/ATL | Medium | Current placeholder is not accurate |
| Web dashboard | Medium | Specs exist; not implemented |
| Apple HealthKit (iOS native track) | Low | Separate project, not this repo |
| iMessage | Not planned | No spec or implementation |

---

## Release Communication Template (for early users)

> **Garmin Personal Coach v0.1.0 — Beta**
>
> What works today:
> - Garmin Connect integration (core)
> - Training load metrics (CTL/ATL/TSB) from Garmin data
> - AI coaching via CLI, Telegram, and MCP
> - Optional Strava sync (manual token setup required)
>
> Known limitations:
> - No web dashboard
> - No mobile app (use Telegram for mobile)
> - Strava OAuth requires manual token — guided flow coming
> - No Nike Run Club or Apple HealthKit support
> - AI coaching requires OpenAI or Anthropic API key
