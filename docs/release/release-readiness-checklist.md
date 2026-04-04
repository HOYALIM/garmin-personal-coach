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
- OAuth is guided through `garmin-coach connect-strava`, but users still need their own Strava API app credentials.
- Strava sync is manual in this release (`garmin-coach strava-sync`).
- Strava is supplemental only — not a standalone authoritative source.

### AI Coaching
- Requires a paid OpenAI, Anthropic, or Gemini API key for AI-enhanced responses.
- Without a key, coaching is rule-based only (TSB thresholds, no personalized language).

### Nutrition Coaching
- Current nutrition coaching is lightweight preference-based guidance only.
- No meal logging, image upload, or calorie-from-photo estimation in this release.

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

**None blocking after the current doc updates.**

---

## Future Work — Not Release Blockers

These are known gaps that do not block an early-user release but should be on the roadmap:

| Item | Priority | Notes |
|------|----------|-------|
| Automatic Strava sync trigger | Medium | Sync is still manual by design in this release |
| Web dashboard | Medium | Specs exist; not implemented |
| Apple HealthKit (iOS native track) | Low | Separate project, not this repo |
| iMessage | Planned later | No implementation yet |

---

## Release Communication Template (for early users)

> **Garmin Personal Coach v0.1.0 — Beta**
>
> What works today:
> - Garmin Connect integration (core)
> - Training load metrics (CTL/ATL/TSB) from Garmin data
> - AI coaching via CLI, Telegram, and MCP
> - Lightweight personalized nutrition guidance
> - Optional Strava sync via guided OAuth + manual sync command
>
> Known limitations:
> - No web dashboard
> - No mobile app (use Telegram for mobile)
> - Strava sync is manual and Garmin remains the primary source of truth
> - No Nike Run Club or Apple HealthKit support
> - AI coaching requires OpenAI, Anthropic, or Gemini API key for enhanced responses
