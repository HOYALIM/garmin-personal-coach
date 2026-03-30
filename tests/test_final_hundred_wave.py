import runpy
from datetime import date, timedelta

import pytest


def test_final_hundred_wave(monkeypatch, tmp_path):
    import garmin_coach.nutrition.hydration as hydration
    import garmin_coach.periodization as periodization
    import garmin_coach.profile_manager as profile_manager
    import garmin_coach.setup_wizard as setup_wizard
    import garmin_coach.training_load as training_load
    import garmin_coach.wizard as wizard

    monkeypatch.setattr(hydration, "get_today_intake", lambda: 2500)
    assert hydration.check_hydration_status(2000) == "goal_reached"

    profile = profile_manager.UserProfile(
        profile=profile_manager.ProfileData(
            name="Pat",
            sports=[profile_manager.Sport.RUNNING],
            primary_sport=profile_manager.Sport.RUNNING,
        )
    )
    engine = periodization.PeriodizationEngine(profile=profile, plan_start=date(2026, 1, 1))
    assert (
        periodization.WeekPlan(
            week_number=1,
            phase=periodization.Phase.BASE,
            week_start=date(2026, 1, 1),
            sessions=[],
            total_volume_hours=0,
        ).to_dict()["phase"]
        == "base"
    )
    assert engine._build_phase_sequence(11)[-1].name == periodization.Phase.PEAK
    assert engine._build_phase_sequence(12)[-1].name == periodization.Phase.PEAK
    assert (
        engine._generate_sessions(1, type("X", (), {"name": "other"})(), False, date(2026, 1, 1))
        == []
    )
    profile.profile.sports = [profile_manager.Sport.TRIATHLON, profile_manager.Sport.CYCLING]
    tri = periodization.PeriodizationEngine(profile=profile, plan_start=date(2026, 1, 1))
    assert any(
        s["sport"] == "cycling"
        for s in tri._base_sessions(date(2026, 1, 1), ["triathlon", "cycling"], 5, True)
    )
    tri._weeks = [
        periodization.WeekPlan(
            week_number=2,
            phase=periodization.Phase.BUILD,
            week_start=date(2026, 1, 8),
            sessions=[],
            total_volume_hours=0,
        )
    ]
    assert tri.get_week(2).phase == periodization.Phase.BUILD

    class FakeDate:
        @staticmethod
        def today():
            return date(2026, 1, 9)

    monkeypatch.setattr(periodization, "date", FakeDate)
    assert tri.get_current_phase() == periodization.Phase.BUILD
    assert tri.get_current_phase(date(2026, 1, 1)) == periodization.Phase.BASE

    empty_cfg = tmp_path / "empty.yaml"
    pm = profile_manager.ProfileManager(empty_cfg)
    assert pm.load() is None
    empty_cfg.write_text("")
    assert pm.load() is None
    bad = profile_manager.UserProfile(
        profile=profile_manager.ProfileData(name="Pat", height_cm=50, weight_kg=20, sports=[])
    )
    errors = pm.validate(bad)
    assert any("height_cm" in e for e in errors)
    assert any("weight_kg" in e for e in errors)
    assert any("sports" in e for e in errors)
    no_races = profile_manager.UserProfile(profile=profile_manager.ProfileData(name="Pat"))
    assert pm.calculate_running_pace_zones(no_races) is None
    assert pm.calculate_cycling_power_zones(no_races) is None
    no_races.fitness.swim_100m_pace = "unknown"
    assert pm.calculate_swim_zones(no_races) is None
    no_races.fitness.swim_100m_pace = "bad"
    assert pm.calculate_swim_zones(no_races) is None
    assert profile_manager._parse_duration("") is None
    assert profile_manager._parse_duration("1:2:3:4") is None

    calc = training_load.SessionLoadCalculator()

    class WeirdNum:
        def __bool__(self):
            return True

        def __gt__(self, other):
            return True

        def __sub__(self, other):
            return 0

    assert (
        calc.calculate_trimp(
            training_load.Sport.RUNNING, 60, avg_hr=WeirdNum(), max_hr=WeirdNum(), rest_hr=1
        )
        > 0
    )
    assert calc.calculate_trimp(training_load.Sport.SWIMMING, 60) > 0
    tl = training_load.TrainingLoadCalculator()
    tl.add_session("2026-01-01", 50, "running", 30)
    assert tl.get_session("2026-01-01") is not None
    for i in range(200):
        tl.add_session(date(2026, 1, 1) - timedelta(days=i), 10, training_load.Sport.RUNNING, 30)
    assert tl.calculate_ctl(date(2026, 1, 1)) >= 0
    assert tl.get_snapshot().date
    assert training_load._pace_to_sec_per_km("1:2:3") is None

    monkeypatch.setattr(
        "builtins.input", lambda *args, **kwargs: (_ for _ in ()).throw(SystemExit(0))
    )
    with pytest.raises(SystemExit):
        runpy.run_module("garmin_coach.wizard", run_name="__main__")

    monkeypatch.setattr(
        "builtins.input", lambda *args, **kwargs: (_ for _ in ()).throw(SystemExit(0))
    )
    with pytest.raises(SystemExit):
        runpy.run_module("garmin_coach.setup_wizard", run_name="__main__")
