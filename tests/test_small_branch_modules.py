import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


def test_update_check_branches(monkeypatch, tmp_path):
    import garmin_coach.update_check as update_check

    cache = tmp_path / ".cache"
    monkeypatch.setattr(update_check, "CACHE_FILE", str(cache))
    monkeypatch.setattr(update_check.os.path, "exists", lambda path: True)
    monkeypatch.setattr(update_check.os.path, "getmtime", lambda path: 0)
    monkeypatch.setattr(
        update_check,
        "datetime",
        type(
            "FakeDateTime",
            (),
            {
                "now": staticmethod(lambda: datetime.fromtimestamp(1)),
                "fromtimestamp": staticmethod(datetime.fromtimestamp),
            },
        ),
    )
    cache.write_text(json.dumps({"tag_name": "v9.9.9", "html_url": "u", "body": "b"}))
    assert update_check._read_cache() is not None

    monkeypatch.setattr(update_check.os.path, "exists", lambda path: True)
    monkeypatch.setattr(
        update_check.os.path, "getmtime", lambda path: (_ for _ in ()).throw(RuntimeError("bad"))
    )
    assert update_check._read_cache() is None

    monkeypatch.setattr(
        update_check.os,
        "makedirs",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no")),
    )
    update_check._write_cache({"x": 1})

    monkeypatch.setattr(
        update_check,
        "requests",
        SimpleNamespace(
            get=lambda *args, **kwargs: SimpleNamespace(status_code=500, json=lambda: {})
        ),
    )
    info = update_check.check_for_updates(force=True)
    assert info.is_update_available is False
    assert update_check._compare_versions("2.0.0", "1.0.0") == 1
    assert update_check._compare_versions("bad", "1.0.0") == 0
    assert "Update available" in update_check.get_update_message(
        update_check.UpdateInfo(current="1.0.0", latest="2.0.0", url="u", is_update_available=True)
    )


def test_training_log_and_workout_review_branches(monkeypatch, tmp_path, capsys):
    import garmin_coach.training_log as training_log
    import garmin_coach.workout_review as workout_review

    base = tmp_path / "data"
    snapshot = base / "snapshots"
    evening = base / "evening_reviews"
    md = base / "training_logs"
    js = base / "training_log_json"
    for p in [snapshot, evening, md, js]:
        p.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(training_log, "SNAPSHOT_DIR", snapshot)
    monkeypatch.setattr(training_log, "EVENING_DIR", evening)
    monkeypatch.setattr(training_log, "TRAINING_MD_DIR", md)
    monkeypatch.setattr(training_log, "TRAINING_JSON_DIR", js)
    training_log.ensure_dirs()
    assert training_log.load_json(Path("/does/not/exist")) is None
    bad_json = snapshot / "bad.json"
    bad_json.write_text("bad")
    assert training_log.load_json(bad_json) is None

    log = SimpleNamespace(
        date="2026-03-29",
        planned=None,
        final_status=None,
        completed=None,
        activity=None,
        subjective=None,
        coach_note="",
        tomorrow_note="",
        source="manual",
        updated_at="now",
    )
    assert "Planned: n/a" in training_log.build_md(log)
    monkeypatch.setattr("sys.argv", ["training_log", "--date", "2026-03-29", "--source", "strava"])
    assert training_log.parse_args().source == "strava"

    monkeypatch.setattr(workout_review, "SNAPSHOT_DIR", snapshot)
    monkeypatch.setattr(workout_review, "TRAINING_MD_DIR", md)
    monkeypatch.setattr(workout_review, "TRAINING_JSON_DIR", js)
    workout_review.ensure_dirs()
    assert workout_review.load_json(Path("/no/file")) is None
    bad_wr = snapshot / "bad_wr.json"
    bad_wr.write_text("bad")
    assert workout_review.load_json(bad_wr) is None
    assert workout_review.find_today_activity([], "2026-03-29") is None
    assert workout_review.classify_activity_type({"type": "Pool Swim"}) == "swimming"
    assert workout_review.classify_activity_type({"type": "Bike Ride"}) == "cycling"
    assert workout_review.classify_activity_type({}) == "unknown"
    assert "manually" in workout_review.build_coach_note({}, "easy", None)
    assert "Pace feel OK" in workout_review.build_coach_note({}, "threshold session", 5.0)
    assert "Fuel/hydration" in workout_review.build_coach_note({}, "long run", 20.0)
    assert "% vs plan" in workout_review.build_coach_note({}, "10 km easy", 8.0)
    monkeypatch.setattr("sys.argv", ["workout_review", "--date", "2026-03-29", "--no-calendar"])
    assert workout_review.parse_args().no_calendar is True

    monkeypatch.setattr(workout_review, "resume_garth", lambda: False)
    monkeypatch.setattr(workout_review, "load_json", lambda path: None)
    monkeypatch.setattr(
        workout_review, "find_and_update_workout_event", lambda target_date, log: None
    )
    monkeypatch.setattr(
        workout_review,
        "parse_args",
        lambda: SimpleNamespace(
            date="2026-03-29",
            no_calendar=True,
            distance_km=None,
            duration_min=None,
            avg_pace="",
            avg_hr=None,
            energy=3,
            legs=2,
            mood=3,
            pain=False,
            illness=False,
            notes="",
            tomorrow_note="",
        ),
    )
    workout_review.main()
    assert "No recent activity found." in capsys.readouterr().out


def test_plan_and_coach_engine_branches():
    from garmin_coach.coach_engine import (
        classify,
        evaluate,
        get_downgrade_rule,
        get_execution_guidance,
        get_pace_hr_guide,
        recommend,
        score_body_battery,
        score_hrv_or_readiness,
    )
    from garmin_coach.models import MorningMetrics, Phase, SessionClass, Status
    from garmin_coach.plan import (
        classify_session,
        get_planned_session,
        get_session_purpose,
        get_week_brief,
        get_week_number,
    )

    assert get_week_number("2025-01-01") == 1
    assert get_planned_session("2026-04-30")[1]
    assert get_week_brief(99) == "Stay consistent."
    assert classify_session("MP run") == SessionClass.MP
    assert classify_session("recovery jog") == SessionClass.RECOVERY
    assert classify_session("walk") == SessionClass.REST
    assert classify_session("strength session") == SessionClass.STRENGTH_SUPPORTED
    assert classify_session("mystery") == SessionClass.UNKNOWN
    assert "lactate threshold" in get_session_purpose("threshold repeats")
    assert "marathon pace" in get_session_purpose("mp workout").lower()
    assert "endurance" in get_session_purpose("long run").lower()
    assert "aerobic base" in get_session_purpose("medium-long aerobic").lower()
    assert "Recovery run" in get_session_purpose("easy run")
    assert "Rest day" in get_session_purpose("rest")
    assert "Stay consistent" in get_session_purpose("mystery")

    assert score_hrv_or_readiness(None, 30) == (2, "readiness low")
    assert score_hrv_or_readiness("balanced", None) == (0, None)
    assert score_hrv_or_readiness("fair", None) == (1, "HRV a bit low")
    assert score_hrv_or_readiness("terrible", None) == (2, "HRV suppressed")
    assert score_body_battery(40) == (1, "body battery modest")
    assert classify(6, False, False) == Status.RED
    assert recommend(Status.YELLOW, "easy run") == "Shorten easy run 15-30%, skip extras"
    assert get_execution_guidance("threshold", "planned", Status.GREEN)[0].startswith("Warm up")
    assert get_execution_guidance("easy run", "45-50 min easy only", Status.YELLOW)[0].startswith(
        "Today is quality"
    )
    assert get_execution_guidance("long run", "plan", Status.GREEN)[0].startswith("First 20-30")
    assert get_execution_guidance("easy run", "plan", Status.GREEN)[0].startswith(
        "Keep it conversational"
    )
    assert get_execution_guidance("anything", "Rest or 20-30 min very easy only", Status.RED)[
        0
    ].startswith("No hard effort")
    assert get_execution_guidance("anything", "plan", Status.GREEN)[0].startswith("Stay controlled")
    assert "Zone 2" in get_pace_hr_guide("easy run", "plan", Status.GREEN)
    assert "Zone 4" in get_pace_hr_guide("threshold run", "plan", Status.GREEN)
    assert "Marathon pace" in get_pace_hr_guide("mp run", "plan", Status.GREEN)
    assert "Zone 2 early" in get_pace_hr_guide("long run", "plan", Status.GREEN)
    assert "Rest day" in get_pace_hr_guide("run", "rest", Status.RED)
    assert "Controlled effort" in get_pace_hr_guide("mystery", "plan", Status.GREEN)
    assert "Downgrade" in get_downgrade_rule(Status.GREEN, "threshold run")
    assert "cut 15-25%" in get_downgrade_rule(Status.GREEN, "easy run")
    assert "drop to easy" in get_downgrade_rule(Status.YELLOW, "anything")
    assert "stop and rest" in get_downgrade_rule(Status.RED, "anything")

    result = evaluate(
        date="2026-03-29",
        phase=Phase.FINAL,
        week_number=5,
        planned="threshold workout",
        metrics=MorningMetrics(
            sleep_hours=5.5,
            resting_hr=60,
            body_battery=20,
            training_readiness=20,
            hrv_status="suppressed",
        ),
        rhr_baseline=50,
        soreness=4,
        pain=False,
        illness=False,
    )
    assert result.status == Status.RED
    assert result.session_class == SessionClass.THRESHOLD
