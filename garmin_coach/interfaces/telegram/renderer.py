"""Message rendering — format data models into Telegram-friendly text.

Style guide:
- Emoji consistency: 🏃 workout, 😴 sleep, 💪 fitness, 🍽️ nutrition, ⚠️ warning
- Numbers: 1 decimal place
- Korean language, casual-polite tone
"""

from __future__ import annotations

from typing import Any


def render_readiness(readiness: dict[str, Any]) -> str:
    """Render ReadinessScore data into a Telegram message."""
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
    lines = ["📅 이번 주 계획:\n━━━━━━━━━━━━━━━━━━"]

    days = plan.get("days", [])
    day_names = ["월", "화", "수", "목", "금", "토", "일"]
    for i, day in enumerate(days):
        name = day_names[i] if i < len(day_names) else f"Day{i+1}"
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
    """Render weekly report — may produce multiple messages.

    Returns a list of message strings (split for Telegram 4096 char limit).
    """
    messages: list[str] = []

    # Header
    period = report.get("period", "")
    header = f"📊 주간 트레이닝 리포트 ({period})\n"

    # Summary section
    summary_lines = [header, "🏃 이번 주 요약:\n━━━━━━━━━━━━━━━━━━"]
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

    # Training load
    load = report.get("training_load", {})
    if load:
        summary_lines.append("\n📈 트레이닝 로드:")
        ctl = load.get("ctl")
        if ctl is not None:
            summary_lines.append(f"- CTL: {ctl:.1f}")
        atl = load.get("atl")
        if atl is not None:
            summary_lines.append(f"- ATL: {atl:.1f}")
        tsb = load.get("tsb")
        if tsb is not None:
            emoji = "🟢" if tsb > -10 else ("🟡" if tsb > -25 else "🔴")
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

    # Coach comment
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
