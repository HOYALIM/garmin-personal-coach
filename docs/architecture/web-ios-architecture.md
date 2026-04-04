# Web / iOS Architecture Draft

## Goal

Define the smallest architecture that lets `garmin-personal-coach` grow from a Garmin-first CLI product into a multi-surface product without rewriting the core coaching logic.

## Current Runtime Reality

The current product already has four meaningful surfaces:

- **CLI** via `garmin_coach.cli`
- **Natural-language coach runtime** via `garmin_coach.handler`
- **Telegram bot** via `garmin_coach.telegram_bot`
- **MCP server** via `mcp_server.server`

The durable product value is inside the shared Python domain logic: adapters, profile/config, training load, AI routing, and response generation.

## Core Principle

Future web/iOS work should **wrap the existing core** rather than fork it.

That means:

- no duplicate training-load calculations in frontend code,
- no duplicate AI orchestration logic in a mobile app,
- no separate truth source for profile or adapter state.

## Recommended Architecture

### Layer 1 — Core Domain (existing repo)
Primary responsibilities:

- profile and onboarding state
- Garmin/Strava adapter logic
- training load science
- AI provider routing
- natural-language coaching responses

Representative modules:

- `garmin_coach/adapters/**`
- `garmin_coach/profile_manager.py`
- `garmin_coach/training_load*`
- `garmin_coach/handler/**`
- `garmin_coach/ai_simple.py`

### Layer 2 — Delivery Interfaces (existing repo)
Primary responsibilities:

- CLI commands
- Telegram bot interactions
- MCP tool exposure

Representative modules:

- `garmin_coach/cli.py`
- `garmin_coach/telegram_bot.py`
- `mcp_server/server.py`

### Layer 3 — Future App/API Layer (new work)
Primary responsibilities:

- authenticated client/server boundary for web/mobile
- normalized JSON contracts for profile, metrics, activities, recommendations
- ingestion endpoint for future Apple/native clients

This layer is the missing piece for web and iOS. It should be added as a thin API surface over the existing Python core.

## Web Direction

The web surface should start as a **read-only dashboard**.

Initial web responsibilities:

- show training status and recent activity,
- show AI-generated coaching summary,
- show profile/connectivity state,
- avoid direct editing or complex workflow orchestration in v1.

This keeps the first web version tightly aligned with the current CLI + Telegram product, instead of inventing a new product shape.

## iOS Direction

iOS should be treated as two possible layers, not one:

### Option A — Thin mobile client
- authenticates to backend/API
- reads dashboard/coaching data
- pushes notifications or lightweight interaction

### Option B — Native health client
- reads HealthKit
- optionally communicates with watchOS
- uploads normalized data to backend/core layer

Option A can happen without HealthKit. Option B is the Apple platform expansion path.

## Auth / Session Model

Recommended model for future web/iOS:

- a product-level user identity independent of raw Garmin session files,
- adapter connection status stored in product config/profile,
- client auth for web/mobile separated from third-party provider auth,
- provider credentials/tokens stored server-side or device-side according to platform needs.

Important distinction:

- **product auth** = user signs into the coaching product
- **provider auth** = Garmin / Strava / future Apple connection

Do not collapse these into one concept.

## Data Sync Model

Recommended sync direction:

1. adapter/native client fetches source data,
2. core layer normalizes it,
3. training load + AI context update,
4. delivery surfaces read the same normalized state.

This means web, CLI, Telegram, and future mobile all consume one normalized coaching model.

## Boundaries That Must Stay Stable

The following concepts should become stable contracts before major UI work:

- profile
- adapter connection state
- recent activities
- daily metrics / readiness context
- training load context (CTL / ATL / TSB)
- AI recommendation payload

## Non-Goals for This Phase

- building a full web app now
- building an iOS app now
- introducing a second implementation of core coaching logic
- moving Telegram/CLI behavior into frontend-specific code

## Recommendation

The next correct step is:

1. keep core Python domain as source of truth,
2. define a minimal API contract,
3. build a read-only dashboard first,
4. treat HealthKit as a separate native client track.
