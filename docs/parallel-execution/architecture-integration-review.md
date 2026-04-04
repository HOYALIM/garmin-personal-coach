# Architecture Integration Review

## Purpose

This document explains how the parallel lanes should reconnect into the current product without fragmenting the architecture.

It is a PM / VP-level view of the product, not a low-level code plan.

---

## Current Product Core

The current shipped product is centered on one durable core:

- **profile/config state**
- **training-load state**
- **AI/rule-based coaching logic**
- **provider adapters and ingestion**

Current delivery surfaces are:

- CLI (`garmin_coach.cli`)
- natural-language runtime (`garmin_coach.handler`)
- Telegram (`garmin_coach.telegram_bot`)
- MCP (`mcp_server.server`)

These are interfaces to the same coaching product, not separate products.

---

## Current Truth Hierarchy

### Garmin
Garmin remains the authoritative runtime source.

That means:

- Garmin still anchors the coaching product’s default connected state.
- Garmin remains primary in generic fetch/runtime paths.
- Garmin should not be displaced by opportunistic Strava behavior.

### Strava
Strava is now a synchronized supplemental ingestion source.

That means:

- Strava is valuable,
- Strava should influence training-load ingestion,
- Strava should not silently redefine Garmin-first runtime truth.

### Nike
Nike remains blocked/deferred.

### HealthKit
HealthKit remains a future native-client track, not a Python adapter task.

---

## What Each Lane Is Supposed To Improve

## Lane 1 — Runtime / Strava Phase 2

This lane improves the **runtime data model and ownership boundaries**.

It should answer:

- how Strava-synced load is represented,
- how it coexists with Garmin,
- how sync status and ownership are exposed,
- how runtime truth remains clear.

It should **not** redesign the dashboard or future API layer.

## Lane 2 — Research / Nike + HealthKit

This lane improves the **strategic clarity of what not to build yet**.

It should answer:

- why Nike is blocked,
- why HealthKit requires a native path,
- where future expansion would need new platform work.

It should **not** try to rescue blocked integrations by lowering standards.

## Lane 3 — Architecture / Backend API + Dashboard Spec

This lane improves the **future interface layer**.

It should answer:

- how the future API wraps the current core,
- what the dashboard consumes,
- how future web/mobile fit the product without duplicating the core.

It should **not** redefine the current runtime as a web-first product.

---

## Integration Checkpoints

These are the files/functions that matter most when reconciling lane outputs.

### Runtime truth checkpoints
- `garmin_coach/cli.py`
- `garmin_coach/handler/__init__.py`
- `garmin_coach/telegram_bot.py`
- `mcp_server/server.py`

### Garmin/Strava data boundary checkpoints
- `garmin_coach/adapters/fetch.py`
- `garmin_coach/adapters/strava.py`
- `garmin_coach/integrations/strava/sync.py`

### Product contract checkpoints
- `docs/architecture/web-ios-architecture.md`
- `docs/specs/dashboard-api-contract.md`
- `docs/specs/dashboard-mvp.md`

### Contract provenance checkpoints
- Every API/dashboard contract endpoint and field must be classed as:
  - `existing`
  - `derived from existing`
  - `target only`
- `existing` and `derived from existing` endpoints and fields must cite a current runtime source such as:
  - `mcp_server/server.py`
  - `garmin_coach/handler/__init__.py`
  - `garmin_coach/profile_manager.py`
  - `garmin_coach/training_load_manager.py`
- `target only` endpoints must not be described as currently reachable through CLI, handler, Telegram, or MCP

---

## Architecture Rules For Integration

## Rule 1 — One coaching core
Do not let web, Telegram, CLI, and MCP drift into separate product logic.

## Rule 2 — Garmin stays primary
Strava can extend the product but should not silently replace Garmin’s runtime role.

## Rule 3 — Sync and fetch are not the same thing
The new Strava sync path is about ingestion into training-load state.
The generic fetch path is still a separate concern.

## Rule 4 — Docs follow runtime truth
Architecture/spec docs must reflect what lane 1 makes true.

This means lane 3 is not final until its claims are re-checked against lane 1’s final runtime diff.

## Rule 5 — Future API is a wrapper, not a fork
The backend API should expose normalized coaching data, not create a parallel logic stack.

---

## What “Good Integration” Looks Like After These Lanes

If the lanes succeed, the product state should be:

- Garmin-first runtime still stable
- Strava sync path cleaner and more explicit
- Nike clearly blocked with strong justification
- HealthKit clearly separated into native-track work
- backend API/dashboard docs precise enough for the next implementation milestone

And specifically:

- no dashboard/API field is presented as current truth unless it has a runtime source,
- target-only contract fields are clearly identified as future implementation work,
- merge order preserves runtime truth before spec truth.

At that point, the next engineering milestone becomes obvious:

1. finalize Strava phase 2 runtime cleanup,
2. build the thin backend API layer,
3. implement the read-only dashboard MVP,
4. keep Apple-native work separate,
5. revisit Nike only if the platform reality changes.

---

## Final PM / VP Position

The product should continue to be treated as:

- a coaching engine first,
- a multi-surface product second,
- a web/mobile platform later.

That ordering is what keeps the current work coherent instead of turning into parallel, conflicting mini-products.
