# Final Pre-Release Review

## What to Check Tonight

Before calling this version ready, verify the product from the user’s point of view in this order.

## 1. Local Power-User Story

Can a user:

- install the package,
- connect Garmin,
- optionally connect Strava,
- run setup,
- ask for status,
- log a workout,
- use Telegram,
- connect via MCP/OpenClaw?

If the answer is yes, the release has a coherent product story.

## 2. Core Truth Story

Can you explain, in one sentence, where the product gets its truth?

Expected answer:

> Garmin is primary, Strava is supplemental sync, and the durable coaching state lives in the shared training-load model.

If that statement is not true after merge, stop.

## 3. Nutrition Story

Can you honestly say:

> The product now gives lightweight personalized nutrition coaching based on setup preferences and training context.

But also:

> It does not yet do food image analysis, meal tracking, or calorie-from-photo estimation.

If both are true, the nutrition layer is release-safe.

## 4. Honest Beta Positioning

The release should be described as:

- local / power-user friendly,
- Garmin-first,
- usable now via CLI / Telegram / MCP,
- still early for broader consumer UX.

Do not position it as a polished mainstream consumer app yet.

## 5. Final Go Condition

You are ready to release when:

- lane 1 / 2 / 3 are merged,
- the release checklist is green,
- the README matches the runtime truth,
- no unresolved blocker remains in the release audit.

## If Not Releasing Tonight

The most valuable next step remains:

1. thin backend API layer,
2. then read-only dashboard,
3. then future platform expansions.
