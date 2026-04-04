# Garmin Personal Coach — Parallel Claude Code Execution Plan

## Purpose

This document is the source of truth for running multiple Claude Code sessions in parallel against `garmin-personal-coach` without stepping on each other.

The goal is not "more agents doing random work." The goal is controlled parallelism:

1. one lane ships core product value,
2. one lane reduces external dependency uncertainty,
3. one lane prepares the next interface layer,
4. all lanes avoid file overlap and merge churn.

---

## Product Direction

`garmin-personal-coach` is not just a Python CLI. It is a personal endurance coaching product whose long-term value comes from combining:

- reliable training data ingestion,
- interpretable training-load science,
- AI-generated coaching guidance,
- friendly delivery surfaces beyond the terminal.

### Current Product Thesis

The current product should be treated as:

- **core product now**: Garmin-centric coaching engine with AI support,
- **next product step**: multi-source ingestion and provider-flexible AI,
- **next delivery step**: operational reliability and user-facing surfaces,
- **future expansion**: web/mobile experience once the data/auth/core contracts stabilize.

### What is already considered real

Based on prior project state captured in session memory, the repo is already treated as having:

- Garmin integration,
- AI coach integration,
- MCP server,
- Telegram bot,
- training load science (CTL/ATL/TSB, TRIMP),
- high automated test coverage,
- production-ready core CLI direction.

### What is still strategically important

The next value unlocks are:

1. **real Strava OAuth2 + real activity ingestion**,
2. **user-selectable AI provider/model routing**,
3. **real-world runtime validation and operational hardening**,
4. **future-facing architecture/spec work without destabilizing the core**.

---

## Parallelism Strategy

Do **not** split work by vague themes like "backend" and "frontend." Split by **conflict surface**.

### Conflict-minimizing split

- **Lane A/B (runtime lane)** touches executable product code and runtime behavior.
- **Lane C (research lane)** touches research/docs only.
- **Lane D-prep (architecture/spec lane)** touches planning/spec/docs only.

This means we are explicitly **not** implementing the dashboard in parallel yet. We are only preparing it.

Reason: if the runtime lane changes auth, config shape, adapter outputs, or provider routing, a concurrently implemented dashboard will drift and get rebuilt.

---

## Recommended Active Claude Code Sessions

Run **3 Claude Code sessions in parallel right now**.

### Session 1 — Runtime Core
- Worktree: `/Users/ho/code/garmin-personal-coach-runtime`
- Branch: `feat/parallel-runtime-ab`
- Mission: Milestone A + B execution

### Session 2 — External Integrations Research
- Worktree: `/Users/ho/code/garmin-personal-coach-research`
- Branch: `docs/research-integrations`
- Mission: Nike + HealthKit feasibility research

### Session 3 — Product Architecture / Dashboard Spec
- Worktree: `/Users/ho/code/garmin-personal-coach-architecture`
- Branch: `docs/architecture-dashboard`
- Mission: web/iOS architecture + dashboard MVP/API contract spec

### Optional Session 4 — Verifier / Reviewer

Do **not** start this immediately.

Start a 4th Claude Code session only after Session 1 produces meaningful code changes. Use it for:

- skeptical review,
- merge-risk inspection,
- runtime/docs consistency check,
- release readiness validation.

If you launch too many sessions before there is reviewable output, you increase coordination cost without increasing throughput.

---

## Worktree Topology

### Coordinator checkout
- Path: `/Users/ho/code/garmin-personal-coach`
- Role: read-only coordinator/integration view unless explicitly needed for merge preparation

### Active worktrees

| Lane | Path | Branch | Type |
|---|---|---|---|
| Coordinator | `/Users/ho/code/garmin-personal-coach` | `main` | integration view |
| Runtime | `/Users/ho/code/garmin-personal-coach-runtime` | `feat/parallel-runtime-ab` | executable code |
| Research | `/Users/ho/code/garmin-personal-coach-research` | `docs/research-integrations` | docs only |
| Architecture | `/Users/ho/code/garmin-personal-coach-architecture` | `docs/architecture-dashboard` | docs/spec only |

---

## Lane Ownership

This is the most important section in the document.

If a lane edits files outside its ownership boundary, parallelism stops being safe.

### Session 1 — Runtime Core Lane

#### Mission
Ship the highest-leverage product work that changes real behavior.

#### Scope
- Strava real OAuth2
- Strava real token storage/refresh
- Strava real activity fetch path
- AI provider/model selection
- provider routing and validation
- real Garmin account validation
- Telegram production hardening/deployment preparation

#### Files this lane may own
- `garmin_coach/adapters/**`
- `garmin_coach/wizard/**`
- `garmin_coach/ai_simple.py`
- `garmin_coach/profile_manager.py`
- `garmin_coach/setup_wizard.py`
- `garmin_coach/handler/**` when AI routing or runtime invocation wiring must change
- `telegram/**`
- runtime config/profile/schema files
- executable tests directly covering runtime changes
- runtime-facing docs that must match shipped behavior

#### Files this lane must avoid unless absolutely required
- dashboard design/spec documents owned by Session 3
- research documents owned by Session 2
- `README.md` unless runtime truth forces a minimal factual correction

#### Success criteria
- real product behavior improved,
- tests updated and passing,
- runtime docs reflect actual state,
- no placeholder implementation shipped as if complete.

---

### Session 2 — External Integrations Research Lane

#### Mission
Reduce uncertainty around future integrations before anyone wastes implementation time.

#### Scope
- Nike Run Club API feasibility
- Apple HealthKit / Apple Watch feasibility
- external dependency constraints
- risk classification for future implementation

#### Files this lane may own
- `docs/research/**`
- `docs/investigations/**`
- `docs/parallel-execution/**` only if explicitly editing this plan

#### Files this lane must not edit
- any Python runtime code
- config/schema files
- tests
- deployment/runtime scripts

#### Required output style
Every research document must separate:

- **confirmed facts**,
- **working assumptions**,
- **unknowns / blockers**,
- **recommended decision**.

#### Success criteria
- clear go / no-go or defer recommendation,
- external risk is made explicit,
- future implementers can start without redoing discovery.

---

### Session 3 — Product Architecture / Dashboard Spec Lane

#### Mission
Prepare the next product surface without destabilizing current runtime work.

#### Scope
- web architecture draft
- iOS/mobile architecture draft
- dashboard MVP scope
- API/data contract proposal for the dashboard
- product boundary definitions between core, API, and user-facing clients

#### Files this lane may own
- `docs/architecture/**`
- `docs/specs/**`
- `docs/product/**`

#### Files this lane must not edit
- runtime adapters
- runtime config/schema
- `telegram/bot.py`
- AI provider routing code
- executable API server code unless separately approved later

#### Critical rule
This lane is **design/spec only for now**.

Do not build the dashboard yet.
Do not add frontend runtime code yet.
Do not force premature backend contracts into implementation code.

#### Success criteria
- dashboard MVP is scoped tightly,
- future web work has a concrete contract target,
- architecture reflects runtime reality rather than fantasy platform design.

---

## Detailed Instructions per Session

## Session 1 — Runtime Core Prompt

### Task
Implement the next core product milestones for `garmin-personal-coach`.

### Product understanding you must carry
This repo is a Garmin-first endurance coaching product moving toward multi-source ingestion and provider-flexible AI. The point of the next work is to close the gap between what the product claims and what it can do with real users and real credentials.

### Deliverables
1. Real Strava OAuth2 flow
2. Token persistence and refresh
3. Real Strava activity fetch integration
4. AI provider/model selection in config/profile flow
5. Real Garmin account validation evidence
6. Telegram production hardening plan or implementation where safely local

### Must do
- Match existing repository patterns
- Keep diffs surgical
- Update tests where behavior changes
- Prefer compatibility-preserving config evolution
- Distinguish scaffolding from fully functional behavior
- Leave a clear note if any part depends on real external credentials

### Must not do
- Do not build the dashboard
- Do not redesign the whole architecture
- Do not change docs/spec files owned by other lanes except when runtime truth forces a minimal correction
- Do not claim real integration without real execution evidence

### Verification expectations
- diagnostics clean,
- related tests pass,
- at least one real/manual validation path for changed external flows,
- runtime docs aligned to implementation state.

---

## Session 2 — Research Lane Prompt

### Task
Produce external integration feasibility research for Nike Run Club and Apple HealthKit.

### Product understanding you must carry
The product already has meaningful runtime functionality. Your job is not to add more code. Your job is to prevent the team from wasting time on brittle or impossible future integrations.

### Deliverables
1. `docs/research/nike-run-club-feasibility.md`
2. `docs/research/healthkit-feasibility.md`

### Must do
- Determine whether official/public APIs exist
- Identify auth, platform, legal, stability, and maintenance risks
- Separate near-term implementation viability from long-term strategic value
- End each document with a recommendation: implement / defer / drop

### Must not do
- Do not write runtime integration code
- Do not draft fake adapter implementations
- Do not assume unsupported APIs are acceptable just because reverse-engineering is possible

---

## Session 3 — Architecture / Dashboard Spec Prompt

### Task
Produce architecture and dashboard-spec documents that prepare the next interface layer while respecting that runtime contracts may still move slightly during Session 1.

### Product understanding you must carry
This product’s durable value is the coaching engine and ingestion pipeline. The dashboard exists to expose that value, not to redefine it. Your design should wrap the core, not distort it.

### Deliverables
1. `docs/architecture/web-ios-architecture.md`
2. `docs/specs/dashboard-mvp.md`
3. `docs/specs/dashboard-api-contract.md`

### Must do
- Define the smallest useful dashboard MVP
- Prefer read-only MVP first
- Distinguish present confirmed runtime data from proposed future data
- Define API/data contracts conservatively
- Identify where web, mobile, CLI, Telegram, and MCP should share core logic

### Must not do
- Do not implement UI code yet
- Do not create a full platform roadmap that assumes infinite time
- Do not introduce speculative auth/session models as if already chosen

---

## Coordination Protocol

## Concrete Collision Hotspots

These files are the most likely places to create merge pain if lane ownership is ignored:

- `garmin_coach/profile_manager.py`
- `garmin_coach/adapters/fetch.py`
- `garmin_coach/adapters/__init__.py`
- `garmin_coach/wizard/__init__.py`
- `garmin_coach/handler/__init__.py`
- `mcp_server/server.py`
- `README.md`

Default policy:

- Session 1 may touch these when needed for runtime truth.
- Session 2 and 3 should treat them as read-only.

### Rule 1 — Runtime truth wins
If Session 1 changes actual runtime behavior or config shape, Session 2 and 3 documents must be updated to match that truth.

### Rule 2 — Docs lanes do not back-drive runtime changes
Session 2 and 3 can recommend, but they do not force code changes by editing runtime files.

### Rule 3 — Use explicit status labels
Every spec/research document should clearly mark statements as one of:

- `Confirmed`
- `Assumption`
- `Open Question`
- `Recommendation`

### Rule 4 — Merge order matters
Recommended merge order:

1. research docs lane,
2. architecture/spec lane,
3. runtime lane,
4. optional reviewer lane after runtime merge candidate exists.

If runtime truth invalidates docs before merge, regenerate docs instead of arguing with implementation reality.

---

## File / Directory Recommendations

Create and use these directories if they do not already exist:

- `docs/research/`
- `docs/architecture/`
- `docs/specs/`
- `docs/parallel-execution/`

Suggested outputs:

- `docs/research/nike-run-club-feasibility.md`
- `docs/research/healthkit-feasibility.md`
- `docs/architecture/web-ios-architecture.md`
- `docs/specs/dashboard-mvp.md`
- `docs/specs/dashboard-api-contract.md`
- `docs/parallel-execution/claude-code-parallel-plan.md`

---

## Startup Commands

### Session 1 — Runtime Core
```bash
cd /Users/ho/code/garmin-personal-coach-runtime
claude
```

### Session 2 — Research
```bash
cd /Users/ho/code/garmin-personal-coach-research
claude
```

### Session 3 — Architecture / Dashboard Spec
```bash
cd /Users/ho/code/garmin-personal-coach-architecture
claude
```

Optional review session later:

```bash
cd /Users/ho/code/garmin-personal-coach
claude
```

---

## What "Good Parallelism" Looks Like

At the end of this phase, success looks like:

- runtime lane closes real product gaps,
- research lane collapses unknowns into decisions,
- architecture lane prepares the next UI layer without causing rework,
- no one fights merge conflicts over the same files,
- the product becomes more real, not just more busy.
