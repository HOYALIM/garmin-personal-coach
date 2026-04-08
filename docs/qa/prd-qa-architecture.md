# PRD-First QA Architecture

## Goal

This project does not treat "implementation exists" as completion.
Completion means the behavior required by `garmin-coach-prd.md` is enforced by:

1. executable tests,
2. architecture guard checks,
3. targeted manual verification procedures.

The PRD is the highest-fidelity source for user-visible behavior, example outputs,
and safety expectations. `work-orders-5stream.md` defines execution ownership.
When they differ in strictness, QA follows the stricter interpretation.

## Test Layers

### 1. Contract / Invariant Tests

Purpose: prove low-level safety and domain invariants.

Examples:
- guardrails never allow unsafe advice to bypass hard rules
- timeout/cancel are explicit states, not business values
- idempotent persistence for meal logging and feedback collection
- deterministic report generation from stored data only

Current examples:
- `tests/test_stream1_guardrails.py`
- `tests/test_stream3_onboarding_settings.py`
- `tests/test_stream4_nutrition_contracts.py`
- `tests/test_stream5_feedback_reports.py`

### 2. Stream-Level Integration Tests

Purpose: prove each stream's owned flow behaves correctly through its real service boundary.

Examples:
- Telegram runtime wiring for Stream 2
- onboarding resume + persistence side effects for Stream 3
- photo confirmation / non-authoritative nutrition path for Stream 4
- post-workout partial feedback resume and typed report generation for Stream 5

Current example:
- `tests/test_stream2_telegram.py`

### 3. PRD Example Acceptance Tests

Purpose: encode PRD examples and exact expected behaviors so future work cannot drift.

Examples that must be represented either in automated tests or the runbook:
- morning briefing readiness thresholds and downgrade behavior
- post-workout nutrition recommendation structure and buttons
- injury/pain flow follow-up behavior
- weekly/monthly report content requirements
- onboarding branching for marathon and rehab users

These are tracked in `docs/qa/prd-acceptance-matrix.yaml`.

### 4. Architecture Guard Tests

Purpose: stop structural drift even when feature tests still pass.

Examples:
- `flows/` must not import Telegram interfaces
- stream outputs remain structured where required
- runtime paths use the intended stream boundaries
- local-only / sensitive-data handling promises are preserved

### 5. Manual Verification Runbook

Purpose: verify user-visible behavior that is too expensive or brittle to encode fully in automated tests.

This is not optional. Manual QA is required for:
- Telegram-first flows and message ergonomics
- long, user-visible report rendering
- end-to-end onboarding continuity
- real post-workout feedback interaction timing

See `docs/qa/manual-verification-runbook.md`.

### 6. Pre-Merge Gate Checklist

Purpose: provide the final hard gate before merge.

Use `docs/qa/pre-merge-gate-checklist.md` together with
`docs/qa/pre-merge-evidence-template.md` to record the exact evidence for merge.

## Acceptance Rules

Every PRD-critical behavior must have all of the following:

1. `case_id`
2. owning stream
3. PRD source section
4. expected outcome in binary terms
5. at least one verification target:
   - automated test file, and/or
   - named manual QA case

If a PRD behavior has no verification target, it is incomplete.

## Merge / Review Gates

Before calling a stream complete:

1. stream-owned tests pass,
2. changed-file diagnostics are clean,
3. PRD acceptance matrix entries for that stream have verification coverage,
4. required manual QA cases have been executed or explicitly queued,
5. no known blocker remains open in the stream's owned scope.

If any of the above is unknown, merge is a NO-GO.

## Scope Boundary Rule

The QA architecture is PRD-first, but still stream-aware:

- Stream 1: data / readiness / safety
- Stream 2: runtime / flow orchestration / Telegram delivery
- Stream 3: onboarding / profile / settings
- Stream 4: nutrition
- Stream 5: feedback / reports

Cross-stream issues are allowed in QA, but ownership of fixes still follows the work-order.
