"""Tests for nutrition preferences profile fields and personalized coaching."""

from types import SimpleNamespace

import pytest

from garmin_coach.profile_manager import (
    NutritionPreferences,
    UserProfile,
)


# ── NutritionPreferences dataclass ────────────────────────────────────────────


def test_nutrition_preferences_defaults():
    n = NutritionPreferences()
    assert n.weight_goal == "maintain"
    assert n.dietary_style == "omnivore"
    assert n.food_restrictions == []
    assert n.coaching_style == "brief"


def test_nutrition_preferences_roundtrip():
    n = NutritionPreferences(
        weight_goal="lose",
        dietary_style="vegan",
        food_restrictions=["gluten", "nuts"],
        coaching_style="detailed",
    )
    d = n.to_dict()
    assert d["weight_goal"] == "lose"
    assert d["food_restrictions"] == ["gluten", "nuts"]
    n2 = NutritionPreferences.from_dict(d)
    assert n2 == n


def test_nutrition_preferences_from_dict_partial():
    # Missing keys fall back to defaults
    n = NutritionPreferences.from_dict({"weight_goal": "gain"})
    assert n.weight_goal == "gain"
    assert n.dietary_style == "omnivore"
    assert n.coaching_style == "brief"


# ── UserProfile persists nutrition ────────────────────────────────────────────


def test_user_profile_includes_nutrition():
    profile = UserProfile()
    d = profile.to_dict()
    assert "nutrition" in d
    assert d["nutrition"]["weight_goal"] == "maintain"


def test_user_profile_nutrition_roundtrip():
    profile = UserProfile(
        nutrition=NutritionPreferences(
            weight_goal="lose",
            dietary_style="vegetarian",
            food_restrictions=["dairy"],
            coaching_style="macros",
        )
    )
    d = profile.to_dict()
    profile2 = UserProfile.from_dict(d)
    assert profile2.nutrition.weight_goal == "lose"
    assert profile2.nutrition.dietary_style == "vegetarian"
    assert profile2.nutrition.food_restrictions == ["dairy"]
    assert profile2.nutrition.coaching_style == "macros"


def test_user_profile_from_dict_without_nutrition():
    # Existing profiles without a nutrition key get defaults
    d = {
        "version": "1.0",
        "profile": {"name": "Pat"},
        "fitness": {},
        "garmin": {},
        "schedule": {},
        "ai_coach": {},
    }
    profile = UserProfile.from_dict(d)
    assert profile.nutrition.weight_goal == "maintain"


# ── Handler: personalized nutrition coaching ──────────────────────────────────


def _make_handler(nutrition: dict, ctl: float = 0.0):
    from garmin_coach.handler import MessageHandler

    config = {
        "name": "Tester",
        "setup_complete": True,
        "garmin_connected": False,
        "ai": {"enabled": False},
        "nutrition": nutrition,
    }
    h = MessageHandler(config=config)
    h._ai_coach = None
    return h, {"ctl": ctl, "atl": 0, "tsb": 0, "has_data": True, "nutrition": nutrition}


def test_nutrition_response_high_load():
    h, ctx = _make_handler({}, ctl=60.0)
    resp = h._handle_ask_nutrition(ctx)
    assert "High training load" in resp


def test_nutrition_response_low_load():
    h, ctx = _make_handler({}, ctl=10.0)
    resp = h._handle_ask_nutrition(ctx)
    assert "base fitness" in resp


def test_nutrition_response_weight_goal_lose():
    h, ctx = _make_handler({"weight_goal": "lose"}, ctl=40.0)
    resp = h._handle_ask_nutrition(ctx)
    assert "deficit" in resp


def test_nutrition_response_weight_goal_gain():
    h, ctx = _make_handler({"weight_goal": "gain"}, ctl=40.0)
    resp = h._handle_ask_nutrition(ctx)
    assert "surplus" in resp


def test_nutrition_response_vegan():
    h, ctx = _make_handler({"dietary_style": "vegan"}, ctl=20.0)
    resp = h._handle_ask_nutrition(ctx)
    assert "plant-based" in resp or "legumes" in resp


def test_nutrition_response_restrictions():
    h, ctx = _make_handler({"food_restrictions": ["gluten", "dairy"]}, ctl=20.0)
    resp = h._handle_ask_nutrition(ctx)
    assert "gluten" in resp
    assert "dairy" in resp


def test_nutrition_response_detailed_style():
    h, ctx = _make_handler({"coaching_style": "detailed"}, ctl=20.0)
    resp = h._handle_ask_nutrition(ctx)
    assert "\n" in resp  # detailed uses newline-separated lines
    assert "hydrated" in resp


def test_nutrition_response_macros_style():
    h, ctx = _make_handler({"coaching_style": "macros"}, ctl=60.0)
    resp = h._handle_ask_nutrition(ctx)
    assert "protein/kg" in resp


def test_nutrition_response_differs_by_profile():
    """Vegan + losing weight gets different advice than omnivore + gaining."""
    h1, ctx1 = _make_handler({"dietary_style": "vegan", "weight_goal": "lose"}, ctl=40.0)
    h2, ctx2 = _make_handler({"dietary_style": "omnivore", "weight_goal": "gain"}, ctl=40.0)
    resp1 = h1._handle_ask_nutrition(ctx1)
    resp2 = h2._handle_ask_nutrition(ctx2)
    assert resp1 != resp2


def test_process_message_uses_saved_nutrition_config(monkeypatch):
    import garmin_coach.handler as handler

    monkeypatch.setattr(
        handler,
        "_load_config",
        lambda: {
            "name": "Tester",
            "setup_complete": True,
            "garmin_connected": False,
            "ai": {"enabled": False},
            "nutrition": {
                "weight_goal": "lose",
                "dietary_style": "vegan",
                "food_restrictions": ["gluten"],
                "coaching_style": "detailed",
            },
        },
    )
    monkeypatch.setattr(
        handler,
        "get_training_load_manager",
        lambda: SimpleNamespace(get_context=lambda: {"ctl": 45, "atl": 50, "tsb": -5}),
    )
    monkeypatch.setattr(handler, "detect_intent", lambda message: handler.Intent.ASK_NUTRITION)

    response = handler.process_message("오늘 식단 어떻게 먹지?")

    assert "deficit" in response
    assert "plant-based" in response or "legumes" in response
    assert "gluten" in response
