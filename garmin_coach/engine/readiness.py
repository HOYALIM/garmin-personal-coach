from __future__ import annotations

from dataclasses import dataclass

from garmin_coach.models import HealthMetrics, ReadinessScore


@dataclass
class ReadinessCalculator:
    COMPONENTS: dict[str, float] = None  # type: ignore[assignment]
    THRESHOLDS: dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.COMPONENTS is None:
            self.COMPONENTS = {
                "hrv_deviation_pct": 0.30,
                "sleep_score": 0.25,
                "body_battery": 0.15,
                "rhr": 0.15,
                "tsb": 0.10,
                "stress_avg": 0.05,
            }
        if self.THRESHOLDS is None:
            self.THRESHOLDS = {"green": 75, "yellow": 50, "red": 30}

    def calculate(self, metrics: HealthMetrics, available_days: int = 14) -> ReadinessScore:
        normalized = {
            "hrv_deviation_pct": self._norm_hrv(metrics.hrv_deviation_pct),
            "sleep_score": self._clamp(metrics.sleep_score),
            "body_battery": self._clamp(metrics.body_battery_morning),
            "rhr": self._norm_rhr(metrics.rhr.deviation_bpm if metrics.rhr else None),
            "tsb": self._norm_tsb(metrics.tsb),
            "stress_avg": self._norm_stress(metrics.stress_avg),
        }
        present = {k: v for k, v in normalized.items() if v is not None}
        if not present:
            return ReadinessScore(
                score=50, level="yellow", confidence="low", reason="No readiness inputs available"
            )
        active_weight = sum(self.COMPONENTS[key] for key in present)
        redistributed = {key: self.COMPONENTS[key] / active_weight for key in present}
        score = round(sum(present[key] * redistributed[key] for key in present))
        level = self._level(score)
        confidence = "high" if available_days >= 14 else "low"
        reason = f"Readiness {level} based on {len(present)} components"
        return ReadinessScore(
            score=score,
            level=level,
            components={k: round(v, 1) for k, v in present.items()},
            component_weights={k: round(v, 3) for k, v in redistributed.items()},
            confidence=confidence,
            reason=reason,
        )

    def _level(self, score: int) -> str:
        if score >= self.THRESHOLDS["green"]:
            return "green"
        if score >= self.THRESHOLDS["yellow"]:
            return "yellow"
        if score >= self.THRESHOLDS["red"]:
            return "red"
        return "critical"

    @staticmethod
    def _clamp(value: float | int | None) -> float | None:
        if value is None:
            return None
        return max(0.0, min(100.0, float(value)))

    @staticmethod
    def _norm_hrv(value: float | None) -> float | None:
        if value is None:
            return None
        return max(0.0, min(100.0, ((float(value) + 30.0) / 60.0) * 100.0))

    @staticmethod
    def _norm_rhr(value: float | None) -> float | None:
        if value is None:
            return None
        bounded = max(-15.0, min(15.0, float(value)))
        return ((15.0 - bounded) / 30.0) * 100.0

    @staticmethod
    def _norm_tsb(value: float | None) -> float | None:
        if value is None:
            return None
        bounded = max(-30.0, min(30.0, float(value)))
        return ((bounded + 30.0) / 60.0) * 100.0

    @staticmethod
    def _norm_stress(value: float | None) -> float | None:
        if value is None:
            return None
        bounded = max(0.0, min(100.0, float(value)))
        return 100.0 - bounded
