from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
QA_DIR = REPO_ROOT / "docs" / "qa"
MATRIX_PATH = QA_DIR / "prd-acceptance-matrix.yaml"
RUNBOOK_PATH = QA_DIR / "manual-verification-runbook.md"


def _load_matrix() -> dict:
    return yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))


def test_prd_acceptance_matrix_exists() -> None:
    assert MATRIX_PATH.exists()
    assert RUNBOOK_PATH.exists()


def test_prd_acceptance_matrix_has_all_streams_and_required_fields() -> None:
    matrix = _load_matrix()
    cases = matrix["cases"]
    assert cases

    streams = {case["stream"] for case in cases}
    assert streams == {1, 2, 3, 4, 5}

    required_fields = {
        "id",
        "stream",
        "prd_section",
        "title",
        "expected_outcome",
        "automated_tests",
        "manual_qa",
    }
    for case in cases:
        assert required_fields.issubset(case.keys())
        assert case["id"].startswith("prd-s")
        assert str(case["expected_outcome"]).strip()


def test_every_prd_case_has_verification_target() -> None:
    matrix = _load_matrix()
    manual_ids = {entry["id"] for entry in matrix["manual_qa_cases"]}

    for case in matrix["cases"]:
        automated_tests = case["automated_tests"]
        manual_cases = case["manual_qa"]
        assert automated_tests or manual_cases

        for test_path in automated_tests:
            assert (REPO_ROOT / test_path).exists(), test_path
        for manual_id in manual_cases:
            assert manual_id in manual_ids, manual_id


def test_prd_matrix_covers_key_behavior_classes() -> None:
    matrix = _load_matrix()
    ids = {case["id"] for case in matrix["cases"]}

    expected = {
        "prd-s1-guardrail-overtraining",
        "prd-s1-guardrail-injury-bodypart",
        "prd-s1-readiness-thresholds",
        "prd-s2-flow-isolation",
        "prd-s2-telegram-runtime",
        "prd-s2-post-workout-trigger",
        "prd-s3-phase1-immediate-value",
        "prd-s3-rehab-branching",
        "prd-s3-timeout-explicit",
        "prd-s4-periodized-macros",
        "prd-s4-low-confidence-photo",
        "prd-s4-allergy-filtering",
        "prd-s5-feedback-dedup",
        "prd-s5-partial-feedback-resume",
        "prd-s5-report-determinism",
        "prd-s5-workout-food-photo-separation",
    }

    assert expected.issubset(ids)


def test_manual_runbook_contains_all_manual_case_ids() -> None:
    matrix = _load_matrix()
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
    for entry in matrix["manual_qa_cases"]:
        assert entry["id"] in runbook
