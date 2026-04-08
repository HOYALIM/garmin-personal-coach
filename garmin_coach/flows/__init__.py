"""Channel-agnostic business flows.

IMPORTANT: No module in this package may import from garmin_coach.interfaces
or any concrete channel implementation. All user interaction goes through
garmin_coach.ports.CoachingPort.
"""

from garmin_coach.flows.evening_checkin import EveningCheckinFlow
from garmin_coach.flows.goals import GoalsFlow
from garmin_coach.flows.injury_report import InjuryReportFlow
from garmin_coach.flows.morning_briefing import MorningBriefingFlow
from garmin_coach.flows.nutrition_log import NutritionLogFlow
from garmin_coach.flows.post_workout import PostWorkoutFlow
from garmin_coach.flows.settings import SettingsFlow

try:
    from garmin_coach.flows.onboarding import OnboardingFlow
except ModuleNotFoundError:
    OnboardingFlow = None

__all__ = [
    "EveningCheckinFlow",
    "GoalsFlow",
    "InjuryReportFlow",
    "MorningBriefingFlow",
    "NutritionLogFlow",
    "PostWorkoutFlow",
    "SettingsFlow",
]

if OnboardingFlow is not None:
    __all__.append("OnboardingFlow")
