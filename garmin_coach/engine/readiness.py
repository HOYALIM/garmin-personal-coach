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
        garmin_score = None
        if metrics.training_readiness and metrics.training_readiness.score is not None:
            garmin_score = max(0.0, min(100.0, float(metrics.training_readiness.score)))
        normalized = {
            "garmin_training_readiness": garmin_score,
            "hrv_deviation_pct": self._norm_hrv(metrics.hrv_deviation_pct),
            "sleep_score": self._clamp(metrics.sleep_score),
            "body_battery": self._clamp(metrics.body_battery_morning),
            "rhr": self._norm_rhr(metrics.rhr.deviation_bpm if metrics.rhr else None),
            "tsb": self._norm_tsb(metrics.tsb),
            "stress_avg": self._norm_stress(metrics.stress_avg),
        }
        component_weights = dict(self.COMPONENTS)
        if garmin_score is not None:
            component_weights = {
                "garmin_training_readiness": 0.45,
                "hrv_deviation_pct": 0.18,
                "sleep_score": 0.15,
                "body_battery": 0.08,
                "rhr": 0.07,
                "tsb": 0.05,
                "stress_avg": 0.02,
            }
        present = {k: v for k, v in normalized.items() if v is not None}
        if not present:
            return ReadinessScore(
                score=50,
                level="yellow",
                confidence="low",
                reason="No readiness inputs available",
                limiting_factors=["missing_data"],
            )
        active_weight = sum(component_weights[key] for key in present)
        redistributed = {key: component_weights[key] / active_weight for key in present}
        score = round(sum(present[key] * redistributed[key] for key in present))
        level = self._level(score)
        confidence = self._confidence(present, available_days)
        limiting_factors = self._limiting_factors(metrics, present)
        reason = f"Readiness {level} based on {len(present)} components"
        return ReadinessScore(
            score=score,
            level=level,
            components={k: round(v, 1) for k, v in present.items()},
            component_weights={k: round(v, 3) for k, v in redistributed.items()},
            confidence=confidence,
            reason=reason,
            input_snapshot={
                "sleep_score": metrics.sleep_score,
                "body_battery": metrics.body_battery_morning,
                "hrv_deviation_pct": metrics.hrv_deviation_pct,
                "rhr_deviation_bpm": metrics.rhr.deviation_bpm if metrics.rhr else None,
                "tsb": metrics.tsb,
                "stress_avg": metrics.stress_avg,
                "garmin_training_readiness": metrics.training_readiness.score
                if metrics.training_readiness
                else None,
            },
            limiting_factors=limiting_factors,
        )

    @staticmethod
    def _confidence(present: dict[str, float], available_days: int) -> str:
        if len(present) >= 5 and available_days >= 7:
            return "high"
        if len(present) >= 3:
            return "medium"
        return "low"

    @staticmethod
    def _limiting_factors(metrics: HealthMetrics, present: dict[str, float]) -> list[str]:
        factors: list[str] = []
        if metrics.sleep_score is not None and metrics.sleep_score < 60:
            factors.append("sleep")
        if metrics.hrv_deviation_pct is not None and metrics.hrv_deviation_pct < -10:
            factors.append("hrv")
        if metrics.body_battery_morning is not None and metrics.body_battery_morning < 40:
            factors.append("body_battery")
        if metrics.rhr and metrics.rhr.deviation_bpm is not None and metrics.rhr.deviation_bpm > 7:
            factors.append("rhr")
        if metrics.tsb < -15:
            factors.append("fatigue")
        if not factors and present:
            factors.append("none")
        return factors

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
