# Manual Verification Runbook

This runbook exists because passing unit tests is not enough to prove PRD fidelity.
Use it before calling a stream or release candidate complete.

## qa-manual-001 / QA-MANUAL-001 — Morning briefing readiness downgrade

Verify:
- readiness score is shown,
- downgrade reason is visible,
- adjusted workout path is explicit,
- user actions are available.

Expected evidence:
- score/level rendered,
- explanation of why the session changed,
- no unsafe hard-session recommendation when readiness is low.

## qa-manual-002 / QA-MANUAL-002 — Post-workout nutrition + feedback loop

Verify:
- activity triggers post-workout summary,
- recovery nutrition appears,
- subjective prompts follow,
- timeout/skip/cancel do not become fake persisted values,
- low-confidence food photo requires confirmation.

Expected evidence:
- summary rendered,
- nutrition advice rendered,
- explicit abort or confirmation state,
- persisted feedback/meal records match expectations.

## qa-manual-003 / QA-MANUAL-003 — Onboarding resume and partial state

Verify:
- Phase 1 creates a usable coaching profile,
- Phase 2 timeout stores explicit resume point,
- rerun resumes from last incomplete step,
- Garmin auth failure does not mark onboarding complete.

Expected evidence:
- progress state contains current step,
- no duplicated Phase 1 prompts on resume,
- no corrupted profile fields from timeout/cancel.

## qa-manual-004 / QA-MANUAL-004 — Weekly report rendering

Verify:
- computed metrics appear consistently,
- missing-data mode explains missing inputs instead of inventing values,
- coach comment remains coherent,
- next-step or advisory text is visible.

Expected evidence:
- stable repeated output for same fixture,
- no hallucinated CTL/ATL/TSB/distance values,
- explicit missing-data note when inputs are absent.
