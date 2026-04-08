import asyncio
from datetime import date
from types import SimpleNamespace
from typing import Any, cast

from garmin_coach.models import (
    FitnessLevel,
    GarminAuth,
    InjuryRecord,
    MedicalProfile,
    SessionType,
    TrainingGoal,
    UserProfile,
)
from garmin_coach.ports import CoachingPort


def _prd_user(**nutrition_overrides):
    return UserProfile(
        garmin_credentials=GarminAuth(email="runner@example.com"),
        birth_date=date(1994, 4, 8),
        sex="male",
        height_cm=175,
        weight_kg=70,
        goal=TrainingGoal(type="endurance"),
        fitness_level=FitnessLevel(level="intermediate"),
        medical=nutrition_overrides.pop("medical", None),
        nutrition=cast(
            Any,
            SimpleNamespace(
                allergies=nutrition_overrides.pop("allergies", []),
                dietary_restrictions=nutrition_overrides.pop("dietary_restrictions", []),
                food_restrictions=nutrition_overrides.pop("food_restrictions", []),
                dietary_style=nutrition_overrides.pop("dietary_style", "omnivore"),
                weight_goal=nutrition_overrides.pop("weight_goal", "maintain"),
            ),
        ),
    )


def test_macros_interval_runner_and_bmr_floor():
    from garmin_coach.nutrition.macros import calculate_daily_macros

    macros = calculate_daily_macros(_prd_user(), SessionType.INTERVAL)

    assert macros.carbs_g == (420.0, 560.0)
    assert macros.fat_g[0] >= 70.0
    assert macros.total_kcal[0] >= macros.bmr_kcal


def test_macros_weight_loss_never_goes_below_bmr_or_fat_floor():
    from garmin_coach.nutrition.macros import calculate_daily_macros

    user = _prd_user(weight_goal="lose")
    macros = calculate_daily_macros(user, SessionType.REST)

    assert macros.goal_type == "weight_loss"
    assert macros.total_kcal[0] >= macros.bmr_kcal
    assert macros.fat_g[0] == 70.0


def test_macros_rehab_branch_raises_protein():
    from garmin_coach.nutrition.macros import calculate_daily_macros

    user = _prd_user(
        medical=MedicalProfile(
            current_injuries=[InjuryRecord(body_part="knee", description="rehab")]
        )
    )
    macros = calculate_daily_macros(user, SessionType.EASY)

    assert macros.goal_type == "rehab"
    assert macros.protein_g == (112.0, 140.0)


def test_missing_profile_degrades_safely():
    from garmin_coach.nutrition.engine import NutritionEngine

    guide = asyncio.run(
        NutritionEngine().get_today_guide(
            SimpleNamespace(nutrition={"dietary_style": "vegan"}),
            SessionType.MODERATE,
            duration_min=80,
        )
    )

    assert guide.macros.degraded_safely is True
    assert guide.macros.total_kcal[0] >= guide.macros.bmr_kcal
    assert isinstance(guide.to_dict(), dict)


def test_pre_and_post_examples_filter_allergies_and_restrictions():
    from garmin_coach.nutrition.timing import get_post_workout_advice, get_pre_workout_advice

    user = _prd_user(
        dietary_style="vegan",
        allergies=["nuts"],
        dietary_restrictions=["dairy", "gluten"],
    )

    pre = get_pre_workout_advice(1.5, SessionType.LONG, user)
    post = get_post_workout_advice(SessionType.HARD, user)

    combined = " | ".join(pre.examples + post.examples).lower()
    for banned in ["honey", "yogurt", "milk", "toast", "peanut", "chicken", "우유"]:
        assert banned not in combined
    assert pre.restrictions_applied
    assert post.restrictions_applied


def test_during_advice_for_over_180_minutes_requires_salt():
    from garmin_coach.nutrition.timing import get_during_advice

    advice = get_during_advice(210, SessionType.LONG)

    assert advice.carbs_per_hour_g == (60, 90)
    assert "필수" in advice.description
    assert advice.requires_electrolytes is True


def test_hydration_hot_weather_and_sweat_rate():
    from garmin_coach.nutrition.hydration import calculate_sweat_rate, get_hydration_plan

    plan = get_hydration_plan(SessionType.LONG, duration_min=120, temp_celsius=31)
    sweat_rate = calculate_sweat_rate(70.5, 69.8, 600, 2.0)

    assert plan.hot_weather_adjustment_ml_per_hour == 250
    assert plan.sodium_mg_per_liter == (500, 1000)
    assert sweat_rate == 650.0


def test_recovery_advice_weight_loss_branch_and_filters():
    from garmin_coach.nutrition.recovery_fuel import get_recovery_advice

    user = _prd_user(weight_goal="lose", dietary_style="vegan", dietary_restrictions=["dairy"])
    advice = get_recovery_advice(SimpleNamespace(session_type=SessionType.HARD), user)

    assert advice.priority == "carb_repletion"
    assert "체중 감량" in advice.rationale
    assert "우유" not in " ".join(advice.food_examples)


def test_photo_analysis_low_confidence_requires_confirmation_and_warns_on_conflicts():
    from garmin_coach.nutrition.photo_food import FoodPhotoAnalyzer

    async def fake_client(photo, user):
        return {
            "items_detected": ["peanut butter toast", "banana"],
            "estimated_macros": {"calories": 450, "protein_g": 12, "carbs_g": 55, "fat_g": 18},
            "confidence": "low",
            "coaching_note": "식사로 보입니다.",
        }

    user = _prd_user(allergies=["nuts"], dietary_restrictions=["gluten"])
    analysis = asyncio.run(FoodPhotoAnalyzer(fake_client).analyze(b"img", user))

    assert analysis.requires_confirmation is True
    assert analysis.authoritative is False
    assert analysis.allergen_warning is not None
    assert "확인" in analysis.coaching_note


def test_nutrition_engine_returns_structured_outputs_only():
    from garmin_coach.nutrition.engine import NutritionEngine

    guide = asyncio.run(
        NutritionEngine().get_today_guide(
            _prd_user(), SessionType.LONG, hours_until=3.0, temp_celsius=29
        )
    )

    assert hasattr(guide, "macros")
    assert hasattr(guide, "hydration")
    assert hasattr(guide, "during_workout")
    assert isinstance(guide.to_dict()["hydration"], dict)


def test_meal_logging_is_idempotent_with_stream1_storage(tmp_path):
    from garmin_coach.nutrition.engine import NutritionEngine
    from garmin_coach.storage.database import GarminCoachDatabase

    db = GarminCoachDatabase(tmp_path / "coach.db")
    engine = NutritionEngine(storage=db)
    meal = {
        "type": "photo_analyzed",
        "analysis": {
            "items_detected": ["rice", "tofu"],
            "estimated_macros": {"calories": 500},
            "confidence": "medium",
        },
        "authoritative": True,
        "status": "confirmed",
        "entry_date": "2026-04-08",
    }

    first = asyncio.run(engine.log_meal("u1", meal))
    second = asyncio.run(engine.log_meal("u1", meal))
    rows = db.list_recent_nutrition_logs("u1")

    assert first == second
    assert len(rows) == 1
    assert rows[0]["entry_id"] == first
    db.close()


def test_low_confidence_log_never_becomes_authoritative(tmp_path):
    from garmin_coach.nutrition.engine import NutritionEngine
    from garmin_coach.storage.database import GarminCoachDatabase

    db = GarminCoachDatabase(tmp_path / "coach.db")
    entry_id = asyncio.run(
        NutritionEngine(storage=db).log_meal(
            "u1",
            {
                "type": "photo_analyzed",
                "analysis": {
                    "items_detected": ["salad"],
                    "estimated_macros": {"calories": 250},
                    "confidence": "low",
                },
                "authoritative": True,
                "status": "confirmed",
                "entry_date": "2026-04-08",
            },
        )
    )

    saved = db.load_nutrition_log("u1", cast(str, entry_id))
    assert saved is not None
    assert saved["authoritative"] is False
    db.close()


class _FakePort:
    def __init__(self, selects, photo=b"photo", text_response="밥 + 두부"):
        self.selects = list(selects)
        self.photo = photo
        self.text_response = text_response
        self.messages = []
        self.prompts = []

    async def send_message(self, user_id, text, buttons=None):
        self.messages.append(text)

    async def send_image(self, user_id, image, caption=None):
        raise NotImplementedError

    async def send_report(self, user_id, report):
        raise NotImplementedError

    async def request_text(self, user_id, prompt):
        self.prompts.append(prompt)
        return self.text_response

    async def request_number(self, user_id, prompt, min_val=None, max_val=None):
        raise NotImplementedError

    async def request_date(self, user_id, prompt):
        raise NotImplementedError

    async def request_select(self, user_id, prompt, options):
        self.prompts.append(prompt)
        return self.selects.pop(0)

    async def request_multi_select(self, user_id, prompt, options):
        raise NotImplementedError

    async def request_photo(self, user_id, prompt):
        return self.photo


class _FakeStorage:
    def __init__(self):
        self.saved = {}

    async def save_meal(self, user_id, meal):
        self.saved[(user_id, meal["entry_id"])] = meal


class _FakePhotoAnalyzer:
    def __init__(self, result):
        self.result = result

    async def analyze(self, user_id, photo):
        return self.result


def test_flow_low_confidence_requires_confirmation_and_saves_non_authoritative():
    from garmin_coach.flows.nutrition_log import NutritionLogFlow

    port = _FakePort(selects=["photo", "confirm"])
    storage = _FakeStorage()
    analyzer = _FakePhotoAnalyzer(
        {
            "items_detected": ["salad"],
            "estimated_macros": {"calories": 220, "protein_g": 12, "carbs_g": 18, "fat_g": 9},
            "confidence": "low",
            "coaching_note": "추정치입니다.",
        }
    )

    asyncio.run(
        NutritionLogFlow(
            cast(CoachingPort, port), photo_analyzer=analyzer, storage=storage
        ).execute("u1")
    )

    assert len(storage.saved) == 1
    saved_meal = next(iter(storage.saved.values()))
    assert saved_meal["authoritative"] is False
    assert saved_meal["requires_confirmation"] is True
    assert any("신뢰도가 낮아" in prompt for prompt in port.prompts)


def test_flow_photo_cancel_does_not_save():
    from garmin_coach.flows.nutrition_log import NutritionLogFlow

    port = _FakePort(selects=["photo", "cancel"])
    storage = _FakeStorage()
    analyzer = _FakePhotoAnalyzer(
        {
            "items_detected": ["rice"],
            "estimated_macros": {"calories": 300},
            "confidence": "low",
        }
    )

    asyncio.run(
        NutritionLogFlow(
            cast(CoachingPort, port), photo_analyzer=analyzer, storage=storage
        ).execute("u1")
    )

    assert storage.saved == {}


def test_flow_text_logging_uses_stable_entry_id():
    from garmin_coach.flows.nutrition_log import NutritionLogFlow

    flow = NutritionLogFlow(cast(CoachingPort, _FakePort(selects=[])))
    first = asyncio.run(flow._log_by_text("u1"))
    second = asyncio.run(flow._log_by_text("u1"))

    assert first["entry_id"] == second["entry_id"]
