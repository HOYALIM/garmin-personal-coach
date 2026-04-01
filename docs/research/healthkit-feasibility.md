# Apple HealthKit / Apple Watch Feasibility

## Summary

**Decision: SEPARATE TRACK — backend preparation now, native app later.**

HealthKit cannot be accessed from Python, a CLI, or a server. It is an on-device Apple framework that requires a native iOS app. This repo's Python core can be prepared now to receive and process Apple Health data, but the HealthKit client layer must be a separate native iOS (and optionally watchOS) app. This is not a blocker to product progress — it is a scope boundary.

---

## Confirmed Facts

- HealthKit is an on-device framework. Access is through native Apple APIs only — not via Python, HTTP, or server-side SDKs.
- Health data access is permissioned per app and per data type at the iOS system level. No server-side token or credential grants HealthKit access.
- Apple Watch data flows through the HealthKit ecosystem but is still accessed through native app surfaces, not backend calls.
- iPhone ↔ Apple Watch coordination uses Apple-native patterns (HealthKit, WatchConnectivity). There is no server-to-watch data path without a native app in between.
- There is no official Apple HealthKit REST API or Python SDK.

---

## Working Assumptions

- This repo remains primarily Python / CLI / server-side for the foreseeable future.
- Any HealthKit integration worth shipping requires at minimum a native iOS companion app.
- A watchOS app is optional for basic HealthKit ingestion, but necessary for watch-native workout UX or real-time session features.
- The Python backend is a valid and stable platform for coaching logic — it only needs a data delivery contract with the native layer.

---

## Unknowns / Blockers

- Whether a lightweight iOS shortcut or Health export (CSV/XML) would be an acceptable interim path before a full native app is built.
- Whether the product needs real-time watch-side workout capture, or only post-workout sync (the latter is significantly simpler to implement).
- Auth model between a future native iOS app and this repo's backend — OAuth2, session token, or local-only sync.
- Whether a third-party bridge (e.g., Health Auto Export app, HealthKit → webhook approach) is acceptable for early adopters as a stopgap.

---

## Repo Boundary: What This Repo Can and Cannot Do

### What the current Python repo CAN do

- Define normalized data schemas for workouts, recovery, sleep, HR, readiness, and activity metrics.
- Receive health data payloads from a native client over an API or sync mechanism.
- Process coaching logic, training load analysis, AI interpretation, and downstream outputs (Telegram, calendar, dashboard).
- Expose API endpoints or sync targets designed for a future native iOS companion.
- Prepare auth / session model for mobile client authentication.

### What the current Python repo CANNOT do

- Request HealthKit permissions.
- Read or write HealthKit data directly.
- Access Apple Watch sensor data or workout sessions without a native app intermediary.
- Act as the HealthKit client in any form.

**The Python repo is the backend. A native iOS app is the HealthKit client. These are two distinct things.**

---

## Two-Track Model

```
Track A — Backend prep (this repo, now)
  └─ Define ingestion API contract
  └─ Normalize Apple Health data model
  └─ Design auth model for mobile client

Track B — Native client (separate project, later)
  └─ Native iOS app: HealthKit permissions + data read
  └─ Optional watchOS app: workout capture, session UX
  └─ Sync to Track A backend over API
```

Track A and Track B are independent. Track A work is useful and shippable now. Track B requires a separate native app project.

---

## Risk Assessment

| Risk Area | Level | Reasoning |
|-----------|-------|-----------|
| Technical feasibility (direct, current repo) | **Low** | HealthKit is not accessible from Python |
| Technical feasibility (backend support work) | **High** | Standard API + data model work |
| Product value | **High** | Apple Health / Watch support broadens product beyond Garmin-centric users significantly |
| Delivery complexity | **High** | Requires new native surface, OS-level permissions, sync design, and auth between app and backend |

---

## Recommendation

**SEPARATE TRACK — start backend preparation now, native app is a distinct future project.**

### What to build now (Track A — this repo)

- Ingestion API contract for Apple Health data (workout, recovery, sleep, HR).
- Normalized data model compatible with Apple Health types and the existing coaching engine.
- Auth / session model for a future mobile client.

### What to build later (Track B — separate native project)

- Native iOS companion app with HealthKit permissions and data export to this repo's API.
- Optional watchOS app if the product needs watch-native workout capture or real-time session UX.

### What not to do

- Do not add a `healthkit.py` adapter in `garmin_coach/adapters/`. There is nothing to implement there — HealthKit is not accessible from this layer.
- Do not frame this as "waiting to implement the HealthKit adapter." Frame it as "backend ready, native client is a separate workstream."

---

## Repo Implication

HealthKit is a **platform expansion requiring a native client layer**, not a Python adapter task. Immediate work in this repo is limited to data schema and API preparation. A watchOS/iOS app is a distinct project scope that should be planned and scoped separately from the Python core roadmap.

---

## Source Notes

This assessment is grounded in Apple's official platform documentation for HealthKit and watchOS: on-device, native, app-permissioned data access. No server-side or Python access path for HealthKit was identified in Apple's public documentation.
