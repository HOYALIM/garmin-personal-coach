from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from garmin_coach.models.feedback import (
    FeedbackCollectionStatus,
    FeedbackCompletion,
    FeedbackSummary,
    PainReport,
    RPEIntensityGap,
    SessionFeedback,
)
from garmin_coach.storage.database import GarminCoachDatabase


class FeedbackAggregatorService:
    def __init__(self, database: GarminCoachDatabase, guardrail_root: Path | None = None) -> None:
        self.database = database
        self.guardrail_root = guardrail_root

    def save_feedback(
        self,
        user_id: str,
        activity_id: str,
        feedback: dict[str, Any],
        *,
        activity_date: str | None = None,
    ) -> SessionFeedback:
        existing_payload = self.database.load_feedback(user_id, activity_id)
        existing = SessionFeedback.from_dict(existing_payload) if existing_payload else None
        session_date = self._resolve_session_date(existing, feedback, activity_date)
        collection_status = self._parse_collection_status(feedback, existing)
        merged = SessionFeedback(
            session_date=session_date,
            activity_id=activity_id,
            session_type=existing.session_type if existing else None,
            completion=self._parse_completion(feedback, existing),
            collection_status=collection_status,
            feeling=self._pick_value(feedback, "feeling", existing),
            rpe=self._parse_rpe(feedback.get("rpe"), existing.rpe if existing else None),
            target_pace_met=self._pick_value(feedback, "target_pace_met", existing),
            pain_report=self._build_pain_report(feedback, existing),
            during_nutrition=self._pick_value(feedback, "during_nutrition", existing),
            gi_issues=self._parse_gi_issues(feedback, existing),
            note=self._normalize_note(feedback.get("note"), existing.note if existing else ""),
            flagged_for_review=bool(
                feedback.get("feeling") == "pain" or (existing and existing.flagged_for_review)
            ),
            answered_keys=self._merge_keys(
                existing.answered_keys if existing else [], feedback.get("answered_keys"), feedback
            ),
            pending_keys=self._resolve_pending_keys(existing, feedback),
            source_event_id=self._pick_value(feedback, "source_event_id", existing),
            updated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        )
        if merged.pain_report:
            merged.pain_report.consecutive_count = self._consecutive_pain_count(
                user_id,
                activity_id,
                merged.pain_report.body_part,
                merged.session_date,
            )
        self.database.save_feedback(user_id, activity_id, merged.session_date, merged.to_dict())
        self._persist_auto_restrict(user_id, merged)
        return merged

    def get_feedback_summary(
        self,
        user_id: str,
        *,
        days: int = 14,
        end_date: date | None = None,
    ) -> FeedbackSummary:
        end = end_date or date.today()
        start = end - timedelta(days=max(days - 1, 0))
        rows = [
            SessionFeedback.from_dict(item)
            for item in self.database.list_feedback(
                user_id,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
            )
        ]
        if not rows:
            return FeedbackSummary(
                notes=["최근 피드백 데이터가 없어 주관적 반응 추세를 계산하지 못했습니다."]
            )

        rpe_values = [item.rpe for item in rows if item.rpe is not None]
        completed = sum(
            1 for item in rows if item.collection_status == FeedbackCollectionStatus.COMPLETE
        )
        partial = sum(
            1 for item in rows if item.collection_status == FeedbackCollectionStatus.PARTIAL
        )
        skipped = sum(
            1
            for item in rows
            if item.collection_status
            in {
                FeedbackCollectionStatus.SKIPPED,
                FeedbackCollectionStatus.TIMEOUT,
                FeedbackCollectionStatus.CANCELLED,
            }
        )
        notes: list[str] = []
        if any(item.collection_status != FeedbackCollectionStatus.COMPLETE for item in rows):
            notes.append(
                "일부 세션은 피드백이 부분 완료 또는 건너뛰기 상태라 해석 신뢰도가 낮습니다."
            )
        if not rpe_values:
            notes.append("RPE 응답이 부족해 평균 체감 강도를 계산하지 못했습니다.")

        intensity_gaps = [
            gap for gap in (self._build_rpe_gap(item) for item in rows) if gap is not None
        ]
        return FeedbackSummary(
            average_rpe=round(sum(rpe_values) / len(rpe_values), 2) if rpe_values else None,
            pain_reports=sum(1 for item in rows if item.pain_report is not None),
            missed_key_sessions=sum(
                1
                for item in rows
                if item.completion == FeedbackCompletion.NONE
                or item.collection_status
                in {FeedbackCollectionStatus.TIMEOUT, FeedbackCollectionStatus.CANCELLED}
            ),
            pace_achievement_rate=None,
            gi_issue_reports=sum(1 for item in rows if item.gi_issues is True),
            completed_feedbacks=completed,
            partial_feedbacks=partial,
            skipped_feedbacks=skipped,
            rpe_intensity_gaps=intensity_gaps,
            notes=notes,
        )

    def _resolve_session_date(
        self,
        existing: SessionFeedback | None,
        feedback: dict[str, Any],
        activity_date: str | None,
    ) -> str:
        candidate = str(
            feedback.get("session_date")
            or activity_date
            or (existing.session_date if existing else "")
        )
        if "T" in candidate:
            return candidate.split("T", 1)[0]
        return candidate or date.today().isoformat()

    def _parse_collection_status(
        self, feedback: dict[str, Any], existing: SessionFeedback | None
    ) -> FeedbackCollectionStatus:
        raw = feedback.get("collection_status")
        if raw is None:
            return existing.collection_status if existing else FeedbackCollectionStatus.COMPLETE
        if isinstance(raw, FeedbackCollectionStatus):
            return raw
        return FeedbackCollectionStatus(str(raw))

    def _parse_completion(
        self, feedback: dict[str, Any], existing: SessionFeedback | None
    ) -> FeedbackCompletion:
        raw = feedback.get("completion")
        if raw is None:
            return existing.completion if existing else FeedbackCompletion.UNKNOWN
        if isinstance(raw, FeedbackCompletion):
            return raw
        return FeedbackCompletion(str(raw))

    def _parse_rpe(self, raw: Any, existing: int | None) -> int | None:
        if raw is None:
            return existing
        if isinstance(raw, int):
            return raw
        text = str(raw).strip()
        if not text:
            return existing
        if "-" in text:
            head = text.split("-", 1)[0]
            return int(head) if head.isdigit() else existing
        return int(text) if text.isdigit() else existing

    def _parse_gi_issues(
        self, feedback: dict[str, Any], existing: SessionFeedback | None
    ) -> bool | None:
        if "gi_issues" in feedback:
            value = feedback.get("gi_issues")
            return bool(value) if value is not None else None
        during = feedback.get("during_nutrition")
        if during == "gi_issue":
            return True
        return existing.gi_issues if existing else None

    def _build_pain_report(
        self, feedback: dict[str, Any], existing: SessionFeedback | None
    ) -> PainReport | None:
        raw = feedback.get("pain_detail")
        if raw is None:
            return replace(existing.pain_report) if existing and existing.pain_report else None
        if not isinstance(raw, dict):
            return None
        return PainReport(
            body_part=str(raw.get("body_part", "other")),
            severity=str(raw.get("severity", "mild")),
            description=str(raw.get("description", "")),
            consecutive_count=0,
        )

    def _merge_keys(
        self,
        existing: list[str],
        explicit: Any,
        feedback: dict[str, Any],
    ) -> list[str]:
        keys = set(existing)
        if isinstance(explicit, list):
            keys.update(str(item) for item in explicit)
        for key in ("rpe", "feeling", "completion", "during_nutrition", "note", "target_pace_met"):
            if feedback.get(key) not in {None, ""}:
                keys.add(key)
        if isinstance(feedback.get("pain_detail"), dict):
            keys.add("pain_detail")
        return sorted(keys)

    def _resolve_pending_keys(
        self, existing: SessionFeedback | None, feedback: dict[str, Any]
    ) -> list[str]:
        explicit = feedback.get("pending_keys")
        if isinstance(explicit, list):
            return [str(item) for item in explicit]
        if existing:
            answered = set(self._merge_keys(existing.answered_keys, None, feedback))
            return [item for item in existing.pending_keys if item not in answered]
        return []

    def _normalize_note(self, raw: Any, existing: str) -> str:
        if raw is None:
            return existing
        text = str(raw).strip()
        if text.lower() in {"", "없음", "none", "skip"}:
            return ""
        return text

    def _pick_value(
        self, feedback: dict[str, Any], key: str, existing: SessionFeedback | None
    ) -> Any:
        if key in feedback:
            return feedback.get(key)
        return getattr(existing, key) if existing else None

    def _consecutive_pain_count(
        self,
        user_id: str,
        activity_id: str,
        body_part: str,
        session_date: str,
    ) -> int:
        count = 1
        rows = self.database.list_feedback(user_id)
        rows.sort(
            key=lambda item: (
                str(item.get("session_date") or ""),
                str(item.get("activity_id") or ""),
            ),
            reverse=True,
        )
        for payload in rows:
            prior = SessionFeedback.from_dict(payload)
            if prior.activity_id == activity_id:
                continue
            if prior.session_date > session_date:
                continue
            if prior.pain_report is None:
                break
            if prior.pain_report.body_part != body_part:
                break
            count += 1
        return count

    def _persist_auto_restrict(self, user_id: str, feedback: SessionFeedback) -> None:
        if self.guardrail_root is None or feedback.pain_report is None:
            return
        if feedback.pain_report.consecutive_count < 2:
            return
        self.guardrail_root.mkdir(parents=True, exist_ok=True)
        restricted = ["hard"]
        if feedback.pain_report.severity in {"moderate", "severe"}:
            restricted = ["hard", "interval", "tempo"]
        payload = {
            "body_part": feedback.pain_report.body_part,
            "severity": feedback.pain_report.severity,
            "restricted_session_types": restricted,
            "pain_reports_count": feedback.pain_report.consecutive_count,
            "updated_at": feedback.updated_at,
        }
        (self.guardrail_root / f"{user_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2)
        )

    def _build_rpe_gap(self, feedback: SessionFeedback) -> RPEIntensityGap | None:
        if feedback.rpe is None:
            return None
        significance = "high" if feedback.rpe >= 8 else "normal"
        direction = "harder_than_expected" if feedback.rpe >= 8 else "match"
        return RPEIntensityGap(
            rpe=feedback.rpe,
            expected_rpe_range=(4, 7),
            gap_direction=direction,
            significance=significance,
        )
