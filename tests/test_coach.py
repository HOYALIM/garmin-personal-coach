"""Tests for Garmin Personal Coach modules."""

import os
import re
import sys

import pytest

# Allow imports from garmin_coach package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("GARMIN_PLAN_START_DATE", "2026-01-01")

from garmin_coach.coach_engine import (
    classify,
    evaluate,
    recommend,
    score_body_battery,
    score_rhr,
    score_sleep,
    score_subjective,
)
from garmin_coach.models import MorningMetrics, Phase, SessionClass, Status, WorkoutLog
from garmin_coach.plan import (
    classify_session,
    get_planned_session,
    get_week_brief,
    get_week_number,
)
from garmin_coach.triggers import detect_trigger, TriggerType
from garmin_coach.calendar_sync import (
    strip_workout_block,
    merge_description,
    WORKOUT_BLOCK_START,
    WORKOUT_BLOCK_END,
)
from garmin_coach.garmin_writeback import GARMIN_WRITEBACK_STATUS


class TestPlanLookup:
    def test_week_number_week1(self):
        assert get_week_number("2026-01-01") == 1
        assert get_week_number("2026-01-07") == 1

    def test_week_number_week2(self):
        assert get_week_number("2026-01-08") == 2

    def test_week_number_boundary(self):
        assert get_week_number("2026-04-13") == 14
        assert get_week_number("2026-04-20") == 14

    def test_planned_session_week1_monday(self):
        week, session = get_planned_session("2026-01-01")
        assert week == 1
        assert "5 km easy" in session

    def test_classify_session(self):
        assert classify_session("7 km easy") == SessionClass.EASY
        assert classify_session("Threshold: 4 x 6 min") == SessionClass.THRESHOLD
        assert classify_session("16 km long run") == SessionClass.LONG_RUN
        assert classify_session("Rest") == SessionClass.REST
        assert classify_session("12 km aerobic") == SessionClass.AEROBIC

    def test_week_brief_exists_all_weeks(self):
        for w in range(1, 15):
            brief = get_week_brief(w)
            assert brief, f"Missing brief for week {w}"


class TestScoring:
    def test_score_sleep_precheck_ignores(self):
        assert score_sleep(5.0, Phase.PRECHECK) == (0, None)
        assert score_sleep(None, Phase.PRECHECK) == (0, None)

    def test_score_sleep_final_weights(self):
        assert score_sleep(None, Phase.FINAL) == (0, None)
        assert score_sleep(7.5, Phase.FINAL) == (0, None)
        assert score_sleep(6.5, Phase.FINAL) == (1, "sleep slightly short")
        assert score_sleep(5.0, Phase.FINAL) == (2, "sleep poor")

    def test_score_rhr(self):
        assert score_rhr(None, 50.0) == (0, None)
        assert score_rhr(51, 50.0) == (0, None)
        assert score_rhr(55, 50.0) == (1, "RHR +5 vs baseline")
        assert score_rhr(60, 50.0) == (2, "RHR +10 vs baseline")

    def test_score_body_battery(self):
        assert score_body_battery(None) == (0, None)
        assert score_body_battery(70) == (0, None)
        assert score_body_battery(50) == (1, "body battery modest")
        assert score_body_battery(25) == (2, "body battery low")

    def test_score_subjective(self):
        assert score_subjective(2, False, False) == (0, None)
        assert score_subjective(3, False, False) == (1, "legs heavy")
        assert score_subjective(4, False, False) == (2, "soreness high")
        assert score_subjective(2, True, False) == (2, "pain or illness")
        assert score_subjective(2, False, True) == (2, "pain or illness")

    def test_classify_green(self):
        assert classify(0, False, False) == Status.GREEN
        assert classify(2, False, False) == Status.GREEN

    def test_classify_yellow(self):
        assert classify(3, False, False) == Status.YELLOW
        assert classify(5, False, False) == Status.YELLOW

    def test_classify_red(self):
        assert classify(6, False, False) == Status.RED
        assert classify(0, True, False) == Status.RED
        assert classify(0, False, True) == Status.RED

    def test_recommend_green(self):
        assert recommend(Status.GREEN, "7 km easy") == "7 km easy"

    def test_recommend_yellow_threshold(self):
        assert "easy only" in recommend(Status.YELLOW, "Threshold: 4 x 6 min")

    def test_recommend_yellow_long_run(self):
        assert "Reduce" in recommend(Status.YELLOW, "16 km long run")

    def test_recommend_red(self):
        assert "Rest" in recommend(Status.RED, "7 km easy")


class TestMorningResult:
    def test_evaluate_produces_result(self):
        metrics = MorningMetrics(
            sleep_hours=7.5,
            resting_hr=50,
            body_battery=70,
            training_readiness=75,
            hrv_status="balanced",
        )
        result = evaluate(
            date="2026-03-25",
            phase=Phase.PRECHECK,
            week_number=1,
            planned="5 km easy",
            metrics=metrics,
            rhr_baseline=50.0,
        )
        assert result.status == Status.GREEN
        assert result.phase == Phase.PRECHECK
        assert result.recommended_session == "5 km easy"
        assert result.freshness["sleep_complete"] is True
        assert result.freshness["post_wake_data_used"] is False

    def test_evaluate_final_marks_freshness(self):
        metrics = MorningMetrics(sleep_hours=7.0)
        result = evaluate(
            date="2026-03-25",
            phase=Phase.FINAL,
            week_number=1,
            planned="5 km easy",
            metrics=metrics,
            rhr_baseline=50.0,
        )
        assert result.freshness["post_wake_data_used"] is True

    def test_format_message_contains_key_elements(self):
        metrics = MorningMetrics(sleep_hours=6.5, resting_hr=55, body_battery=40)
        result = evaluate(
            date="2026-03-25",
            phase=Phase.PRECHECK,
            week_number=1,
            planned="5 km easy",
            metrics=metrics,
            rhr_baseline=50.0,
        )
        msg = result.format_message()
        assert "PRECHECK" in msg
        assert "5 km easy" in msg
        assert "Details:" in msg


class TestTriggers:
    def test_wake_triggers(self):
        assert detect_trigger("일어났어").trigger_type == TriggerType.WAKE
        assert detect_trigger("기상").trigger_type == TriggerType.WAKE
        assert detect_trigger("woke up").trigger_type == TriggerType.WAKE

    def test_workout_complete_triggers(self):
        assert detect_trigger("운동 끝").trigger_type == TriggerType.WORKOUT_COMPLETE
        assert detect_trigger("러닝 끝").trigger_type == TriggerType.WORKOUT_COMPLETE
        assert (
            detect_trigger("오늘 운동했어").trigger_type == TriggerType.WORKOUT_COMPLETE
        )

    def test_unrelated_returns_none(self):
        assert detect_trigger("오늘 날씨가 좋다") is None
        assert detect_trigger("뭐 해") is None
        assert detect_trigger("") is None


class TestCalendarSync:
    def test_strip_workout_block(self):
        text = f"Before\n{WORKOUT_BLOCK_START}\nContent\n{WORKOUT_BLOCK_END}\nAfter"
        result = strip_workout_block(text)
        assert "Garmin Coach" not in result
        assert "Before" in result
        assert "After" in result

    def test_strip_no_block(self):
        assert strip_workout_block("No block") == "No block"

    def test_merge_idempotent(self):
        from garmin_coach.models import WorkoutLog

        log = WorkoutLog(date="2026-03-25")
        log.planned = "7 km easy"
        log.final_status = "GREEN"
        log.updated_at = "2026-03-25T10:00:00"

        desc1 = merge_description("Event", log)
        assert "Garmin Coach" in desc1

        desc2 = merge_description(desc1, log)
        assert desc2.count(WORKOUT_BLOCK_START) == 1


class TestGarminWriteback:
    def test_status_defined(self):
        assert GARMIN_WRITEBACK_STATUS["garth_read_only"] is True
        assert "durable_source" in GARMIN_WRITEBACK_STATUS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
