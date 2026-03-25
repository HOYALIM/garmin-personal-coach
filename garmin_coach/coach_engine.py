"""Coaching engine — scoring + recommendation logic."""

from garmin_coach.models import (
    MorningMetrics,
    MorningResult,
    Phase,
    SessionClass,
    Status,
)
from garmin_coach.plan import classify_session, get_session_purpose, get_week_brief


def score_sleep(hours: float | None, phase: Phase) -> tuple[int, str | None]:
    if phase == Phase.PRECHECK:
        return 0, None
    if hours is None:
        return 0, None
    if hours >= 7:
        return 0, None
    if hours >= 6:
        return 1, "sleep slightly short"
    return 2, "sleep poor"


def score_rhr(resting_hr: int | None, baseline: float | None) -> tuple[int, str | None]:
    if resting_hr is None or baseline is None:
        return 0, None
    delta = resting_hr - baseline
    if delta <= 3:
        return 0, None
    if delta <= 7:
        return 1, f"RHR +{delta:.0f} vs baseline"
    return 2, f"RHR +{delta:.0f} vs baseline"


def score_hrv_or_readiness(
    hrv_status: str | None, readiness: int | None
) -> tuple[int, str | None]:
    status = (hrv_status or "").lower()
    if readiness is not None:
        if readiness >= 65:
            return 0, None
        if readiness >= 40:
            return 1, "readiness fair"
        return 2, "readiness low"
    if status in {"balanced", "normal", "good"}:
        return 0, None
    if status in {"fair", "low", "slightly low", "moderate"}:
        return 1, "HRV a bit low"
    if status:
        return 2, "HRV suppressed"
    return 0, None


def score_body_battery(value: int | None) -> tuple[int, str | None]:
    if value is None:
        return 0, None
    if value >= 60:
        return 0, None
    if value >= 35:
        return 1, "body battery modest"
    return 2, "body battery low"


def score_subjective(
    soreness: int, pain: bool, illness: bool
) -> tuple[int, str | None]:
    if pain or illness:
        return 2, "pain or illness"
    if soreness <= 2:
        return 0, None
    if soreness == 3:
        return 1, "legs heavy"
    return 2, "soreness high"


def classify(total_score: int, pain: bool, illness: bool) -> Status:
    if pain or illness:
        return Status.RED
    if total_score <= 2:
        return Status.GREEN
    if total_score <= 5:
        return Status.YELLOW
    return Status.RED


def recommend(status: Status, planned: str) -> str:
    lower = planned.lower()
    if status == Status.GREEN:
        return planned
    if status == Status.YELLOW:
        if any(
            w in lower
            for w in ("threshold", "interval", "hill", "fartlek", "mp", "marathon")
        ):
            return "45-50 min easy only, skip hard reps"
        if "long run" in lower:
            return "Reduce long run 10-25%, keep fully easy"
        return "Shorten easy run 15-30%, skip extras"
    return "Rest or 20-30 min very easy only"


def get_execution_guidance(
    planned: str, recommendation: str, status: Status
) -> list[str]:
    text = recommendation.lower()
    lower = planned.lower()
    if "threshold" in lower and status == Status.GREEN:
        return [
            "Warm up 10-15 min easy first.",
            "Start conservatively — finish each rep strong.",
            "If you blow up before the last rep, back off.",
        ]
    if "45-50 min easy only" in text:
        return [
            "Today is quality converted to easy.",
            "Zone 2 pace, conversational breathing.",
            "Shorter is fine if you feel heavy.",
        ]
    if "long run" in lower:
        return [
            "First 20-30 min very easy.",
            "Fuel and hydrate as planned.",
            "If you fade hard, finish easy.",
        ]
    if "easy" in lower:
        return [
            "Keep it conversational.",
            "Breathe through your nose when possible.",
            "If you'd want to go longer after, that's the right pace.",
        ]
    if "rest" in text or "very easy" in text:
        return ["No hard effort. Walk or very light mobility only."]
    return ["Stay controlled. Next session is more important than today's."]


def get_pace_hr_guide(planned: str, recommendation: str, status: Status) -> str:
    lower = recommendation.lower()
    planned_lower = planned.lower()
    if any(x in lower for x in ("easy", "conversational")) or "easy" in planned_lower:
        return "Zone 2 / conversational / ~6:20-7:00/km"
    if "threshold" in planned_lower and status == Status.GREEN:
        return "Warm-up easy. Work sets: comfortably hard. Zone 4."
    if "mp" in planned_lower:
        return "Marathon pace feel. Stable rhythm, don't surge."
    if "long run" in planned_lower:
        return "Zone 2 early. Easy throughout unless steady is planned."
    if "rest" in lower:
        return "Rest day. No intensity."
    return "Controlled effort. No red-line running."


def get_downgrade_rule(status: Status, planned: str) -> str:
    lower = planned.lower()
    if status == Status.GREEN:
        if "threshold" in lower or "mp" in lower:
            return "Downgrade: if warm-up still feels heavy, go easy only."
        return "Downgrade: if first 10-15 min feels bad, cut 15-25%."
    if status == Status.YELLOW:
        return "Downgrade: if HR spikes or legs are heavy, drop to easy or walk."
    return "Downgrade: any pain/dizziness/fatigue — stop and rest."


def evaluate(
    date: str,
    phase: Phase,
    week_number: int,
    planned: str,
    metrics: MorningMetrics,
    rhr_baseline: float | None,
    soreness: int = 2,
    pain: bool = False,
    illness: bool = False,
) -> MorningResult:
    metrics.rhr_baseline = rhr_baseline
    reasons: list[str] = []
    parts = [
        score_sleep(metrics.sleep_hours, phase),
        score_rhr(metrics.resting_hr, rhr_baseline),
        score_hrv_or_readiness(metrics.hrv_status, metrics.training_readiness),
        score_body_battery(metrics.body_battery),
        score_subjective(soreness, pain, illness),
    ]
    total_score = 0
    for points, reason in parts:
        total_score += points
        if reason:
            reasons.append(reason)

    status = classify(total_score, pain, illness)
    recommendation = recommend(status, planned)
    session_class = classify_session(planned)

    freshness = {
        "sleep_complete": metrics.sleep_hours is not None,
        "post_wake_data_used": phase == Phase.FINAL,
    }

    return MorningResult(
        date=date,
        phase=phase,
        week=week_number,
        planned_session=planned,
        recommended_session=recommendation,
        status=status,
        reasons=reasons,
        total_score=total_score,
        week_brief=get_week_brief(week_number),
        session_purpose=get_session_purpose(planned),
        execution_guidance=get_execution_guidance(planned, recommendation, status),
        pace_hr_guidance=get_pace_hr_guide(planned, recommendation, status),
        downgrade_rule=get_downgrade_rule(status, planned),
        metrics=metrics,
        freshness=freshness,
        session_class=session_class,
    )
