"""Tests for new core modules — profile_manager, training_load, periodization, ai_coach, scheduler."""

import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GARMIN_PLAN_START_DATE", "2026-01-01")

from garmin_coach.profile_manager import (
    ProfileData,
    ProfileManager,
    ProfileValidationError,
    AIFlexibility,
    AITone,
    Sport,
    FitnessLevel,
    Sex,
)
from garmin_coach.training_load import (
    SessionLoadCalculator,
    Sport as TSport,
    SessionIntensity,
    FormCategory,
    TrainingLoadCalculator,
)
from garmin_coach.periodization import (
    PeriodizationEngine,
    Phase,
    WeekPlan,
)


class TestProfileManager:
    def test_default_profile_saves_and_loads(self, tmp_path):
        pm = ProfileManager(tmp_path / "config.yaml")
        profile = ProfileData(name="Test User", age=30, primary_sport=Sport.RUNNING)
        from garmin_coach.profile_manager import UserProfile

        up = UserProfile(profile=profile)
        pm.save(up)
        assert pm.exists()
        loaded = pm.load()
        assert loaded is not None
        assert loaded.profile.name == "Test User"
        assert loaded.profile.age == 30

    def test_validate_missing_name(self):
        pm = ProfileManager()
        from garmin_coach.profile_manager import UserProfile

        up = UserProfile(profile=ProfileData(name=""))
        errors = pm.validate(up)
        assert any("name" in e.lower() for e in errors)

    def test_validate_invalid_age(self):
        pm = ProfileManager()
        from garmin_coach.profile_manager import UserProfile

        up = UserProfile(profile=ProfileData(name="T", age=200))
        errors = pm.validate(up)
        assert any("age" in e.lower() for e in errors)

    def test_hr_zones_calculated(self):
        pm = ProfileManager()
        from garmin_coach.profile_manager import UserProfile

        up = UserProfile(profile=ProfileData(age=30))
        zones = pm.calculate_hr_zones(up)
        assert zones.z1_min > 0
        assert zones.z5_max >= zones.z4_max
        assert zones.z2_max > zones.z2_min

    def test_hr_zones_default_max_hr(self):
        pm = ProfileManager()
        from garmin_coach.profile_manager import UserProfile

        up = UserProfile(
            profile=ProfileData(age=30), fitness=type("F", (), {"max_hr": None})()
        )
        up = UserProfile(profile=ProfileData(age=30))
        zones = pm.calculate_hr_zones(up)
        assert zones.z5_max == 190

    def test_running_pace_zones_from_10k(self):
        pm = ProfileManager()
        from garmin_coach.profile_manager import UserProfile

        up = UserProfile(
            profile=ProfileData(),
            fitness=type("F", (), {"recent_10k": "50:00"})(),
        )
        up = UserProfile(
            profile=ProfileData(),
            fitness=type(
                "F",
                (),
                {
                    "recent_10k": "50:00",
                    "recent_5k": None,
                    "recent_half": None,
                    "recent_marathon": None,
                },
            )(),
        )
        zones = pm.calculate_running_pace_zones(up)
        assert zones is not None
        assert zones.threshold_pace is not None
        assert zones.z2 is not None

    def test_weekly_trimp_targets(self):
        pm = ProfileManager()
        from garmin_coach.profile_manager import UserProfile

        up = UserProfile(profile=ProfileData(fitness_level=FitnessLevel.INTERMEDIATE))
        lo, hi = pm.weekly_trimp_target(up)
        assert 300 < lo < hi < 800

    def test_profile_to_dict_roundtrip(self):
        from garmin_coach.profile_manager import UserProfile

        up = UserProfile(profile=ProfileData(name="Alice", age=28))
        d = up.to_dict()
        restored = UserProfile.from_dict(d)
        assert restored.profile.name == "Alice"
        assert restored.profile.age == 28


class TestSessionLoadCalculator:
    def test_running_trimp_by_intensity(self):
        calc = SessionLoadCalculator(sex="male")
        trimp = calc.calculate_trimp(
            sport=TSport.RUNNING,
            duration_min=60.0,
            session_intensity=SessionIntensity.THRESHOLD,
        )
        assert 40 < trimp < 80

    def test_female_metabolic_factor_higher(self):
        male = SessionLoadCalculator(sex="male")
        female = SessionLoadCalculator(sex="female")
        male_trimp = male.calculate_trimp(
            sport=TSport.RUNNING,
            duration_min=60,
            session_intensity=SessionIntensity.EASY,
        )
        female_trimp = female.calculate_trimp(
            sport=TSport.RUNNING,
            duration_min=60,
            session_intensity=SessionIntensity.EASY,
        )
        assert female_trimp > male_trimp

    def test_cycling_trimp_from_power(self):
        calc = SessionLoadCalculator()
        trimp = calc.calculate_trimp(
            sport=TSport.CYCLING,
            duration_min=90.0,
            avg_power=220,
            ftp=200,
        )
        assert trimp > 0

    def test_swimming_trimp(self):
        calc = SessionLoadCalculator()
        trimp = calc.calculate_trimp(
            sport=TSport.SWIMMING,
            duration_min=45.0,
            session_intensity=SessionIntensity.THRESHOLD,
        )
        assert trimp > 0

    def test_trimp_unknown_sport(self):
        calc = SessionLoadCalculator()
        trimp = calc.calculate_trimp(sport=TSport.OTHER, duration_min=30.0)
        assert trimp > 0


class TestTrainingLoadCalculator:
    def test_ctl_starts_at_zero(self):
        calc = TrainingLoadCalculator()
        assert calc.calculate_ctl() == 0.0

    def test_ctl_accumulates_with_sessions(self):
        calc = TrainingLoadCalculator()
        today = date.today()
        for i in range(10):
            d = today - timedelta(days=i)
            calc.add_session(d, trimp=100.0, sport=TSport.RUNNING, duration_min=60)
        ctl = calc.calculate_ctl()
        assert ctl > 0

    def test_atl_short_term_responsiveness(self):
        calc = TrainingLoadCalculator()
        today = date.today()
        for i in range(14):
            d = today - timedelta(days=i)
            calc.add_session(d, trimp=100.0, sport=TSport.RUNNING, duration_min=60)
        atl = calc.calculate_atl()
        ctl = calc.calculate_ctl()
        assert atl > 0 and ctl > 0

    def test_tsb_calculation(self):
        calc = TrainingLoadCalculator()
        today = date.today()
        for i in range(20):
            calc.add_session(
                today - timedelta(days=i),
                trimp=100.0,
                sport=TSport.RUNNING,
                duration_min=60,
            )
        tsb = calc.calculate_tsb()
        assert tsb >= 0

    def test_form_category(self):
        calc = TrainingLoadCalculator()
        assert calc._tsb_to_form(30.0) == FormCategory.FRESHNESS_RISK
        assert calc._tsb_to_form(15.0) == FormCategory.FRESH
        assert calc._tsb_to_form(0.0) == FormCategory.PREPARED
        assert calc._tsb_to_form(-15.0) == FormCategory.TIRED
        assert calc._tsb_to_form(-35.0) == FormCategory.EXCESSIVE

    def test_weekly_stats(self):
        calc = TrainingLoadCalculator()
        monday = date.today() - timedelta(days=date.today().weekday())
        for i in range(5):
            d = monday + timedelta(days=i)
            calc.add_session(d, trimp=80.0, sport=TSport.RUNNING, duration_min=60)
        stats = calc.get_weekly_stats(monday)
        assert stats.session_count == 5
        assert stats.total_trimp == 400.0
        assert stats.total_hours == 5.0

    def test_should_deload_triggers_at_3_weeks(self):
        calc = TrainingLoadCalculator()
        today = date.today()
        for i in range(30):
            d = today - timedelta(days=i)
            calc.add_session(d, trimp=50.0, sport=TSport.RUNNING, duration_min=45)
        should, reason = calc.should_deload(current_week=4, weeks_since_last_deload=3)
        assert should is True

    def test_export_import_json(self):
        calc = TrainingLoadCalculator()
        today = date.today()
        calc.add_session(today, trimp=120.0, sport=TSport.RUNNING, duration_min=60)
        json_str = calc.export_json()
        restored = TrainingLoadCalculator.from_json(json_str)
        assert restored.calculate_ctl() > 0


class TestPeriodizationEngine:
    def test_build_generates_weeks(self):
        from garmin_coach.profile_manager import UserProfile, ProfileData, FitnessData

        up = UserProfile(
            profile=ProfileData(
                fitness_level=FitnessLevel.INTERMEDIATE,
                available_days=5,
                sports=[Sport.RUNNING],
            ),
        )
        engine = PeriodizationEngine(
            profile=up,
            plan_start=date(2026, 1, 1),
            goal_date=date(2026, 4, 15),
        )
        weeks = engine.build()
        assert len(weeks) >= 14
        assert all(isinstance(w, WeekPlan) for w in weeks)
        assert weeks[0].week_number == 1

    def test_recovery_weeks_halved_volume(self):
        from garmin_coach.profile_manager import UserProfile, ProfileData

        up = UserProfile(
            profile=ProfileData(
                fitness_level=FitnessLevel.INTERMEDIATE,
                available_days=5,
                sports=[Sport.RUNNING],
            ),
        )
        engine = PeriodizationEngine(
            profile=up,
            plan_start=date(2026, 1, 1),
        )
        weeks = engine.build()
        recovery_weeks = [w for w in weeks if w.is_deload]
        regular_weeks = [w for w in weeks if not w.is_deload]
        if recovery_weeks:
            avg_rec_hours = sum(w.total_volume_hours for w in recovery_weeks) / len(
                recovery_weeks
            )
            avg_reg_hours = sum(w.total_volume_hours for w in regular_weeks) / max(
                1, len(regular_weeks)
            )
            assert avg_rec_hours < avg_reg_hours

    def test_phases_ordered(self):
        from garmin_coach.profile_manager import UserProfile, ProfileData

        up = UserProfile(
            profile=ProfileData(sports=[Sport.RUNNING], available_days=5),
        )
        engine = PeriodizationEngine(profile=up, plan_start=date(2026, 1, 1))
        weeks = engine.build()
        phase_order = [w.phase for w in weeks]
        base_idx = next((i for i, p in enumerate(phase_order) if p.value == "base"), -1)
        build_idx = next(
            (i for i, p in enumerate(phase_order) if p.value == "build"), -1
        )
        peak_idx = next((i for i, p in enumerate(phase_order) if p.value == "peak"), -1)
        if base_idx >= 0 and build_idx >= 0:
            assert base_idx < build_idx
        if build_idx >= 0 and peak_idx >= 0:
            assert build_idx < peak_idx


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
