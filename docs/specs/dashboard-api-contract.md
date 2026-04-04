# Dashboard API / Data Contract Draft

## Goal

Define the smallest server-facing contract needed for a read-only dashboard MVP.

This draft is intentionally conservative. It describes the stable data shapes the dashboard should consume from backend/core logic.

## Contract Principles

- read-only first
- normalized product data, not provider-native payloads
- avoid leaking raw config/session internals to the UI
- keep one source of truth in Python core logic

## Endpoint 1 — Profile Summary

### `GET /api/profile`

Response draft:

```json
{
  "name": "HoLim",
  "age": 30,
  "sports": ["running", "cycling"],
  "fitness_level": "intermediate",
  "setup_complete": true
}
```

Primary source today:

- normalized config/profile state
- conceptually aligned with `mcp_server.server.get_user_profile`

## Endpoint 2 — Connection Status

### `GET /api/connections`

Response draft:

```json
{
  "garmin": { "connected": true },
  "strava": { "connected": true },
  "ai": {
    "enabled": true,
    "provider": "anthropic",
    "model": "claude-sonnet"
  }
}
```

Notes:

- Do not expose raw tokens, secrets, or local file paths.

## Endpoint 3 — Training Status

### `GET /api/training-status`

Response draft:

```json
{
  "ctl": 42.1,
  "atl": 47.3,
  "tsb": -5.2,
  "has_data": true,
  "status_text": "Slight fatigue, manageable with steady training"
}
```

Primary source today:

- training load manager / handler context
- conceptually aligned with `mcp_server.server.get_training_status`

## Endpoint 4 — Recent Activities

### `GET /api/activities?limit=10`

Response draft:

```json
{
  "items": [
    {
      "date": "2026-03-29T07:00:00",
      "sport": "running",
      "name": "Morning Run",
      "duration_min": 59,
      "distance_km": 10.0,
      "trimp": 75
    }
  ]
}
```

Notes:

- Normalize duration/distance to dashboard-friendly values.
- Prefer already-derived product values over raw provider payloads.

## Endpoint 5 — Coaching Summary

### `GET /api/coaching-summary`

Response draft:

```json
{
  "headline": "You are carrying manageable fatigue.",
  "recommendation": "Favor an easy aerobic session today.",
  "source": "rule" 
}
```

Future extension:

- include `source: ai | rule`
- include provider/model metadata only if useful for debugging/admin views

## Endpoint 6 — Recovery Snapshot

### `GET /api/recovery`

Response draft:

```json
{
  "resting_hr": 51,
  "sleep_hours": 5.27,
  "training_readiness": 66
}
```

Notes:

- This endpoint should tolerate partial data.
- Missing fields should be omitted or null, not treated as fatal.

## MVP Aggregation Option

To reduce frontend complexity, a single bootstrap endpoint is also acceptable:

### `GET /api/dashboard`

```json
{
  "profile": { "...": "..." },
  "connections": { "...": "..." },
  "training_status": { "...": "..." },
  "recovery": { "...": "..." },
  "recent_activities": { "items": [] },
  "coaching_summary": { "...": "..." }
}
```

This is probably the best first implementation because it keeps the frontend simple while the API surface is still stabilizing.

## Auth Assumption

Not finalized in this phase.

For MVP planning purposes, assume:

- authenticated product user
- server-side access to normalized profile and adapter state
- no direct browser access to local config/session artifacts

## Non-Goals

- mutation endpoints
- provider OAuth endpoints for dashboard UI
- admin/debug APIs
- raw Garmin/Strava passthrough payloads
