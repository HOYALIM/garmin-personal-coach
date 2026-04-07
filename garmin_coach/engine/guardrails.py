from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from garmin_coach.models import CoachingResponse, HealthMetrics, UserProfile


class GuardrailAction(Enum):
    PASS = "pass"
    MODIFY = "modify"
    OVERRIDE = "override"
    BLOCK_AND_ALERT = "block"


@dataclass
class GuardrailResult:
    action: GuardrailAction
    original_coaching: str
    modified_coaching: str | None
    reason: str
    severity: str
    reasons: list[str] = field(default_factory=list)
    rule_id: str = ""
    append_message: str | None = None


class CoachingGuardrails:
    _severity_rank = {"info": 0, "warning": 1, "critical": 2}
    _action_rank = {
        GuardrailAction.PASS: 0,
        GuardrailAction.MODIFY: 1,
        GuardrailAction.OVERRIDE: 2,
        GuardrailAction.BLOCK_AND_ALERT: 3,
    }

    def validate(
        self, coaching: CoachingResponse, user: UserProfile, current_metrics: HealthMetrics
    ) -> GuardrailResult:
        checks = [
            self._check_overtraining(coaching, current_metrics),
            self._check_sleep_recovery(coaching, current_metrics),
            self._check_heart_rate(coaching, user, current_metrics),
            self._check_injury(coaching, user),
            self._check_medical_claims(coaching),
            self._check_nutrition_safety(coaching, user),
            self._check_environment(coaching, current_metrics),
            self._check_ramp_rate(coaching, current_metrics),
        ]
        active = [result for result in checks if result.action != GuardrailAction.PASS]
        if not active:
            return self._pass(coaching)
        return self._compose_result(coaching, active)

    def _compose_result(
        self, coaching: CoachingResponse, results: list[GuardrailResult]
    ) -> GuardrailResult:
        top = max(
            results,
            key=lambda result: (
                self._action_rank[result.action],
                self._severity_rank[result.severity],
            ),
        )
        text = coaching.text
        if top.action in {GuardrailAction.OVERRIDE, GuardrailAction.BLOCK_AND_ALERT}:
            text = top.modified_coaching or text
        else:
            rewrite_results = [
                result
                for result in results
                if result.action == GuardrailAction.MODIFY
                and result.modified_coaching
                and result.modified_coaching != coaching.text
            ]
            for rewrite in rewrite_results:
                text = self._merge_rewrite(text, coaching.text, rewrite.modified_coaching or text)
        append_messages = [result.append_message for result in results if result.append_message]
        if append_messages:
            deduped = []
            for message in append_messages:
                if message not in deduped:
                    deduped.append(message)
            if text:
                text = text + "\n\n" + "\n".join(deduped)
            else:
                text = "\n".join(deduped)
        reasons = []
        for result in results:
            if result.reason not in reasons:
                reasons.append(result.reason)
        return GuardrailResult(
            action=top.action,
            original_coaching=coaching.text,
            modified_coaching=text,
            reason=" / ".join(reasons),
            severity=top.severity,
            reasons=reasons,
            rule_id=top.rule_id,
        )

    @staticmethod
    def _merge_rewrite(current_text: str, original_text: str, rewritten_text: str) -> str:
        if rewritten_text == original_text:
            return current_text
        if rewritten_text.startswith(original_text):
            suffix = rewritten_text[len(original_text) :]
            if suffix and suffix not in current_text:
                return current_text + suffix
            return current_text
        if rewritten_text not in current_text:
            return rewritten_text
        return current_text

    def _pass(self, coaching: CoachingResponse) -> GuardrailResult:
        return GuardrailResult(
            GuardrailAction.PASS,
            coaching.text,
            None,
            "정상 범위입니다.",
            "info",
            reasons=["정상 범위입니다."],
            rule_id="pass",
        )

    def _check_overtraining(
        self, coaching: CoachingResponse, metrics: HealthMetrics
    ) -> GuardrailResult:
        if metrics.tsb < -30 and coaching.max_zone >= 4:
            reason = f"TSB={metrics.tsb:.1f} (< -30). 과훈련 위험으로 고강도 세션을 차단합니다."
            return GuardrailResult(
                GuardrailAction.OVERRIDE,
                coaching.text,
                self._generate_rest_coaching(metrics),
                reason,
                "critical",
                reasons=[reason],
                rule_id="overtraining-tsb",
            )
        if metrics.ramp_rate > 5.0:
            reason = f"Ramp Rate={metrics.ramp_rate:.1f} (> 5.0/주). 과부하 경고를 추가합니다."
            return GuardrailResult(
                GuardrailAction.MODIFY,
                coaching.text,
                coaching.text,
                reason,
                "warning",
                reasons=[reason],
                rule_id="overtraining-ramp-rate",
                append_message="⚠️ 최근 Ramp Rate가 높아 부하 증가를 보수적으로 조정하세요.",
            )
        return self._pass(coaching)

    def _check_sleep_recovery(
        self, coaching: CoachingResponse, metrics: HealthMetrics
    ) -> GuardrailResult:
        if (metrics.body_battery_morning or 999) < 25:
            reason = f"Body Battery={metrics.body_battery_morning} (< 25). 완전 휴식을 강제합니다."
            return GuardrailResult(
                GuardrailAction.OVERRIDE,
                coaching.text,
                self._generate_full_rest(metrics),
                reason,
                "critical",
                reasons=[reason],
                rule_id="sleep-body-battery",
            )
        reasons: list[str] = []
        append_messages: list[str] = []
        modified_text: str | None = None
        if (metrics.sleep_score or 100) < 50 and coaching.intensity in {
            "hard",
            "interval",
            "tempo",
        }:
            reasons.append(f"Sleep Score={metrics.sleep_score} (< 50). 강도를 낮춥니다.")
            modified_text = self._downgrade_to_easy(coaching, metrics)
        if (metrics.hrv_deviation_pct or 0) < -15 and coaching.intensity in {
            "hard",
            "interval",
            "tempo",
        }:
            reasons.append(f"HRV 기준선 대비 {metrics.hrv_deviation_pct:.0f}%. 강도를 낮춥니다.")
            modified_text = self._downgrade_to_easy(coaching, metrics)
        if len(metrics.recent_sleep_scores) >= 3 and all(
            score < 60 for score in metrics.recent_sleep_scores[-3:]
        ):
            reasons.append("연속 3일 이상 Sleep Score 60 미만이라 누적 수면 부채를 경고합니다.")
            append_messages.append(
                "⚠️ 최근 3일 연속 수면 점수가 낮습니다. 오늘은 누적 수면 부채를 해소하는 쪽이 안전합니다."
            )
        if reasons:
            return GuardrailResult(
                GuardrailAction.MODIFY,
                coaching.text,
                modified_text or coaching.text,
                " / ".join(reasons),
                "warning",
                reasons=reasons,
                rule_id="sleep-recovery",
                append_message="\n".join(append_messages) if append_messages else None,
            )
        return self._pass(coaching)

    def _check_heart_rate(
        self, coaching: CoachingResponse, user: UserProfile, metrics: HealthMetrics
    ) -> GuardrailResult:
        reasons: list[str] = []
        append_messages: list[str] = []
        modified_text: str | None = None
        action = GuardrailAction.MODIFY
        severity = "warning"
        if user.medical and user.medical.beta_blocker and coaching.uses_hr_zones:
            reasons.append("베타차단제 복용으로 HR Zone 대신 RPE 기반 지시로 전환합니다.")
            modified_text = self._convert_to_rpe_based(coaching)
            severity = "info"
        if metrics.recent_max_hr is not None and metrics.recent_max_hr > (220 - user.age) * 1.05:
            reason = f"최근 최대 심박 {metrics.recent_max_hr}bpm이 추정 최대 심박의 105%를 초과했습니다. 운동 중단을 권고합니다."
            return GuardrailResult(
                GuardrailAction.OVERRIDE,
                coaching.text,
                "최근 심박 이상이 감지되었습니다. 오늘은 운동을 중단하고 상태를 확인하세요.",
                reason,
                "critical",
                reasons=[reason] + reasons,
                rule_id="heart-rate-max-anomaly",
            )
        if (
            metrics.rhr_today is not None
            and metrics.rhr_baseline is not None
            and metrics.rhr_today - metrics.rhr_baseline > 15
        ):
            reasons.append(
                f"안정시 심박이 기준선보다 {metrics.rhr_today - metrics.rhr_baseline:.0f}bpm 높습니다. 건강 이상 가능성을 안내합니다."
            )
            append_messages.append(self._rhr_warning(metrics))
        if metrics.spo2 and metrics.spo2.min_pct is not None and metrics.spo2.min_pct <= 90:
            reasons.append("SpO2가 90% 이하로 감지되어 의료 상담 권고를 추가합니다.")
            append_messages.append(
                "🚨 SpO2가 낮게 감지되었습니다. 운동보다 의료 상담을 우선하세요."
            )
            severity = "critical"
        if reasons:
            return GuardrailResult(
                action,
                coaching.text,
                modified_text or coaching.text,
                " / ".join(reasons),
                severity,
                reasons=reasons,
                rule_id="heart-rate",
                append_message="\n".join(append_messages) if append_messages else None,
            )
        return self._pass(coaching)

    def _check_injury(self, coaching: CoachingResponse, user: UserProfile) -> GuardrailResult:
        if not user.medical or not user.medical.current_injuries:
            return self._pass(coaching)
        results: list[GuardrailResult] = []
        for injury in user.medical.current_injuries:
            if injury.medical_clearance == "pending" and coaching.intensity in {
                "hard",
                "interval",
                "tempo",
                "race",
            }:
                reason = f"부상 부위 '{injury.body_part}' 의료 허가 대기 중이므로 고강도 운동을 차단합니다."
                results.append(
                    GuardrailResult(
                        GuardrailAction.OVERRIDE,
                        coaching.text,
                        self._generate_pending_clearance_coaching(injury.body_part),
                        reason,
                        "critical",
                        reasons=[reason],
                        rule_id="injury-clearance",
                    )
                )
            for restriction in injury.restrictions:
                if self._coaching_violates_restriction(coaching, restriction):
                    reason = f"부상 제한사항 '{restriction}'을 반영해 세션을 조정합니다."
                    results.append(
                        GuardrailResult(
                            GuardrailAction.MODIFY,
                            coaching.text,
                            self._apply_restriction(coaching, restriction),
                            reason,
                            "warning",
                            reasons=[reason],
                            rule_id="injury-restriction",
                        )
                    )
            if injury.pain_reports_count >= 2 and injury.restricted_session_types:
                reason = f"같은 부위 통증이 반복되어 {', '.join(injury.restricted_session_types)} 유형을 자동 제한합니다."
                results.append(
                    GuardrailResult(
                        GuardrailAction.OVERRIDE,
                        coaching.text,
                        f"최근 {injury.body_part} 통증이 반복되어 해당 부위 부담이 적은 회복 세션만 권장합니다.",
                        reason,
                        "critical",
                        reasons=[reason],
                        rule_id="injury-repeat-pain",
                    )
                )
        if not results:
            return self._pass(coaching)
        return self._compose_result(coaching, results)

    def _check_nutrition_safety(
        self, coaching: CoachingResponse, user: UserProfile
    ) -> GuardrailResult:
        if user.nutrition and user.nutrition.allergies:
            for allergen in user.nutrition.allergies:
                if allergen and allergen.lower() in coaching.text.lower():
                    text = re.sub(
                        re.escape(allergen),
                        "[알레르기 식품 제거]",
                        coaching.text,
                        flags=re.IGNORECASE,
                    )
                    reason = f"알레르기 식품 '{allergen}'을 제거했습니다."
                    return GuardrailResult(
                        GuardrailAction.MODIFY,
                        coaching.text,
                        text,
                        reason,
                        "warning",
                        reasons=[reason],
                        rule_id="nutrition-allergy",
                    )
        kcal_match = re.search(r"(\d{2,4})\s?kcal", coaching.text.lower())
        if kcal_match and user.weight_kg and user.height_cm:
            recommended = int(kcal_match.group(1))
            bmr = max(
                0,
                int(
                    10 * user.weight_kg
                    + 6.25 * user.height_cm
                    - 5 * user.age
                    + (5 if user.sex == "male" else -161)
                ),
            )
            if recommended < bmr:
                reason = f"제안 칼로리 {recommended}kcal가 추정 BMR {bmr}kcal 미만입니다."
                return GuardrailResult(
                    GuardrailAction.BLOCK_AND_ALERT,
                    coaching.text,
                    "⚠️ BMR 이하의 극단적 칼로리 제한은 권장할 수 없습니다. 더 안전한 범위로 다시 안내합니다.",
                    reason,
                    "critical",
                    reasons=[reason],
                    rule_id="nutrition-bmr",
                )
        if re.search(r"(완치|치료|예방).*(보충제|supplement)", coaching.text.lower()):
            reason = "보충제의 의학적 효능 주장 표현을 제거했습니다."
            return GuardrailResult(
                GuardrailAction.MODIFY,
                coaching.text,
                coaching.text
                + "\n\n※ 보충제의 의학적 효능은 단정하지 않습니다. 필요 시 전문가와 상의하세요.",
                reason,
                "warning",
                reasons=[reason],
                rule_id="nutrition-supplement-claim",
            )
        return self._pass(coaching)

    def _check_medical_claims(self, coaching: CoachingResponse) -> GuardrailResult:
        patterns = [r"진단[을를]?", r"처방", r"치료[를]?"]
        medication_patterns = [r"약[을를]?\s*(먹|복용|처방)"]
        if any(re.search(pattern, coaching.text) for pattern in patterns + medication_patterns):
            cleaned = re.sub(r"진단|처방|치료", "의학적 판단", coaching.text)
            cleaned = re.sub(r"약[을를]?\s*(먹|복용|처방)", "약물 관련 결정", cleaned)
            cleaned += (
                "\n\n※ 의학적 진단이나 약물 조언은 제공하지 않습니다. 필요 시 전문의와 상의하세요."
            )
            reason = "의학적 진단/치료 표현을 제거하고 전문의 상담 안내를 추가했습니다."
            return GuardrailResult(
                GuardrailAction.MODIFY,
                coaching.text,
                cleaned,
                reason,
                "critical",
                reasons=[reason],
                rule_id="medical-claims",
            )
        return self._pass(coaching)

    def _check_environment(
        self, coaching: CoachingResponse, metrics: HealthMetrics
    ) -> GuardrailResult:
        if not metrics.environment:
            return self._pass(coaching)
        warnings: list[str] = []
        env = metrics.environment
        if env.temperature_c is not None and env.temperature_c >= 35:
            warnings.append("⚠️ 기온이 매우 높습니다. 실외 고강도 운동은 자제하세요.")
        if env.wbgt_c is not None and env.wbgt_c >= 28:
            warnings.append(
                "⚠️ WBGT가 높아 열 스트레스 위험이 있습니다. 강도를 낮추거나 실내 대안을 고려하세요."
            )
        if env.temperature_c is not None and env.temperature_c <= -15:
            warnings.append("⚠️ 기온이 매우 낮습니다. 실외 운동 시 보온과 강도 조절이 필요합니다.")
        if env.air_quality and env.air_quality.lower() in {"very_bad", "매우 나쁨"}:
            warnings.append("⚠️ 공기질이 매우 나쁩니다. 실외 운동은 피하세요.")
        if warnings:
            reason = "환경 안전 경고를 추가합니다."
            return GuardrailResult(
                GuardrailAction.MODIFY,
                coaching.text,
                coaching.text,
                reason,
                "warning",
                reasons=[reason],
                rule_id="environment",
                append_message="\n".join(warnings),
            )
        return self._pass(coaching)

    def _check_ramp_rate(
        self, coaching: CoachingResponse, metrics: HealthMetrics
    ) -> GuardrailResult:
        warnings: list[str] = []
        reasons: list[str] = []
        if metrics.training_load.weekly_volume_increase_pct > 10:
            reasons.append("주간 볼륨 증가가 10%를 초과했습니다.")
            warnings.append("⚠️ 주간 볼륨 증가가 커서 10% rule을 넘지 않도록 줄이세요.")
        if metrics.monotony >= 2.0:
            reasons.append(f"Monotony={metrics.monotony:.1f} (>=2.0).")
            warnings.append("⚠️ 최근 훈련 단조로움이 높아 변화를 주는 편이 안전합니다.")
        if (
            metrics.training_load.strain > 0
            and metrics.training_load.ctl > 0
            and metrics.training_load.strain > metrics.training_load.ctl * 2
        ):
            reasons.append("Strain이 CTL의 2배를 초과했습니다.")
            warnings.append("⚠️ 누적 strain이 높습니다. 회복일을 확보하세요.")
        if reasons:
            return GuardrailResult(
                GuardrailAction.MODIFY,
                coaching.text,
                coaching.text,
                " / ".join(reasons),
                "warning",
                reasons=reasons,
                rule_id="training-load",
                append_message="\n".join(warnings),
            )
        return self._pass(coaching)

    @staticmethod
    def _generate_rest_coaching(metrics: HealthMetrics) -> str:
        return f"오늘은 회복이 우선입니다. TSB {metrics.tsb:.1f}로 낮아 완전 휴식이나 매우 가벼운 회복만 권장합니다."

    @staticmethod
    def _generate_full_rest(metrics: HealthMetrics) -> str:
        return f"기상 시 Body Battery가 {metrics.body_battery_morning}로 낮습니다. 오늘은 완전 휴식을 권장합니다. 게으른 것이 아니라 현명한 결정입니다."

    @staticmethod
    def _downgrade_to_easy(coaching: CoachingResponse, metrics: HealthMetrics) -> str:
        return f"원래 계획 대신 20-40% 강도를 낮춘 이지 세션으로 조정하세요. 근거: 수면/회복 지표 저하 (sleep={metrics.sleep_score}, hrv={metrics.hrv_deviation_pct})."

    @staticmethod
    def _convert_to_rpe_based(coaching: CoachingResponse) -> str:
        return coaching.text + "\n\n심박 대신 RPE 4-5 수준의 체감 강도로 진행하세요."

    @staticmethod
    def _rhr_warning(metrics: HealthMetrics) -> str:
        return f"⚠️ 안정시 심박이 기준선보다 높습니다 ({metrics.rhr_today} vs {metrics.rhr_baseline}). 무리하지 말고 이상 지속 시 전문의 상담을 권합니다."

    @staticmethod
    def _generate_pending_clearance_coaching(body_part: str) -> str:
        return f"{body_part} 관련 의료 허가가 아직 확인되지 않아 고강도 운동 대신 휴식 또는 부담이 적은 회복 운동만 권장합니다."

    @staticmethod
    def _coaching_violates_restriction(coaching: CoachingResponse, restriction: str) -> bool:
        text = coaching.text.lower()
        restriction = restriction.lower()
        if restriction == "no_impact":
            return any(
                token in text for token in ("run", "interval", "tempo", "jump", "인터벌", "러닝")
            )
        if restriction.startswith("hr_below_") and coaching.uses_hr_zones:
            return True
        return restriction in text

    @staticmethod
    def _apply_restriction(coaching: CoachingResponse, restriction: str) -> str:
        return f"제한사항 '{restriction}'을 반영해 충격/고강도 요소를 제거하고 회복 중심으로 조정합니다."
