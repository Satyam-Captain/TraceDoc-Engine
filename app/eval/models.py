"""Data models for deterministic QA evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BenchmarkCase:
    """One benchmark question with expected outcomes."""

    case_id: str
    question: str
    expected_answer_mode: str
    expected_contains: list[str] = field(default_factory=list)
    expected_not_contains: list[str] = field(default_factory=list)
    expected_retrieval_strategy: str | None = None
    expected_section: str | None = None


@dataclass
class BenchmarkSuite:
    """Benchmark document plus question cases."""

    document_name: str
    cases: list[BenchmarkCase]


@dataclass
class CaseCheckResult:
    """Outcome of one assertion for a benchmark case."""

    name: str
    passed: bool
    detail: str = ""


@dataclass
class CaseEvalResult:
    """Evaluation result for one benchmark case."""

    case_id: str
    question: str
    passed: bool
    actual_answer_mode: str
    actual_retrieval_strategy: str
    actual_section: str | None
    checks: list[CaseCheckResult] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    """Aggregate evaluation report."""

    total_cases: int
    passed_cases: int
    failed_cases: int
    case_results: list[CaseEvalResult] = field(default_factory=list)
    answer_mode_accuracy: float = 0.0
    contains_pass_rate: float = 0.0
    not_contains_violations: int = 0

    @property
    def success(self) -> bool:
        return self.failed_cases == 0
