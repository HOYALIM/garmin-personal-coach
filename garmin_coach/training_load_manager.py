"""Training load manager with persistence."""

import os
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from garmin_coach.training_load import (
    TrainingLoadCalculator,
    LoadSnapshot,
    DailyLoad,
    Sport,
    FormCategory,
)


DATA_DIR = os.path.expanduser("~/.config/garmin_coach")
LOAD_FILE = os.path.join(DATA_DIR, "training_load.json")
PROFILE_FILE = os.path.join(DATA_DIR, "config.yaml")

os.makedirs(DATA_DIR, exist_ok=True)


class TrainingLoadManager:
    _instance: Optional["TrainingLoadManager"] = None

    def __init__(self):
        self._ensure_data_dir()
        self._load_calculator()

    @classmethod
    def get_instance(cls) -> "TrainingLoadManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_data_dir(self):
        os.makedirs(DATA_DIR, exist_ok=True)

    def _load_calculator(self):
        self._sex = self._load_sex()
        self._calc = TrainingLoadCalculator(sex=self._sex)

        if os.path.exists(LOAD_FILE):
            try:
                self._calc = TrainingLoadCalculator.from_json(Path(LOAD_FILE), sex=self._sex)
            except Exception:
                self._calc = TrainingLoadCalculator(sex=self._sex)

    def _load_sex(self) -> str:
        try:
            import yaml

            if os.path.exists(PROFILE_FILE):
                with open(PROFILE_FILE) as f:
                    config = yaml.safe_load(f) or {}
                    return config.get("sex", "male")
        except Exception:
            pass
        return "male"

    @property
    def calculator(self) -> TrainingLoadCalculator:
        return self._calc

    def get_snapshot(self, d: Optional[date] = None) -> LoadSnapshot:
        d = d or date.today()
        return self._calc.get_snapshot(d)

    def add_activity(
        self,
        session_date: date,
        trimp: float,
        sport: str = "running",
        duration_min: float = 0,
        description: str = "",
    ):
        sport_enum = Sport(sport) if sport in [s.value for s in Sport] else Sport.OTHER
        self._calc.add_session(
            session_date=session_date,
            trimp=trimp,
            sport=sport_enum,
            duration_min=duration_min,
            description=description,
        )
        self.save()

    def get_context(self) -> dict:
        snapshot = self.get_snapshot()
        return {
            "ctl": snapshot.ctl,
            "atl": snapshot.atl,
            "tsb": snapshot.tsb,
            "form": snapshot.form.value,
            "date": snapshot.date.isoformat(),
        }

    def save(self):
        try:
            self._calc.export_json(Path(LOAD_FILE))
        except Exception as e:
            print(f"Warning: Could not save training load: {e}")

    @classmethod
    def reset(cls):
        cls._instance = None


def get_training_load_manager() -> TrainingLoadManager:
    return TrainingLoadManager.get_instance()
