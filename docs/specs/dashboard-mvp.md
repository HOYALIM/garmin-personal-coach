# Dashboard MVP Specification

## Product Goal

Expose the existing coaching value of `garmin-personal-coach` in a browser without changing the product’s core logic.

This is a **read-only MVP**. The first dashboard should help a user understand their current training state, not replace setup, logging, or deep coaching workflows.

## MVP Principles

- Read-only first
- Reuse existing core metrics and recommendation logic
- Prefer one page over many
- Focus on training status, recovery, and recent activity

## Primary User

An existing Garmin/Strava-connected user who wants a faster, more visual way to check current state than CLI or Telegram.

## MVP Screens

## 1. Dashboard Home

Purpose:

- give the user an immediate understanding of recovery/form and today’s recommendation

Contents:

- profile summary
- connection status (Garmin, Strava, AI enabled)
- CTL / ATL / TSB
- latest coaching recommendation
- training readiness / recovery highlights if available

## 2. Recent Activities

Purpose:

- show what recent training the product is reasoning over

Contents:

- recent activity list
- sport type
- duration
- distance
- date/time
- brief derived metadata if already available

## 3. Source / Setup State

Purpose:

- explain whether the product is actually connected and usable

Contents:

- Garmin connected?
- Strava connected?
- AI enabled / provider chosen?
- profile/setup completeness

This can be a section on the main page instead of a separate route in MVP.

## Out of Scope for MVP

- editing profile data in browser
- running setup in browser
- manual workout logging in browser
- advanced charts beyond a minimal sparkline/trend if cheap
- multi-user admin surfaces
- Apple Health / Nike connection UI

## Information Hierarchy

Top to bottom priority:

1. Today’s state
2. Why the state looks that way
3. Recent workouts feeding the model
4. Connectivity/setup gaps

## UI Blocks

Suggested blocks for the single-page MVP:

- **Hero status card** — current form, short recommendation
- **Training load cards** — CTL / ATL / TSB
- **Recovery card** — sleep / HR / readiness if present
- **Recent activity list**
- **Connection/setup status card**

## Success Criteria

The MVP is successful if a user can answer these questions in under 30 seconds:

- Am I generally fresh or fatigued?
- What does the coach think I should do next?
- Is my account actually connected and configured?
- What recent workouts is the system using?

## Dependency on API Contract

The dashboard should only consume stable, normalized server responses. It should not parse config files, Garmin sessions, or local artifacts directly.
