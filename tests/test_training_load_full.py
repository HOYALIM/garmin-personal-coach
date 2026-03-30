import json
from datetime import date, timedelta


def test_training_load_branches_and_persistence(tmp_path, monkeypatch):
    from garmin_coach.training_load import (
        DailyLoad,
        FormCategory,
        LoadSnapshot,
        PeriodizationPhase,
        RecoveryRecommendation,
        SessionIntensity,
        SessionLoadCalculator,
        Sport,
        TrainingLoadCalculator,
        WeeklyStats,
        _pace_to_sec_per_km,
    )

    assert Sport.RUNNING.value == "running"
    assert PeriodizationPhase.BASE.value == "base"
    assert (
        DailyLoad(
            date=date(2026, 3, 1),
            trimp=50,
            sport=Sport.RUNNING,
            duration_min=30,
            description="easy",
        ).to_dict()["description"]
        == "easy"
    )
    assert (
        LoadSnapshot(
            ctl=10, atl=5, tsb=5, form=FormCategory.PREPARED, date=date(2026, 3, 1)
        ).to_dict()["form"]
        == "prepared"
    )
    assert WeeklyStats(
        week_start=date(2026, 3, 3),
        total_trimp=10,
        total_hours=1,
        session_count=1,
        sport_breakdown={"running": 10},
        ctl_change=1,
        form_trend=[FormCategory.PREPARED],
    ).to_dict()["form_trend"] == ["prepared"]
    assert RecoveryRecommendation(False, "ok", 0.0, "as_planned", 0).rest_days == 0

    female = SessionLoadCalculator(sex="female")
    assert female.metabolic_factor == 1.3
    assert female.estimate_running_intensity(2, "8:00/km", "6:00/km") == 0.65
    assert female.estimate_running_intensity(3, "6:42/km", "6:00/km") == 0.7
    assert female.estimate_running_intensity(3, "6:05/km", "6:00/km") == 0.8
    assert female.estimate_running_intensity(3, "5:30/km", "6:00/km") == 0.9
    assert female.estimate_running_intensity(3, "4:50/km", "6:00/km") == 1.0
    assert female.estimate_running_intensity(3, "4:00/km", "6:00/km") == 1.1
    assert female.estimate_running_intensity(5, None, None) == 0.8
    assert female.estimate_running_intensity(10, None, None) == 0.75
    assert female.estimate_running_intensity(20, None, None) == 0.7
    assert female.estimate_running_intensity(30, None, None) == 0.65
    assert female.estimate_running_intensity(None, None, None) == 0.75

    assert female.estimate_cycling_intensity(100, 200) == 0.6
    assert female.estimate_cycling_intensity(140, 200) == 0.7
    assert female.estimate_cycling_intensity(170, 200) == 0.85
    assert female.estimate_cycling_intensity(200, 200) == 1.0
    assert female.estimate_cycling_intensity(230, 200) == 1.2
    assert female.estimate_cycling_intensity(400, 200) == 1.5
    assert female.estimate_cycling_intensity(None, None) == 0.8

    assert female.calculate_trimp(Sport.RUNNING, 60, avg_hr=150, max_hr=190, rest_hr=50) == 55.7
    assert female.calculate_trimp(Sport.RUNNING, 60, avg_hr=50, max_hr=50, rest_hr=50) == 58.5
    assert (
        female.calculate_trimp(Sport.RUNNING, 60, session_intensity=SessionIntensity.RECOVERY)
        == 50.7
    )
    assert (
        female.calculate_trimp(Sport.CYCLING, 60, session_intensity=SessionIntensity.INTERVAL)
        == 93.6
    )
    assert (
        female.calculate_trimp(Sport.SWIMMING, 60, session_intensity=SessionIntensity.RACE) == 81.9
    )
    assert female.calculate_trimp(Sport.TRIATHLON, 60) == 66.3
    assert female.calculate_trimp(Sport.OTHER, 60) == 54.6
    assert female.trimp_to_load_category(20) == "very_light"
    assert female.trimp_to_load_category(70) == "light"
    assert female.trimp_to_load_category(150) == "moderate"
    assert female.trimp_to_load_category(250) == "hard"
    assert female.trimp_to_load_category(350) == "very_hard"

    calc = TrainingLoadCalculator(sex="male")
    today = date(2026, 3, 29)
    monkeypatch.setattr(
        "garmin_coach.training_load.date",
        type(
            "FakeDate",
            (),
            {"today": staticmethod(lambda: today), "fromisoformat": date.fromisoformat},
        ),
    )

    assert calc.remove_session(today) is False
    assert calc.get_session(today) is None
    calc.add_session(today.isoformat(), 100.0, "running", 60, "hard run")
    assert calc.get_session(today).description == "hard run"
    assert calc.remove_session(today.isoformat()) is True

    for i, trimp in enumerate([50, 60, 70, 80, 90, 100, 110, 120, 130, 140]):
        calc.add_session(today - timedelta(days=i), float(trimp), Sport.RUNNING, 60, f"day-{i}")

    range_sessions = calc.get_sessions_in_range(
        (today - timedelta(days=2)).isoformat(), today.isoformat()
    )
    assert [s.description for s in range_sessions] == ["day-2", "day-1", "day-0"]
    assert calc.calculate_ctl(today.isoformat()) > 0
    assert calc.calculate_atl(today.isoformat()) > 0
    assert isinstance(calc.calculate_tsb(today.isoformat()), float)

    snap = calc.get_snapshot(today.isoformat())
    assert snap.date == today
    assert calc.get_form_category(today) in set(FormCategory)
    assert calc.get_form_description(today)

    stats = calc.get_weekly_stats((today - timedelta(days=today.weekday())).isoformat())
    assert stats.session_count > 0
    assert stats.total_hours > 0
    assert stats.sport_breakdown["running"] > 0

    trend = calc.get_load_trend(weeks=2)
    assert len(trend) == 2
    assert trend[0]["week_start"] <= trend[1]["week_start"]

    excessive = TrainingLoadCalculator()
    excessive.get_snapshot = lambda as_of=None: LoadSnapshot(
        ctl=20, atl=40, tsb=-20, form=FormCategory.EXCESSIVE, date=today
    )
    assert excessive.get_recovery_recommendation().deload_needed is True

    tired = TrainingLoadCalculator()
    tired.get_snapshot = lambda as_of=None: LoadSnapshot(
        ctl=30, atl=35, tsb=-15, form=FormCategory.TIRED, date=today
    )
    assert tired.get_recovery_recommendation().next_intensity == "easy"

    fresh_risk = TrainingLoadCalculator()
    fresh_risk.get_snapshot = lambda as_of=None: LoadSnapshot(
        ctl=10, atl=1, tsb=30, form=FormCategory.FRESHNESS_RISK, date=today
    )
    assert fresh_risk.get_recovery_recommendation().suggested_trimp_reduction == -0.2

    prepared = TrainingLoadCalculator()
    prepared.get_snapshot = lambda as_of=None: LoadSnapshot(
        ctl=30, atl=20, tsb=5, form=FormCategory.PREPARED, date=today
    )
    assert prepared.get_recovery_recommendation().next_intensity == "as_planned"

    deload_calc = TrainingLoadCalculator()
    assert deload_calc.should_deload(current_week=4, weeks_since_last_deload=3)[0] is True
    deload_calc.get_snapshot = lambda: LoadSnapshot(
        ctl=20, atl=30, tsb=-10, form=FormCategory.TIRED, date=today
    )
    assert "ATL" in deload_calc.should_deload(current_week=1, weeks_since_last_deload=0)[1]
    deload_calc.get_snapshot = lambda: LoadSnapshot(
        ctl=20, atl=15, tsb=-31, form=FormCategory.EXCESSIVE, date=today
    )
    assert (
        "TSB very negative"
        in deload_calc.should_deload(current_week=1, weeks_since_last_deload=0)[1]
    )
    deload_calc.get_snapshot = lambda: LoadSnapshot(
        ctl=20, atl=15, tsb=-15, form=FormCategory.TIRED, date=today
    )
    assert (
        "Accumulated fatigue"
        in deload_calc.should_deload(current_week=2, weeks_since_last_deload=0)[1]
    )
    deload_calc.get_snapshot = lambda: LoadSnapshot(
        ctl=20, atl=15, tsb=0, form=FormCategory.PREPARED, date=today
    )
    assert deload_calc.should_deload(current_week=1, weeks_since_last_deload=0) == (
        False,
        "No deload needed",
    )

    json_path = tmp_path / "loads" / "training.json"
    exported = calc.export_json(json_path)
    assert json.loads(exported)["loads"]
    assert json_path.exists()
    restored = TrainingLoadCalculator.from_json(json_path)
    assert restored.get_session(today).description == "day-0"
    restored2 = TrainingLoadCalculator.from_json(exported)
    assert restored2.get_session(today).trimp == 50.0

    series = calc.export_time_series(days=3)
    assert len(series) == 3
    assert series[0]["date"] < series[-1]["date"]

    assert _pace_to_sec_per_km("5:30/km") == 330
    assert _pace_to_sec_per_km("330") == 330
    assert _pace_to_sec_per_km("bad") is None
    assert _pace_to_sec_per_km("") is None
