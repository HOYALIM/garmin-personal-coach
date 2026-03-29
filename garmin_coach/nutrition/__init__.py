from typing import Optional
from dataclasses import dataclass


@dataclass
class NutritionTargets:
    calories: int
    carbs_grams: int
    protein_grams: int
    fat_grams: int
    water_ml: int
    sodium_mg: int


def calculate_basal_metabolic_rate(
    weight_kg: float, height_cm: int, age: int, sex: str
) -> float:
    if sex.lower() == "male":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161


def calculate_total_daily_energy_expenditure(
    bmr: float, activity_level: str = "moderate"
) -> float:
    multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }
    return bmr * multipliers.get(activity_level.lower(), 1.55)


def calculate_activity_calories(
    sport: str, duration_minutes: int, weight_kg: float
) -> int:
    calories_per_kg_per_min = {
        "running": 0.12,
        "cycling": 0.08,
        "swimming": 0.10,
        "triathlon": 0.10,
        "hiking": 0.07,
        "walking": 0.04,
        "strength": 0.05,
    }
    rate = calories_per_kg_per_min.get(sport.lower(), 0.08)
    return int(rate * weight_kg * duration_minutes)


def calculate_macros(
    total_calories: int, sport: str, duration_minutes: int
) -> tuple[int, int, int]:
    carbs_per_min = {
        "running": 1.2,
        "cycling": 0.9,
        "swimming": 1.0,
        "triathlon": 1.0,
        "hiking": 0.8,
    }
    base_carbs = int(total_calories * 0.5 / 4)
    sport_carbs = int(carbs_per_min.get(sport.lower(), 1.0) * duration_minutes)
    carbs = base_carbs + sport_carbs

    protein_per_kg = 1.6 if sport.lower() in ("running", "swimming") else 2.0
    protein = 80
    if duration_minutes > 30:
        protein = int(protein_per_kg * 50)

    fat = int((total_calories - carbs * 4 - protein * 4) / 9)
    fat = max(fat, 20)

    return carbs, protein, fat


def calculate_hydration(
    weight_kg: float, duration_minutes: int, intensity: str = "moderate"
) -> int:
    base_ml_per_kg = 35
    base = int(weight_kg * base_ml_per_kg)

    activity_additional = {
        "low": 0,
        "moderate": int(duration_minutes * 5),
        "high": int(duration_minutes * 10),
        "very_high": int(duration_minutes * 15),
    }

    return base + activity_additional.get(intensity.lower(), 0)


def calculate_nutrition_targets(
    weight_kg: float,
    height_cm: int,
    age: int,
    sex: str,
    sport: str,
    duration_minutes: int,
    activity_level: str = "moderate",
    intensity: str = "moderate",
) -> NutritionTargets:
    bmr = calculate_basal_metabolic_rate(weight_kg, height_cm, age, sex)
    tdee = calculate_total_daily_energy_expenditure(bmr, activity_level)

    activity_cal = calculate_activity_calories(sport, duration_minutes, weight_kg)
    total_calories = int(tdee + activity_cal)

    carbs, protein, fat = calculate_macros(total_calories, sport, duration_minutes)

    water_ml = calculate_hydration(weight_kg, duration_minutes, intensity)
    sodium_mg = int(duration_minutes * 20) + 1500

    return NutritionTargets(
        calories=total_calories,
        carbs_grams=carbs,
        protein_grams=protein,
        fat_grams=fat,
        water_ml=water_ml,
        sodium_mg=sodium_mg,
    )


def recommend_pre_workout(sport: str, duration_minutes: int) -> dict:
    recommendations = {
        "running": {
            "timing": "2-3 hours before",
            "carbs": "1-3 g/kg body weight",
            "protein": "0.2 g/kg",
            "fat": "low",
            "examples": [
                "Oatmeal with banana",
                "Toast with peanut butter",
                "Rice with eggs",
            ],
        },
        "cycling": {
            "timing": "2-4 hours before",
            "carbs": "1-4 g/kg body weight",
            "protein": "0.2-0.4 g/kg",
            "fat": "low-medium",
            "examples": ["Banana bread", "Smoothie", "Pasta with sauce"],
        },
        "swimming": {
            "timing": "2-3 hours before",
            "carbs": "1-2 g/kg body weight",
            "protein": "0.2 g/kg",
            "fat": "low",
            "examples": ["Rice with chicken", "Toast with honey", "Yogurt parfait"],
        },
        "default": {
            "timing": "2-3 hours before",
            "carbs": "1-2 g/kg body weight",
            "protein": "0.2 g/kg",
            "fat": "low",
            "examples": ["Balanced meal", "Sandwich", "Smoothie bowl"],
        },
    }
    return recommendations.get(sport.lower(), recommendations["default"])


def recommend_post_workout(sport: str, duration_minutes: int) -> dict:
    protein_recommendation = 20 if duration_minutes < 60 else 30
    carbs_recommendation = (
        min(1.5, 0.5 + duration_minutes / 120) if duration_minutes > 45 else 0.5
    )

    return {
        "timing": "Within 30-60 minutes",
        "carbs": f"{carbs_recommendation} g/kg body weight",
        "protein": f"{protein_recommendation}g",
        "ratio": "3:1 carbs to protein",
        "examples": [
            "Protein shake with banana",
            "Greek yogurt with berries",
            "Chocolate milk",
            "Chicken with rice",
        ],
    }
