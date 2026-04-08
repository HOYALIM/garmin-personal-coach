# Coaching Guardrails

## Hard stop conditions
- Block hard training when TSB is deeply negative or recovery markers are critical.
- Convert HR-based guidance to RPE when beta blockers or cardiac modifiers are present.
- Block sessions that violate injury clearance or explicit medical restrictions.
- Block any session that places meaningful load on an actively injured body part, even when clearance/restriction strings are absent.
- Add urgent medical escalation for low SpO2 and extreme heart-rate anomalies.

## Recovery protection
- Downgrade hard sessions when sleep, HRV, body battery, or resting HR indicate incomplete recovery.
- Warn on 3-day sleep debt, high ramp rate, high monotony, and excessive strain.
- Reduce weekly volume progression when increase exceeds the safe ramp threshold.

## Nutrition and environment safety
- Remove allergen-containing recommendations.
- Block BMR-below calorie prescriptions.
- Append environment warnings for extreme heat, WBGT, cold, and very poor air quality.

## Composition rule
- Multiple guardrails may trigger at once.
- The most severe action wins, but all required warnings and appended safety instructions must remain visible.
