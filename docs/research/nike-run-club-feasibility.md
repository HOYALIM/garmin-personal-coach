# Nike Run Club Integration Feasibility

## Summary

**Decision: DEFER — do not implement.**

No public Nike developer API exists for third-party workout ingestion. Any integration path available today would rely on reverse-engineered private endpoints, which creates high legal, maintenance, and platform risk. Garmin + Strava already cover the safe interoperability surface this product needs.

---

## Confirmed Facts

- Nike publicly documents NRC as a consumer running product with selected partner and device connections (e.g., Strava, Apple Watch, select device ecosystems).
- **No public NRC developer API reference exists** comparable to Garmin Connect API or Strava API v3 — no public OAuth docs, no scopes, no endpoint reference, no rate limits, no developer program registration.
- Nike's public privacy and terms language describes how workout and location data is handled inside Nike services and through selected connections. It does not expose a third-party API contract for external apps like `garmin-personal-coach`.
- Nike's selected partner integrations are announced at the consumer product level. They do not imply a broadly available developer API.

---

## Working Assumptions

- Any deeper integration surfaces Nike has are partner-only, private, and not available to open application development.
- The "partner" connections documented publicly (e.g., Strava sync, Apple Watch pairing) are consumer UI flows, not exposed APIs.

---

## Official Support vs. Reverse-Engineered Paths

This distinction is critical for this repo:

| Path | Description | Status |
|------|-------------|--------|
| Official public API | Documented developer API, OAuth, scopes, rate limits | **Does not exist** |
| Official partner program | Private Nike partner agreement | Unknown; not publicly available |
| Reverse-engineered private endpoints | Intercepted NRC app traffic, undocumented mobile API calls | **Technically possible; not safe** |
| Account automation / session replay | Scraping NRC with user credentials | **Not safe; ToS violation** |

The temptation to use reverse-engineered paths is real but must be explicitly declined: any integration built on undocumented endpoints is not a stable integration — it is a fragile hack with no support contract.

---

## Unknowns / Blockers

- Whether Nike operates a private partner program for workout-data access and what its requirements are.
- Whether Nike would allow third-party coaching products to ingest NRC workout data under a future commercial agreement.
- Whether Nike's Strava sync is bidirectional (and if so, whether using Strava as a relay for NRC data is contractually permitted).

---

## Why Not Now

1. **No documented API surface.** Building against undocumented endpoints is not a product decision — it is a liability decision.
2. **ToS and legal risk.** In the absence of a public API contract, using undocumented endpoints or session automation creates authorization risk and potential ToS violation.
3. **Maintenance cost is unbounded.** Any unofficial path breaks silently on NRC app updates, auth changes, or network-level protections. There is no version contract.
4. **User impact.** A broken adapter that loses workout data silently is worse than not having the adapter at all.
5. **Strava already covers the overlap.** Users who run with Nike and want cross-platform analysis can sync NRC → Strava. The Strava adapter handles the rest.

---

## Risk Assessment

| Risk Area | Level | Reasoning |
|-----------|-------|-----------|
| API / Platform stability | **High** | No stable, publicly documented NRC API surface exists |
| Maintenance | **High** | Any unofficial path is vulnerable to silent breakage |
| Legal / ToS | **High** | No public API contract; undocumented endpoint use creates authorization risk |
| Product value | **Medium** | Garmin + Strava already cover the primary user surface |

---

## Recommendation

**DEFER — do not implement a Nike adapter.**

### What to do now
- Keep Nike listed as future/conditional work only.
- Do not build an adapter against undocumented Nike surfaces under any circumstances.
- If a user wants NRC workouts in this product, direct them to sync NRC → Strava, then use the existing Strava integration.

### What would change this recommendation
- Nike publishes a public developer API with OAuth, documented scopes, endpoints, and rate limits.
- Nike grants explicit written partner access with a supported data-sharing contract.

---

## Repo Implication

Nike is **out-of-scope after Garmin + Strava**. The next platform expansion should prioritize HealthKit / mobile architecture and dashboard/API work. A `garmin_coach/adapters/nike.py` stub may exist in the codebase but should not be wired to production flows until the above conditions are met.

---

## Source Notes

This assessment is based on official Nike consumer-facing help, privacy, and news sources, and on the confirmed absence of a public NRC developer API comparable to Garmin Connect API or Strava API v3 documentation. No private or partner-level Nike documentation was reviewed.
