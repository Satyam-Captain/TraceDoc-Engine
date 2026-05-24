"""Run deterministic QA benchmark suites."""

from __future__ import annotations

import json
from pathlib import Path

from app.eval.metrics import summarize_results
from app.eval.models import (
    BenchmarkCase,
    BenchmarkSuite,
    CaseCheckResult,
    CaseEvalResult,
    EvalReport,
)
from app.pipeline import process_document
from app.qa import DocumentQAResult, ask_document


def _load_yaml_minimal(text: str) -> dict:
    """Parse a minimal subset of YAML used by questions.yaml without PyYAML."""
    root: dict = {}
    current_list_key: str | None = None
    current_case: dict | None = None
    current_nested_list: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if not line.startswith((" ", "\t")) and ":" in stripped and not stripped.startswith("- "):
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value:
                root[key] = value
                current_list_key = None
                current_case = None
                current_nested_list = None
            elif key == "cases":
                root["cases"] = []
                current_list_key = "cases"
                current_case = None
                current_nested_list = None
            continue

        if stripped == "cases:":
            root["cases"] = []
            current_list_key = "cases"
            current_case = None
            current_nested_list = None
            continue

        if stripped.startswith("- id:") or stripped.startswith("- id:"):
            if current_list_key == "cases":
                current_case = {"id": stripped.split(":", 1)[1].strip()}
                root["cases"].append(current_case)
                current_nested_list = None
            continue

        if current_case is not None and line.startswith("      - "):
            item = stripped[2:].strip().strip('"').strip("'")
            if current_nested_list and isinstance(current_case.get(current_nested_list), list):
                current_case[current_nested_list].append(item)
            continue

        if current_case is not None and line.startswith("    ") and ":" in stripped:
            if stripped.startswith("- "):
                continue
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value:
                current_case[key] = value
                current_nested_list = None
            else:
                current_case[key] = []
                current_nested_list = key
            continue

    return root


def load_benchmark_suite(questions_path: Path) -> BenchmarkSuite:
    """Load benchmark cases from questions.yaml."""
    raw = questions_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(raw)
    except ImportError:
        data = _load_yaml_minimal(raw)

    if not isinstance(data, dict):
        raise ValueError("questions.yaml must define a mapping at the top level")

    document_name = str(data.get("document", "")).strip()
    cases: list[BenchmarkCase] = []
    for entry in data.get("cases", []):
        if not isinstance(entry, dict):
            continue
        cases.append(
            BenchmarkCase(
                case_id=str(entry.get("id", entry.get("case_id", ""))),
                question=str(entry["question"]),
                expected_answer_mode=str(entry["expected_answer_mode"]),
                expected_contains=list(entry.get("expected_contains", []) or []),
                expected_not_contains=list(entry.get("expected_not_contains", []) or []),
                expected_retrieval_strategy=entry.get("expected_retrieval_strategy"),
                expected_section=entry.get("expected_section"),
            )
        )
    if not document_name or not cases:
        raise ValueError("questions.yaml must define document and at least one case")
    return BenchmarkSuite(document_name=document_name, cases=cases)


def answer_text(answer: DocumentQAResult) -> str:
    """Merge structured answer and evidence snippets for substring checks."""
    parts: list[str] = []
    if answer.structured_answer:
        parts.append(answer.structured_answer)
    for card in answer.cards:
        parts.append(card.snippet.replace("[[", "").replace("]]", ""))
    return "\n".join(parts).lower()


def evaluate_case(case: BenchmarkCase, answer: DocumentQAResult) -> CaseEvalResult:
    """Compare one QA result against benchmark expectations."""
    checks: list[CaseCheckResult] = []
    failures: list[str] = []
    text = answer_text(answer)

    mode_ok = answer.answer_mode == case.expected_answer_mode
    checks.append(
        CaseCheckResult(
            name="answer_mode",
            passed=mode_ok,
            detail=f"expected={case.expected_answer_mode} actual={answer.answer_mode}",
        )
    )
    if not mode_ok:
        failures.append(
            f"answer_mode expected {case.expected_answer_mode}, got {answer.answer_mode}"
        )

    if case.expected_retrieval_strategy:
        strategy_ok = (
            answer.retrieval_strategy == case.expected_retrieval_strategy
        )
        checks.append(
            CaseCheckResult(
                name="retrieval_strategy",
                passed=strategy_ok,
                detail=(
                    f"expected={case.expected_retrieval_strategy} "
                    f"actual={answer.retrieval_strategy}"
                ),
            )
        )
        if not strategy_ok:
            failures.append(
                "retrieval_strategy expected "
                f"{case.expected_retrieval_strategy}, got {answer.retrieval_strategy}"
            )

    if case.expected_section:
        section_ok = (answer.retrieved_section_title or "").strip().lower() == (
            case.expected_section.strip().lower()
        )
        checks.append(
            CaseCheckResult(
                name="section",
                passed=section_ok,
                detail=(
                    f"expected={case.expected_section!r} "
                    f"actual={answer.retrieved_section_title!r}"
                ),
            )
        )
        if not section_ok:
            failures.append(
                f"section expected {case.expected_section!r}, "
                f"got {answer.retrieved_section_title!r}"
            )

    for phrase in case.expected_contains:
        found = phrase.lower() in text
        checks.append(
            CaseCheckResult(
                name=f"contains:{phrase}",
                passed=found,
                detail="found" if found else "missing",
            )
        )
        if not found:
            failures.append(f"missing expected phrase: {phrase!r}")

    for phrase in case.expected_not_contains:
        absent = phrase.lower() not in text
        checks.append(
            CaseCheckResult(
                name=f"not_contains:{phrase}",
                passed=absent,
                detail="absent" if absent else "present",
            )
        )
        if not absent:
            failures.append(f"unexpected phrase present: {phrase!r}")

    return CaseEvalResult(
        case_id=case.case_id,
        question=case.question,
        passed=not failures,
        actual_answer_mode=answer.answer_mode,
        actual_retrieval_strategy=answer.retrieval_strategy,
        actual_section=answer.retrieved_section_title,
        checks=checks,
        failures=failures,
    )


def run_benchmark(
    *,
    eval_root: Path,
    db_path: Path,
    questions_file: str = "questions.yaml",
) -> EvalReport:
    """
    Process benchmark document(s) and evaluate all configured questions.

    Creates or reuses a SQLite database at db_path.
    """
    eval_root = eval_root.resolve()
    questions_path = eval_root / questions_file
    suite = load_benchmark_suite(questions_path)

    doc_path = eval_root / "benchmark_docs" / suite.document_name
    if not doc_path.is_file():
        raise FileNotFoundError(f"Benchmark document not found: {doc_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    processed = process_document(str(doc_path), db_path=str(db_path))
    document_id = processed.document_id

    case_results: list[CaseEvalResult] = []
    for case in suite.cases:
        answer = ask_document(
            case.question,
            document_id,
            db_path=str(db_path),
        )
        case_results.append(evaluate_case(case, answer))

    return summarize_results(case_results)


def format_results_table(report: EvalReport) -> str:
    """Render a PASS/FAIL table for console output."""
    headers = ("CASE", "STATUS", "MODE", "STRATEGY", "SECTION", "FAILURES")
    rows: list[tuple[str, ...]] = []
    for result in report.case_results:
        rows.append(
            (
                result.case_id,
                "PASS" if result.passed else "FAIL",
                result.actual_answer_mode,
                result.actual_retrieval_strategy,
                result.actual_section or "",
                "; ".join(result.failures) if result.failures else "",
            )
        )

    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    lines = [
        " | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        "-+-".join("-" * widths[index] for index in range(len(headers))),
    ]
    for row in rows:
        lines.append(
            " | ".join(row[index].ljust(widths[index]) for index in range(len(headers)))
        )
    return "\n".join(lines)


def format_summary(report: EvalReport) -> str:
    """Render aggregate metrics."""
    return (
        f"total_cases={report.total_cases}\n"
        f"passed={report.passed_cases}\n"
        f"failed={report.failed_cases}\n"
        f"answer_mode_accuracy={report.answer_mode_accuracy:.2%}\n"
        f"contains_pass_rate={report.contains_pass_rate:.2%}\n"
        f"not_contains_violations={report.not_contains_violations}"
    )


def report_to_json(report: EvalReport) -> str:
    """Serialize report for machine-readable output."""
    payload = {
        "total_cases": report.total_cases,
        "passed_cases": report.passed_cases,
        "failed_cases": report.failed_cases,
        "answer_mode_accuracy": report.answer_mode_accuracy,
        "contains_pass_rate": report.contains_pass_rate,
        "not_contains_violations": report.not_contains_violations,
        "success": report.success,
        "cases": [
            {
                "case_id": result.case_id,
                "passed": result.passed,
                "actual_answer_mode": result.actual_answer_mode,
                "actual_retrieval_strategy": result.actual_retrieval_strategy,
                "actual_section": result.actual_section,
                "failures": result.failures,
            }
            for result in report.case_results
        ],
    }
    return json.dumps(payload, indent=2)
