#!/usr/bin/env python3
"""Run the deterministic TraceDoc QA evaluation benchmark."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.eval.runner import format_results_table, format_summary, run_benchmark


def main() -> int:
    eval_root = Path(__file__).resolve().parent
    db_path = eval_root / "benchmark.db"

    print("TraceDoc QA evaluation benchmark")
    print(f"Eval root: {eval_root}")
    print(f"Database: {db_path}\n")

    report = run_benchmark(eval_root=eval_root, db_path=db_path)

    print(format_results_table(report))
    print()
    print(format_summary(report))

    if report.success:
        print("\nBenchmark PASSED")
        return 0

    print("\nBenchmark FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
