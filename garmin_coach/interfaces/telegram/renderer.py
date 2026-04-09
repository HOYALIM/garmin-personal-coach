"""Message rendering — format data models into Telegram-friendly text.

Style guide:
- Emoji consistency: 🏃 workout, 😴 sleep, 💪 fitness, 🍽️ nutrition, ⚠️ warning
- Numbers: 1 decimal place
- Korean language, casual-polite tone
"""

from __future__ import annotations

from typing import Any


def _as_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        result = value.to_dict()
        if isinstance(result, dict):
            return result
    return {}


def render_readiness(readiness: dict[str, Any]) -> str:
    """Render ReadinessScore data into a Telegram message."""
    readiness = _as_payload(readiness)
    score = readiness.get("score", "?")
    level = readiness.get("level", "unknown").lower()
    emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴", "critical": "🚨"}.get(level, "⚪")

    lines = [f"🔋 Readiness: {score}/100 {emoji}"]

    components = readiness.get("components", {})
    field_map = {
        "sleep_score": ("수면", None),
        "hrv_deviation_pct": ("HRV", "%"),
        "body_battery": ("Body Battery", None),
        "rhr": ("RHR", "bpm"),
        "tsb": ("TSB", None),
        "stress_avg": ("스트레스", None),
    }
    for key, (label, unit) in field_map.items():
        val = components.get(key)
        if val is not None:
            suffix = f"{unit}" if unit else ""
            if key == "hrv_deviation_pct":
                sign = "+" if val > 0 else ""
                lines.append(f"- {label}: {sign}{val:.1f}{suffix} {'✅' if val >= -10 else '⚠️'}")
            elif key == "sleep_score":
                lines.append(f"- {label}: {val} {'✅' if val >= 70 else '⚠️'}")
            elif key == "body_battery":
                lines.append(f"- {label}: {val} {'✅' if val >= 50 else '⚠️'}")
            else:
                lines.append(f"- {label}: {val}{suffix}")

    return "\n".join(lines)


def render_workout_analysis(analysis: dict[str, Any]) -> str:
    """Render WorkoutAnalysis into Telegram message."""
    analysis = _as_payload(analysis)
    lines = ["📊 세션 분석:"]

    summary = analysis.get("summary", "")
    if summary:
        lines.append(summary)

    zones = analysis.get("zone_distribution", {})
    if zones:
        zone_parts = []
        for zone, pct in sorted(zones.items()):
            zone_parts.append(f"{zone}: {pct:.0f}%")
        lines.append("심박 Zone: " + " / ".join(zone_parts))

    comparison = analysis.get("comparison_to_recent")
    if comparison:
        lines.append(f"\n💬 이전 대비: {comparison}")

    notes = analysis.get("coaching_notes")
    if notes:
        lines.append(f"\n📝 {notes}")

    return "\n".join(lines)


def render_nutrition_advice(advice: dict[str, Any]) -> str:
    """Render nutrition advice into Telegram message."""
    advice = _as_payload(advice)
    lines = ["🍽️ 영양 권장:"]

    timing = advice.get("timing")
    if timing:
        lines.append(timing)

    macros = advice.get("macros", {})
    if macros:
        parts = []
        carbs = macros.get("carbs")
        if carbs:
            parts.append(f"탄수: {carbs}")
        protein = macros.get("protein")
        if protein:
            parts.append(f"단백: {protein}")
        if parts:
            lines.append(" | ".join(parts))

    examples = advice.get("examples", [])
    for ex in examples[:4]:
        lines.append(f"- {ex}")

    return "\n".join(lines)


def render_weekly_plan(plan: dict[str, Any]) -> str:
    """Render WeeklyPlan into Telegram message."""
    plan = _as_payload(plan)
    lines = ["📅 이번 주 계획:\n━━━━━━━━━━━━━━━━━━"]

    days = plan.get("days", [])
    day_names = ["월", "화", "수", "목", "금", "토", "일"]
    for i, day in enumerate(days):
        name = day_names[i] if i < len(day_names) else f"Day{i + 1}"
        session = day.get("description", day.get("session_type", ""))
        lines.append(f"{name}: {session}")

    total_tss = plan.get("total_tss")
    if total_tss:
        lines.append(f"\n예상 총 TSS: {total_tss:.0f}")

    notes = plan.get("notes")
    if notes:
        lines.append(f"\n💡 {notes}")

    return "\n".join(lines)


def render_weekly_report(report: dict[str, Any]) -> list[str]:
    return _render_periodic_report(report, "주간 트레이닝 리포트", "이번 주")


def render_monthly_report(report: dict[str, Any]) -> list[str]:
    return _render_periodic_report(report, "월간 트레이닝 리포트", "이번 달")


def _render_periodic_report(report: dict[str, Any], title: str, summary_label: str) -> list[str]:
    report = _as_payload(report)
    messages: list[str] = []

    period = report.get("period", "")
    header = f"📊 {title} ({period})\n"

    summary_lines = [header, f"🏃 {summary_label} 요약:\n━━━━━━━━━━━━━━━━━━"]
    s = report.get("summary", {})
    if s:
        summary_lines.append(f"운동 횟수: {s.get('sessions', '?')}회")
        dist = s.get("total_distance_km")
        if dist is not None:
            prev = s.get("prev_distance_km")
            diff = ""
            if prev and prev > 0:
                pct = (dist - prev) / prev * 100
                diff = f" (지난주: {prev:.1f}km, {'+' if pct > 0 else ''}{pct:.1f}%)"
                lines_text = f"총 거리: {dist:.1f}km{diff}"
            else:
                lines_text = f"총 거리: {dist:.1f}km"
            summary_lines.append(lines_text)
        total_time = s.get("total_time")
        if total_time:
            summary_lines.append(f"총 시간: {total_time}")
        avg_pace = s.get("average_pace")
        if avg_pace:
            summary_lines.append(f"평균 페이스: {avg_pace}")

    # Training load
    load = report.get("training_load", {})
    if load:
        summary_lines.append("\n📈 트레이닝 로드:")
        ctl = load.get("ctl")
        if ctl is not None:
            ctl_start = load.get("ctl_start")
            if ctl_start is not None:
                summary_lines.append(f"- CTL: {ctl_start:.1f} → {ctl:.1f} ({ctl - ctl_start:+.1f})")
            else:
                summary_lines.append(f"- CTL: {ctl:.1f}")
        atl = load.get("atl")
        if atl is not None:
            atl_start = load.get("atl_start")
            if atl_start is not None:
                summary_lines.append(f"- ATL: {atl_start:.1f} → {atl:.1f} ({atl - atl_start:+.1f})")
            else:
                summary_lines.append(f"- ATL: {atl:.1f}")
        tsb = load.get("tsb")
        if tsb is not None:
            emoji = "🟢" if tsb > -10 else ("🟡" if tsb > -25 else "🔴")
            tsb_start = load.get("tsb_start")
            if tsb_start is not None:
                summary_lines.append(f"- TSB: {tsb_start:.1f} → {tsb:.1f} {emoji}")
            else:
                summary_lines.append(f"- TSB: {tsb:.1f} {emoji}")
        ramp = load.get("ramp_rate")
        if ramp is not None:
            ok = "✅" if ramp <= 5 else "⚠️"
            summary_lines.append(f"- Ramp Rate: {ramp:.1f}%/주 {ok}")

    messages.append("\n".join(summary_lines))

    # Recovery section
    recovery = report.get("recovery", {})
    if recovery:
        rec_lines = ["😴 수면 & 회복:"]
        sleep_avg = recovery.get("avg_sleep")
        if sleep_avg:
            rec_lines.append(f"- 평균 수면: {sleep_avg}")
        sleep_score = recovery.get("avg_sleep_score")
        if sleep_score is not None:
            rec_lines.append(f"- 평균 Sleep Score: {sleep_score}/100")
        hrv = recovery.get("hrv_trend")
        if hrv:
            rec_lines.append(f"- HRV 트렌드: {hrv}")
        bb = recovery.get("avg_body_battery")
        if bb is not None:
            rec_lines.append(f"- Body Battery 평균: {bb}/100")
        messages.append("\n".join(rec_lines))

    nutrition = report.get("nutrition", {})
    if nutrition:
        nutrition_lines = ["🍽️ 영양:"]
        logged = nutrition.get("logged_meals")
        if logged:
            nutrition_lines.append(f"- 기록된 식사: {logged}")
        protein = nutrition.get("avg_protein")
        if protein:
            nutrition_lines.append(f"- 추정 일일 단백질: {protein}")
        hydration = nutrition.get("hydration_response")
        if hydration:
            nutrition_lines.append(f"- 수분 섭취 알림 응답률: {hydration}")
        if len(nutrition_lines) > 1:
            messages.append("\n".join(nutrition_lines))

    feedback = report.get("feedback", {})
    if feedback:
        feedback_lines = ["📝 피드백 요약:"]
        avg_rpe = feedback.get("average_rpe")
        if avg_rpe is not None:
            feedback_lines.append(f"- 평균 RPE: {avg_rpe}")
        pain_reports = feedback.get("pain_reports")
        if pain_reports:
            suffix = "회" if isinstance(pain_reports, (int, float)) else ""
            feedback_lines.append(f"- 통증 보고: {pain_reports}{suffix}")
        pace_achievement = feedback.get("pace_achievement")
        if pace_achievement:
            feedback_lines.append(f"- 목표 페이스 달성률: {pace_achievement}")
        partial = feedback.get("partial_feedbacks")
        skipped = feedback.get("skipped_feedbacks")
        if partial:
            feedback_lines.append(f"- 부분 완료 피드백: {partial}회")
        if skipped:
            feedback_lines.append(f"- 건너뛰기/중단 피드백: {skipped}회")
        feedback_notes = feedback.get("notes") or []
        for note in feedback_notes[:3]:
            feedback_lines.append(f"- {note}")
        if len(feedback_lines) > 1:
            messages.append("\n".join(feedback_lines))

    missing_data_notes = report.get("missing_data_notes") or []
    if missing_data_notes:
        missing_lines = ["ℹ️ 데이터 상태:"]
        for note in missing_data_notes:
            missing_lines.append(f"- {note}")
        messages.append("\n".join(missing_lines))

    # Coach comment
    next_week_plan = report.get("next_week_plan")
    if next_week_plan:
        messages.append(f"🎯 다음 주 계획:\n━━━━━━━━━━━━━━━━━━\n{next_week_plan}")

    comment = report.get("coach_comment")
    if comment:
        messages.append(f"💡 코치 코멘트:\n> {comment}")

    return messages


def render_guardrail_notice(reason: str, severity: str = "warning") -> str:
    """Render guardrail adjustment notice."""
    icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(severity, "⚠️")
    return f"{icon} 코치가 오늘의 계획을 조정했습니다:\n{reason}"


def render_help() -> str:
    """Render /help command output."""
    return (
        "🏃 Garmin Personal Coach 도움말\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📋 명령어:\n"
        "/start — 온보딩 시작\n"
        "/today — 오늘의 컨디션 + 계획\n"
        "/week — 이번 주 계획 보기\n"
        "/report — 즉시 주간 리포트 생성\n"
        "/feedback — 수동 피드백 입력\n"
        "/nutrition — 오늘의 영양 가이드\n"
        "/settings — 프로필/설정 수정\n"
        "/goals — 목표 확인/수정\n"
        "/injury — 부상 보고\n"
        "/help — 이 도움말\n\n"
        "📸 사진을 보내면 자동으로 분석합니다:\n"
        "- 운동 캡쳐 → 세션 데이터 분석\n"
        "- 식단 사진 → 매크로 추정\n\n"
        "💬 자유롭게 질문해도 됩니다!\n"
        '예: "오늘 뭐 먹으면 좋아?", "내 CTL 어때?"'
    )


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2 parse mode."""
    special = r"_*[]()~`>#+-=|{}.!"
    result = []
    for ch in text:
        if ch in special:
            result.append(f"\\{ch}")
        else:
            result.append(ch)
    return "".join(result)
