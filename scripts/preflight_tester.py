#!/usr/bin/env python3
"""
Preflight tester — predict structure/QA readiness before Streamlit upload.

Usage:
  python scripts/preflight_tester.py path/to/document.pdf
  TRACEDOC_EXTRACTOR=v2 python scripts/preflight_tester.py samples/foo.pdf

Does not require Streamlit or a populated DB for structure checks.
Optional --process runs full pipeline into a temp DB and samples one question.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAMPLE_QUESTIONS = [
    (
        "what are different architectures mentioned in the pdf?",
        "STRUCTURED_EXTRACTIVE",
        "Existing architectures",
    ),
    (
        "what are different design patterns mentioned in the pdf?",
        "STRUCTURED_EXTRACTIVE",
        "Design patterns",
    ),
    (
        "What does Enterprise search stack use?",
        "GRAPH_STRUCTURED",
        None,
    ),
]


def _gate(
    *,
    text_len: int,
    section_count: int,
    isolated_heading_lines: int,
    extraction_ok: bool,
) -> str:
    if not extraction_ok or text_len < 80:
        return "RED - NOT_READY"
    if section_count < 2 or isolated_heading_lines == 0:
        return "YELLOW - STRUCTURE_WEAK"
    if section_count >= 4 and isolated_heading_lines >= 2:
        return "GREEN+ - READY_FOR_EVAL"
    return "GREEN - READY_FOR_QA"


def _count_isolated_heading_candidates(lines: list[str]) -> int:
    from app.structure.detector import _match_heading

    count = 0
    for i, line in enumerate(lines):
        prev = lines[i - 1] if i > 0 else None
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if _match_heading(line, previous_line=prev, next_line=nxt) is not None:
            count += 1
    return count


def _predict_questions(sections: list, gate: str) -> None:
    titles = [s.title for s in sections]
    titles_lower = [t.lower() for t in titles]

    print("\n--- Likely UI outcomes (heuristic, not executed) ---")
    if gate.startswith("RED"):
        print("  All questions → likely NO_EVIDENCE or processing error. Fix extraction first.")
        return
    if gate.startswith("YELLOW"):
        print("  List/architecture questions → likely EVIDENCE_ONLY or wrong section.")
        print("  Factoid questions → may work via BM25_CHUNK only.")
        return

    for question, expected_mode, section_hint in SAMPLE_QUESTIONS:
        section_match = None
        if section_hint:
            for t in titles:
                if section_hint.lower() in t.lower():
                    section_match = t
                    break
        if section_match:
            pred_mode = expected_mode
            pred_strategy = "SECTION_LEVEL"
            pred_section = section_match
        elif "enterprise" in question.lower() and any(
            "architecture" in t for t in titles_lower
        ):
            pred_mode = expected_mode
            pred_strategy = "BM25_CHUNK or GRAPH"
            pred_section = "(graph if entities indexed)"
        else:
            pred_mode = "EVIDENCE_ONLY or NO_EVIDENCE"
            pred_strategy = "BM25_CHUNK"
            pred_section = "(none)"

        print(f"  Q: {question}")
        print(f"     predicted_mode~{pred_mode}  strategy~{pred_strategy}")
        print(f"     predicted_section~{pred_section}")
    print("\n  Run Streamlit only after GREEN gate unless intentionally testing failure.")


def run_preflight(file_path: str, *, run_process: bool) -> int:
    extractor = os.environ.get("TRACEDOC_EXTRACTOR", "v1").lower()
    retrieval = os.environ.get("TRACEDOC_RETRIEVAL", "sqlite").lower()
    extraction = os.environ.get("TRACEDOC_EXTRACTION", "grammar").lower()

    print("=" * 60)
    print("TraceDoc preflight")
    print("=" * 60)
    print(f"  file:       {file_path}")
    print(f"  extractor:  {extractor}")
    print(f"  retrieval:  {retrieval}")
    print(f"  extraction: {extraction}")

    path = Path(file_path)
    if not path.is_file():
        print(f"\nERROR: file not found: {file_path}")
        return 2

    extraction_ok = True
    try:
        from app.ingestion import extract_document
        from app.structure import structure_document

        result = extract_document(str(path))
        text = result.text or ""
        sections, chunks = structure_document(result.file_name, text)
    except Exception as error:
        extraction_ok = False
        text = ""
        sections = []
        chunks = []
        print(f"\nERROR during extract/structure: {error}")

    lines = text.split("\n")
    isolated = _count_isolated_heading_candidates(lines) if text else 0
    gate = _gate(
        text_len=len(text),
        section_count=len(sections),
        isolated_heading_lines=isolated,
        extraction_ok=extraction_ok,
    )

    print("\n--- Extraction ---")
    if extraction_ok:
        print(f"  checksum:   {result.checksum_sha256[:16]}...")
        print(f"  chars:      {len(text)}")
        print(f"  lines:      {len(lines)}")
        print(f"  warnings:   {result.extraction_warnings or '(none)'}")
        meta = getattr(result, "metadata", {}) or {}
        if meta.get("extractor_version"):
            print(f"  extractor_version metadata: {meta.get('extractor_version')}")
    print(f"  heading lines detected: {isolated}")

    print("\n--- Structure ---")
    print(f"  sections:   {len(sections)}")
    print(f"  chunks:     {len(chunks)}")
    for sec in sections[:12]:
        print(f"    - [{sec.level}] {sec.title} (lines {sec.start_line}-{sec.end_line})")
    if len(sections) > 12:
        print(f"    ... +{len(sections) - 12} more")

    print(f"\n--- GATE: {gate} ---")

    _predict_questions(sections, gate)

    if run_process and gate.startswith("GREEN"):
        print("\n--- Live pipeline sample (temp DB) ---")
        try:
            from app.pipeline import process_document
            from app.qa import ask_document

            with tempfile.TemporaryDirectory() as tmp:
                db = Path(tmp) / "preflight.db"
                processed = process_document(str(path), db_path=str(db))
                print(f"  document_id: {processed.document_id}")
                print(f"  sections:    {processed.section_count}")
                print(f"  chunks:      {processed.chunk_count}")
                q = SAMPLE_QUESTIONS[0][0]
                answer = ask_document(
                    processed.document_id, q, db_path=str(db)
                )
                print(f"  sample Q: {q}")
                print(f"  answer_mode: {answer.answer_mode}")
                print(f"  strategy:    {answer.retrieval_strategy}")
                print(f"  section:     {answer.retrieved_section_title}")
                if answer.structured_answer:
                    preview = answer.structured_answer[:300].replace("\n", " ")
                    print(f"  structured:    {preview}...")
        except Exception as error:
            print(f"  pipeline sample failed: {error}")

    print("\n--- When to test ---")
    if gate.startswith("RED"):
        print("  NOW: No UI. Update TEST_RESULTS.md and wait for coder P1.")
        return 1
    if gate.startswith("YELLOW"):
        print("  NOW: Preflight only; optional UI for debugging. Fix P1/P2 first.")
        return 1
    print("  NOW: OK for Streamlit upload + questions in TESTER_GUIDE.md")
    if extractor == "v1":
        print("  TIP:  Re-run with TRACEDOC_EXTRACTOR=v2 after coder finishes P1.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="TraceDoc document preflight")
    parser.add_argument("file_path", help="PDF, DOCX, or TXT to analyze")
    parser.add_argument(
        "--process",
        action="store_true",
        help="Run full process_document + one sample question (GREEN only)",
    )
    args = parser.parse_args()
    raise SystemExit(run_preflight(args.file_path, run_process=args.process))


if __name__ == "__main__":
    main()
