from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace
from typing import Any, cast


def test_morning_briefing_matches_prd_style_components():
    from garmin_coach.flows.morning_briefing import MorningBriefingFlow

    class Port:
        def __init__(self):
            self.messages = []

        async def send_message(self, user_id, text, buttons=None):
            self.messages.append((text, buttons))

    class Readiness:
        async def get_readiness(self, user_id):
            return {
                "score": 82,
                "level": "green",
                "sleep_duration": "7h 35m",
                "rhr_baseline": 49,
                "hrv_value": 56,
                "hrv_baseline": 52,
                "components": {
                    "sleep_score": 85,
                    "hrv_deviation_pct": 7.7,
                    "body_battery": 78,
                    "rhr": 48,
                    "tsb": -5.2,
                },
            }

    class Coaching:
        async def generate_daily_coaching(self, user_id, readiness):
            return {
                "session_type": "인터벌 6x1000m @ 4:00/km",
                "text": "컨디션이 좋으니 계획대로 진행! 화이팅 💪",
            }

    class Nutrition:
        async def get_pre_workout_advice(self, user_id, session_type):
            return {
                "description": "운동 2시간 전까지 탄수화물 위주 가벼운 식사 권장",
                "examples": ["바나나", "토스트", "꿀"],
            }

    port = Port()
    flow = MorningBriefingFlow(cast(Any, port), Readiness(), Coaching(), Nutrition())
    asyncio.run(flow.execute("u1"))
    text, buttons = port.messages[0]

    assert "☀️ 좋은 아침이에요! 오늘의 컨디션 브리핑:" in text
    assert "🔋 Readiness Score: 82/100 🟢" in text
    assert "- 수면: 7h 35m (Score: 85) ✅" in text
    assert "- HRV: 56ms (기준선 52ms, +7.7%) ✅" in text
    assert "- Body Battery: 78 ✅" in text
    assert "- RHR: 48bpm (기준선 49) ✅" in text
    assert "- TSB: -5.2 🟢" in text
    assert "🍽️ 운동 전 식사 리마인더:" in text
    assert buttons is not None
    assert [button.label for button in buttons] == ["✅ 계획대로", "🔄 변경", "⏭️ 내일로 미루기"]


def test_post_workout_flow_matches_prd_style_message_and_feedback_sequence():
    from garmin_coach.flows.post_workout import PostWorkoutFlow

    class Port:
        def __init__(self):
            self.messages = []

        async def send_message(self, user_id, text, buttons=None):
            self.messages.append((text, buttons))

        async def request_select(self, user_id, prompt, options):
            if "RPE" in prompt:
                return "7-8"
            if "전체적인 느낌" in prompt:
                return "good"
            if "목표 세트를 모두 완료했나요?" in prompt:
                return "full"
            return "good"

        async def request_text(self, user_id, prompt):
            return "다리 묵직했어요"

    class Analyzer:
        async def analyze(self, user_id, activity):
            return SimpleNamespace(
                tss=85,
                training_effect_aerobic=4.2,
                training_effect_anaerobic=3.1,
                zone_distribution={"Zone 4": 62},
                coaching_notes="이전 유사 세션 대비 페이스 유지가 좋았습니다.",
            )

    class Recovery:
        async def get_advice(self, user_id, activity):
            return {
                "timing": "지금부터 30분 이내",
                "examples": [
                    "초코우유 500ml + 바나나",
                    "프로틴 쉐이크 + 탄수화물 소스",
                    "밥 한 공기 + 단백질 반찬",
                ],
                "rationale": "오늘은 하드 세션이었으므로 탄수화물 6-8g/kg 목표로 섭취하세요.",
            }

    class Feedback:
        def __init__(self):
            self.saved = []

        async def save_feedback(self, user_id, activity_id, feedback):
            self.saved.append(feedback)

    port = Port()
    agg = Feedback()
    flow = PostWorkoutFlow(cast(Any, port), Analyzer(), recovery_fuel=Recovery(), feedback_agg=agg)
    asyncio.run(
        flow.execute(
            "u1",
            {
                "activity_id": "a1",
                "type": "interval",
                "distance_km": 10.2,
                "duration_min": 52.5,
                "avg_hr": 168,
            },
        )
    )
    text, buttons = port.messages[0]

    assert "🏃‍♂️ interval 완료! 수고했어요." in text
    assert "거리: 10.2km" in text
    assert "평균 심박: 168bpm" in text
    assert "Zone 4: 62%" in text
    assert "Training Effect: 유산소 4.2 / 무산소 3.1" in text
    assert "TSS: 85" in text
    assert "🍽️ 회복 영양 권장:" in text
    assert buttons is not None
    assert [button.label for button in buttons] == [
        "👍 먹었어요",
        "⏰ 나중에 먹을게요",
        "📝 뭘 먹었는지 기록",
    ]
    assert agg.saved[0]["collection_status"] == "complete"
    assert agg.saved[0]["rpe"] == "7-8"


def test_weekly_report_renderer_matches_prd_style_sections():
    from garmin_coach.interfaces.telegram.renderer import render_weekly_report

    report = {
        "period": "3/31 - 4/6",
        "summary": {
            "sessions": 5,
            "total_distance_km": 48.3,
            "prev_distance_km": 45.1,
            "total_time": "4시간 22분",
            "average_pace": "5:25/km",
        },
        "training_load": {
            "ctl_start": 52.3,
            "ctl": 54.1,
            "atl_start": 61.2,
            "atl": 58.5,
            "tsb_start": -8.9,
            "tsb": -4.4,
            "ramp_rate": 3.4,
        },
        "recovery": {
            "avg_sleep": "7h 12m",
            "avg_sleep_score": 78,
            "hrv_trend": "안정 (기준선 52ms, 이번 주 평균 54ms)",
            "avg_body_battery": 72,
        },
        "nutrition": {
            "logged_meals": "8/15 (53% 기록률)",
            "avg_protein": "평균 1.4g/kg ✅",
            "hydration_response": "60%",
        },
        "feedback": {
            "average_rpe": 6.2,
            "pain_reports": "없음 ✅",
            "pace_achievement": "3/4 인터벌 (75%)",
        },
        "next_week_plan": "월: 이지런 8km (Zone 2)\n화: 인터벌 6x1000m @ 4:00/km",
        "coach_comment": "이번 주 훌륭했습니다! CTL이 안정적으로 상승 중이고, 회복 지표도 양호합니다.",
    }

    rendered = "\n".join(render_weekly_report(report))
    assert "📊 주간 트레이닝 리포트 (3/31 - 4/6)" in rendered
    assert "총 거리: 48.3km (지난주: 45.1km, +7.1%)" in rendered
    assert "평균 페이스: 5:25/km" in rendered
    assert "CTL: 52.3 → 54.1 (+1.8)" in rendered
    assert "ATL: 61.2 → 58.5 (-2.7)" in rendered
    assert "TSB: -8.9 → -4.4 🟢" in rendered
    assert "🍽️ 영양:" in rendered
    assert "📝 피드백 요약:" in rendered
    assert "🎯 다음 주 계획:" in rendered
    assert "💡 코치 코멘트:" in rendered
