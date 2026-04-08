# Pre-Merge Gate Checklist

This is the hard merge gate for PRD-driven work.

`docs/release/*` may still say whether a release is worth shipping.
This file answers a different question:

> **Can this branch be merged without violating PRD truth, stream ownership, or QA guarantees?**

If any item below is not proven with evidence, merge is **NO-GO**.

---

## 1. Git / PR State

- [ ] Current branch is the intended PR branch, not an ad-hoc local branch.
- [ ] Working tree is clean or every non-clean file is explicitly out of merge scope.
- [ ] PR exists and is the intended merge target.
- [ ] PR base/head match the planned merge path.
- [ ] No accidental local-only fixes remain unpushed.

Required evidence:
- `git status --short`
- current branch name
- PR URL / PR number

---

## 2. PRD Traceability

- [ ] Every changed PRD-relevant behavior maps to one or more `case_id` entries in `docs/qa/prd-acceptance-matrix.yaml`.
- [ ] No changed product behavior exists without an automated test or named manual QA case.
- [ ] Acceptance matrix entries point to real test files / runbook cases.

Required evidence:
- touched `case_id`s
- impacted streams
- referenced test files and manual QA IDs

NO-GO if:
- a changed behavior cannot be named in PRD terms,
- or a PRD behavior changed without traceability.

---

## 3. Stream Ownership / Boundary Integrity

- [ ] Fixes stayed within the owning stream or explicitly documented cross-stream touchpoints.
- [ ] `flows/` remain channel-agnostic.
- [ ] No runtime shortcut bypasses the intended architecture layer.
- [ ] Structured-data boundaries remain intact where required.

Required evidence:
- changed file list grouped by stream
- any intentional cross-stream edits with justification

NO-GO if:
- Telegram/interface imports leak into `flows/`,
- or a stream fixes its problem by bypassing another stream’s contract.

---

## 4. Automated Verification Gate

- [ ] Stream-owned tests pass.
- [ ] PRD acceptance enforcement tests pass.
- [ ] Any known targeted regression suite for the changed area passes.
- [ ] Import/runtime smoke checks pass where relevant.
- [ ] Changed-file diagnostics are clean.

Required evidence:
- exact commands run
- pass/fail counts
- any warnings called out explicitly

NO-GO if:
- tests are selectively omitted without justification,
- or diagnostics fail on changed files.

---

## 5. Manual Verification Gate

Run every required manual case referenced by impacted `case_id`s.

- [ ] `qa-manual-001` if readiness / morning path changed
- [ ] `qa-manual-002` if post-workout / nutrition / feedback path changed
- [ ] `qa-manual-003` if onboarding / settings / profile path changed
- [ ] `qa-manual-004` if weekly report / deterministic reporting changed

Required evidence:
- actual output snippets or screenshots
- what was verified
- result (PASS / FAIL)

NO-GO if:
- manual QA is marked “should work” instead of actually executed,
- or required runbook cases were skipped.

---

## 6. Safety / Data Integrity Gate

- [ ] No known blocker remains in owned scope.
- [ ] No timeout/cancel path silently becomes business data.
- [ ] No duplicate processing path can silently double-write critical state where idempotency is required.
- [ ] No known safety rule regression exists.
- [ ] No known sensitive-data leakage path remains.

Required evidence:
- blocker list = empty, or explicitly documented as non-owned / non-merge-blocking

NO-GO if:
- there is any open blocker in owned scope,
- or any safety/privacy issue is hand-waved as follow-up.

---

## 7. Docs Truth Gate

- [ ] README / release docs do not overclaim what the code currently does.
- [ ] If the QA architecture or acceptance matrix changed, related docs are updated.
- [ ] If limitations remain, they are stated honestly.

Required evidence:
- docs touched or confirmed not needed

NO-GO if:
- docs describe a capability that is still missing or only partially true.

---

## 8. Final Decision

Merge is **GO** only if all sections above are PASS with evidence.

Otherwise merge is **NO-GO**.

Record the outcome in `docs/qa/pre-merge-evidence-template.md` or an equivalent filled copy.
