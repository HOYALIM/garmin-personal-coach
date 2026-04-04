from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date


@dataclass
class CanonicalDailyActivityBatch:
    source: str
    activity_date: date
    external_ids: list[str]
    activity_count: int
    primary_sport: str
    duration_min: float
    distance_km: float
    calories: int
    trimp: float

    @property
    def source_key(self) -> str:
        return f"{self.source}:{self.activity_date.isoformat()}"

    def description(self) -> str:
        return (
            f"[{self.source}-sync] {self.activity_count} activities, "
            f"distance={self.distance_km:.2f}km, ids={','.join(self.external_ids[:3])}"
        )

    def fingerprint(self) -> str:
        payload = (
            f"{self.source}|{self.activity_date.isoformat()}|{','.join(self.external_ids)}|"
            f"{self.activity_count}|{self.primary_sport}|{self.duration_min:.1f}|"
            f"{self.distance_km:.2f}|{self.calories}|{self.trimp:.1f}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
