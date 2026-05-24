"""Tests for deterministic QA evaluation runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.eval.models import BenchmarkCase
from app.eval.runner import (
    evaluate_case,
    load_benchmark_suite,
    run_benchmark,
)
from app.evidence.models import ANSWER_MODE_EVIDENCE_ONLY
from app.qa import DocumentQAResult

EVAL_ROOT = Path(__file__).resolve().parent.parent / "eval"


def test_load_benchmark_suite() -> None:
    suite = load_benchmark_suite(EVAL_ROOT / "questions.yaml")
    assert suite.document_name == "symbolic_architecture_doc.txt"
    assert len(suite.cases) >= 5


def test_benchmark_passes_end_to_end(tmp_path: Path) -> None:
    db_path = tmp_path / "eval.db"
    report = run_benchmark(eval_root=EVAL_ROOT, db_path=db_path)
    assert report.total_cases > 0
    assert report.failed_cases == 0, report.case_results
    assert report.answer_mode_accuracy == 1.0
    assert report.contains_pass_rate == 1.0
    assert report.not_contains_violations == 0


def test_evaluate_case_detects_failures() -> None:
    case = BenchmarkCase(
        case_id="fake",
        question="test",
        expected_answer_mode=ANSWER_MODE_EVIDENCE_ONLY,
        expected_contains=["missing phrase"],
    )
    answer = DocumentQAResult(
        question="test",
        document_id=1,
        document_name="doc.txt",
        answer_mode=ANSWER_MODE_EVIDENCE_ONLY,
        cards=[],
        structured_answer=None,
    )
    result = evaluate_case(case, answer)
    assert not result.passed
    assert result.failures


def test_wrong_mode_fails_evaluation() -> None:
    suite = load_benchmark_suite(EVAL_ROOT / "questions.yaml")
    case = suite.cases[0]
    answer = DocumentQAResult(
        question=case.question,
        document_id=1,
        document_name="doc.txt",
        answer_mode="NO_EVIDENCE",
        cards=[],
    )
    result = evaluate_case(case, answer)
    assert not result.passed
