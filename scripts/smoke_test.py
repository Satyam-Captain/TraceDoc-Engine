#!/usr/bin/env python3
"""Repeatable local smoke test for TraceDoc Engine demo readiness."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline import process_document
from app.qa import ask_document

DB_PATH = PROJECT_ROOT / "data" / "demo_tracedoc.db"
SAMPLES = {
    "hpc6_policy.txt": PROJECT_ROOT / "samples" / "hpc6_policy.txt",
    "requirements_sample.txt": PROJECT_ROOT / "samples" / "requirements_sample.txt",
}

QUESTIONS = (
    {
        "document_key": "hpc6_policy.txt",
        "question": "What is HPC6 memory policy?",
    },
    {
        "document_key": "hpc6_policy.txt",
        "question": "Where is CPU binding mentioned?",
    },
    {
        "document_key": "requirements_sample.txt",
        "question": "What is REQ-001?",
    },
    {
        "document_key": "hpc6_policy.txt",
        "question": "List all storage rules",
    },
)


def run_pytest() -> None:
    print("Running unit tests...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("pytest failed")


def process_samples() -> dict[str, int]:
    if DB_PATH.exists():
        DB_PATH.unlink()

    document_ids: dict[str, int] = {}
    print("\nProcessing sample documents...")
    for name, path in SAMPLES.items():
        processed = process_document(str(path), db_path=str(DB_PATH))
        document_ids[name] = processed.document_id
        print(
            f"  - {name}: id={processed.document_id}, "
            f"sections={processed.section_count}, "
            f"chunks={processed.chunk_count}, "
            f"terms={processed.indexed_term_count}, "
            f"duplicate={processed.duplicate}"
        )
        if processed.warnings:
            print(f"    warnings: {processed.warnings}")
    return document_ids


def run_questions(document_ids: dict[str, int]) -> None:
    print("\nAsking demo questions...")
    for item in QUESTIONS:
        document_id = document_ids[item["document_key"]]
        answer = ask_document(
            item["question"],
            document_id,
            db_path=str(DB_PATH),
            top_k=5,
            max_cards=3,
        )

        print(f"\nQ: {item['question']}")
        print(f"  answer_mode: {answer.answer_mode}")
        if answer.query_intent is not None:
            print(f"  intent: {answer.query_intent.intent_type}")

        if answer.answer_mode != "EVIDENCE_ONLY" or not answer.cards:
            raise RuntimeError(
                f"No evidence found for question: {item['question']!r}"
            )

        top_card = answer.cards[0]
        snippet_preview = (
            top_card.snippet.replace("[[", "").replace("]]", "")[:160]
        )
        print(f"  top_citation: {top_card.citation}")
        print(f"  confidence: {top_card.confidence}")
        print(f"  score: {top_card.score:.4f}")
        print(f"  snippet_preview: {snippet_preview}...")


def main() -> int:
    print("TraceDoc Engine smoke test")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Database: {DB_PATH}")

    try:
        run_pytest()
        document_ids = process_samples()
        run_questions(document_ids)
    except Exception as error:
        print(f"\nSmoke test FAILED: {error}", file=sys.stderr)
        return 1

    print("\nSmoke test PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
