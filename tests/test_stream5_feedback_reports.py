import asyncio
import json
from datetime import date
from typing import Any, cast


def test_duplicate_activity_feedback_does_not_double_count_or_retrigger_guardrail(
    monkeypatch, tmp_path
):
    import garmin_coach.telegram_bot as telegram_bot
    from garmin_coach.storage.database import GarminCoachDatabase

    monkeypatch.setattr(telegram_bot, "GUARDRAIL_DIR", tmp_path)
    db = GarminCoachDatabase(":memory:")
    store = telegram_bot._FeedbackStore(cast(Any, object()), db)

    asyncio.run(
        store.save_feedback(
            "u1",
            "activity-1",
            {
                "session_date": "2026-04-08",
                "feeling": "pain",
                "pain_detail": {"body_part": "knee", "severity": "moderate"},
                "collection_status": "complete",
            },
        )
    )
    first = db.load_feedback("u1", "activity-1")
    assert first is not None
    assert first["pain_report"]["consecutive_count"] == 1
    assert len(db.list_feedback("u1")) == 1
    assert not (tmp_path / "u1.json").exists()

    asyncio.run(
        store.save_feedback(
            "u1",
            "activity-1",
            {
                "session_date": "2026-04-08",
                "feeling": "pain",
                "pain_detail": {"body_part": "knee", "severity": "moderate"},
                "collection_status": "complete",
                "source_event_id": "evt-duplicate",
            },
        )
    )
    duplicate = db.load_feedback("u1", "activity-1")
    assert duplicate is not None
    assert duplicate["pain_report"]["consecutive_count"] == 1
    assert len(db.list_feedback("u1")) == 1

    asyncio.run(
        store.save_feedback(
            "u1",
            "activity-2",
            {
                "session_date": "2026-04-09",
                "feeling": "pain",
                "pain_detail": {"body_part": "knee", "severity": "moderate"},
                "collection_status": "complete",
            },
        )
    )
    second = db.load_feedback("u1", "activity-2")
    assert second is not None
    assert second["pain_report"]["consecutive_count"] == 2
    guardrail = json.loads((tmp_path / "u1.json").read_text())
    assert guardrail["pain_reports_count"] == 2

    asyncio.run(
        store.save_feedback(
            "u1",
            "activity-2",
            {
                "session_date": "2026-04-09",
                "feeling": "pain",
                "pain_detail": {"body_part": "knee", "severity": "moderate"},
                "collection_status": "complete",
                "source_event_id": "evt-duplicate-2",
            },
        )
    )
    second_duplicate = db.load_feedback("u1", "activity-2")
    assert second_duplicate is not None
    assert second_duplicate["pain_report"]["consecutive_count"] == 2
    guardrail_again = json.loads((tmp_path / "u1.json").read_text())
    assert guardrail_again["pain_reports_count"] == 2


def test_post_workout_timeout_persists_partial_feedback_and_resume_merges_answers(
    monkeypatch, tmp_path
):
    import garmin_coach.telegram_bot as telegram_bot
    from garmin_coach.flows.post_workout import PostWorkoutFlow
    from garmin_coach.ports import InputAborted, InputAbortReason, InputType
    from garmin_coach.storage.database import GarminCoachDatabase

    monkeypatch.setattr(telegram_bot, "GUARDRAIL_DIR", tmp_path)
    db = GarminCoachDatabase(":memory:")
    store = telegram_bot._FeedbackStore(cast(Any, object()), db)

    class TimeoutPort:
        def __init__(self):
            self.calls = 0

        async def send_message(self, user_id, text, buttons=None):
            return None

        async def request_select(self, user_id, prompt, options):
            self.calls += 1
            if self.calls == 1:
                return "7-8"
            raise InputAborted(InputType.SELECT, InputAbortReason.TIMEOUT)

        async def request_text(self, user_id, prompt):
            raise AssertionError("note should not be requested after timeout")

    class FullPort:
        async def send_message(self, user_id, text, buttons=None):
            return None

        async def request_select(self, user_id, prompt, options):
            if "RPE" in prompt:
                return "7-8"
            return "bad"

        async def request_text(self, user_id, prompt):
            return "legs felt heavy"

    class FakeAnalyzer:
        async def analyze(self, user_id, activity):
            return None

    activity = {"activity_id": "run-1", "type": "easy", "duration_min": 45}
    timeout_flow = PostWorkoutFlow(cast(Any, TimeoutPort()), FakeAnalyzer(), feedback_agg=store)
    asyncio.run(timeout_flow.execute("u1", activity))

    partial = db.load_feedback("u1", "run-1")
    assert partial is not None
    assert partial["collection_status"] == "timeout"
    assert partial["rpe"] == 7
    assert partial["feeling"] is None
    assert partial["pending_keys"] == ["feeling", "note"]

    full_flow = PostWorkoutFlow(cast(Any, FullPort()), FakeAnalyzer(), feedback_agg=store)
    asyncio.run(full_flow.execute("u1", activity))

    resumed = db.load_feedback("u1", "run-1")
    assert resumed is not None
    assert resumed["collection_status"] == "complete"
    assert resumed["rpe"] == 7
    assert resumed["feeling"] == "bad"
    assert resumed["note"] == "legs felt heavy"
    assert resumed["pending_keys"] == []
    assert resumed["answered_keys"] == ["feeling", "note", "rpe"]


def test_feedback_summary_is_typed_and_reports_partial_state():
    from garmin_coach.feedback import FeedbackAggregatorService
    from garmin_coach.models.feedback import FeedbackSummary
    from garmin_coach.storage.database import GarminCoachDatabase

    db = GarminCoachDatabase(":memory:")
    service = FeedbackAggregatorService(db)
    service.save_feedback(
        "u1",
        "a1",
        {"session_date": "2026-04-07", "rpe": "8", "collection_status": "complete"},
    )
    service.save_feedback(
        "u1",
        "a2",
        {
            "session_date": "2026-04-08",
            "collection_status": "cancelled",
            "answered_keys": [],
            "pending_keys": ["rpe", "feeling"],
        },
    )

    summary = service.get_feedback_summary("u1", days=14, end_date=date(2026, 4, 8))
    assert isinstance(summary, FeedbackSummary)
    assert summary.average_rpe == 8.0
    assert summary.completed_feedbacks == 1
    assert summary.skipped_feedbacks == 1
    assert any("부분 완료" in note or "건너뛰기" in note for note in summary.notes)


def test_weekly_report_is_deterministic_and_uses_only_stored_data():
    from garmin_coach.feedback import FeedbackAggregatorService
    from garmin_coach.models.feedback import FeedbackSummary
    from garmin_coach.reports.weekly import WeeklyReportGenerator
    from garmin_coach.storage.database import GarminCoachDatabase

    db = GarminCoachDatabase(":memory:")
    db.save_activity(
        "u1",
        "a1",
        "2026-04-08",
        {
            "activity_id": "a1",
            "start_time": "2026-04-08T06:30:00",
            "distance_km": 10.0,
            "duration_min": 50.0,
        },
    )
    db.save_daily_health(
        "u1",
        "2026-04-08",
        {
            "sleep": {"overallScore": 81},
            "body_battery": {"morning_value": 72},
            "training_load": {"ctl": 42, "atl": 48, "tsb": -6, "ramp_rate": 3.2},
        },
    )
    feedback_service = FeedbackAggregatorService(db)
    feedback_service.save_feedback(
        "u1",
        "a1",
        {"session_date": "2026-04-08", "rpe": "7", "collection_status": "complete"},
    )
    generator = WeeklyReportGenerator(db, feedback_service)

    report_a = asyncio.run(generator.generate("u1", end_date=date(2026, 4, 8)))
    report_b = asyncio.run(generator.generate("u1", end_date=date(2026, 4, 8)))

    assert report_a.to_dict() == report_b.to_dict()
    assert report_a.summary.total_distance_km == 10.0
    assert report_a.summary.total_time == "0.8h"
    assert isinstance(report_a.feedback, FeedbackSummary)
    assert report_a.feedback.average_rpe == 7.0


def test_partial_data_report_surfaces_missing_data_messages_without_fabricating_values():
    from garmin_coach.feedback import FeedbackAggregatorService
    from garmin_coach.interfaces.telegram.renderer import render_weekly_report
    from garmin_coach.reports.weekly import WeeklyReportGenerator
    from garmin_coach.storage.database import GarminCoachDatabase

    db = GarminCoachDatabase(":memory:")
    generator = WeeklyReportGenerator(db, FeedbackAggregatorService(db))

    report = asyncio.run(generator.generate("u1", end_date=date(2026, 4, 8)))
    rendered = "\n".join(render_weekly_report(cast(Any, report)))

    assert report.summary.sessions == 0
    assert report.summary.total_distance_km is None
    assert report.summary.total_time is None
    assert report.training_load is None
    assert report.recovery is None
    assert report.missing_data_notes
    assert "운동 활동이 없어" in rendered
    assert "데이터가 충분하지 않아" in report.coach_comment


def test_workout_and_food_photo_paths_stay_separate():
    import garmin_coach.telegram_bot as telegram_bot

    calls = {"workout": 0, "food": 0}

    class FakeBridge:
        def latest_activity_payload(self, user_id):
            calls["workout"] += 1
            return {"activity_id": "a1", "type": "run"}

        async def create_workout_analysis(self, user_id, activity):
            return type("Analysis", (), {"to_dict": lambda self: {"summary": "ok"}})()

    class FakeFoodAnalyzer:
        async def analyze(self, user_id, photo):
            calls["food"] += 1
            return {
                "items_detected": ["meal"],
                "estimated_macros": {"carbs_g": 20, "protein_g": 10},
            }

    router = telegram_bot._PhotoRouter(FakeBridge(), FakeFoodAnalyzer())
    asyncio.run(router.analyze_workout("u1", b"\x89PNGdemo"))
    assert calls == {"workout": 1, "food": 0}

    asyncio.run(router.analyze_food("u1", b"\xff\xd8\xffdemo"))
    assert calls == {"workout": 1, "food": 1}
