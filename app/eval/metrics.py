"""Aggregate metrics for QA evaluation reports."""

from __future__ import annotations

from app.eval.models import CaseEvalResult, EvalReport


def summarize_results(case_results: list[CaseEvalResult]) -> EvalReport:
    """Compute aggregate metrics from per-case evaluation results."""
    total = len(case_results)
    passed_cases = sum(1 for result in case_results if result.passed)
    failed_cases = total - passed_cases

    mode_checks = [
        check
        for result in case_results
        for check in result.checks
        if check.name == "answer_mode"
    ]
    contains_checks = [
        check
        for result in case_results
        for check in result.checks
        if check.name.startswith("contains:")
    ]
    not_contains_checks = [
        check
        for result in case_results
        for check in result.checks
        if check.name.startswith("not_contains:")
    ]

    answer_mode_accuracy = (
        sum(1 for check in mode_checks if check.passed) / len(mode_checks)
        if mode_checks
        else 1.0
    )
    contains_pass_rate = (
        sum(1 for check in contains_checks if check.passed) / len(contains_checks)
        if contains_checks
        else 1.0
    )
    not_contains_violations = sum(
        1 for check in not_contains_checks if not check.passed
    )

    return EvalReport(
        total_cases=total,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        case_results=case_results,
        answer_mode_accuracy=answer_mode_accuracy,
        contains_pass_rate=contains_pass_rate,
        not_contains_violations=not_contains_violations,
    )
