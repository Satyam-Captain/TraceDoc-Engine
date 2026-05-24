"""Tests for deterministic symbolic relationship inference."""

from __future__ import annotations

from pathlib import Path

from app.evidence.models import ANSWER_MODE_STRUCTURED_EXTRACTIVE, EvidenceCard
from app.evidence.pattern_extractor import (
    INFERENCE_SYMBOLIC,
    extract_enumerated_phrases,
    extract_enumerated_phrases_with_trace,
)
from app.evidence.sentence_splitter import split_sentences
from app.evidence.structured_composer import compose_structured_answer
from app.evidence.symbolic_inference import infer_symbolic_relationships
from app.pipeline import process_document
from app.qa import RETRIEVAL_STRATEGY_SECTION, ask_document

OPEN_EPHYRA_SENTENCE = (
    "OpenEphyra embodied a modular implementation with question analysis, "
    "query generation, search, and answer extraction/selection."
)

COREFERENCE_SENTENCE = (
    "If your stakeholder says 'no AI', this pipeline is still the "
    "cleanest conceptual answer for many teaching examples."
)

REAL_PDF_SECTION = (
    "The most common pre-generative architecture is the enterprise search stack: "
    "repository connectors ingest content, normalize text, and feed search indexes. "
    f"{OPEN_EPHYRA_SENTENCE} "
    f"{COREFERENCE_SENTENCE} "
    "A third architecture is the ontology and knowledge-graph stack. "
    "A fourth architecture is the traceability and citation graph."
)

QUESTION = "what are different architectures mentioned in the pdf?"


def test_open_ephyra_sentence_infers_classic_qa_pipeline() -> None:
    sentences = split_sentences(OPEN_EPHYRA_SENTENCE)
    inferred = infer_symbolic_relationships(sentences, "architecture")

    assert len(inferred) == 1
    assert inferred[0].value == "Classic QA pipeline"
    assert inferred[0].pattern_name == "open_ephyra_pipeline_inference"
    assert inferred[0].inference_type == INFERENCE_SYMBOLIC


def test_coreference_resolves_to_pipeline_context() -> None:
    sentences = split_sentences(f"{OPEN_EPHYRA_SENTENCE} {COREFERENCE_SENTENCE}")
    inferred = infer_symbolic_relationships(sentences, "architecture")

    assert any(entry.value == "Classic QA pipeline" for entry in inferred)
    assert any(
        entry.pattern_name == "open_ephyra_pipeline_inference" for entry in inferred
    )


def test_unrelated_sentence_does_not_infer_architecture() -> None:
    sentences = split_sentences("The weather is sunny and unrelated to systems design.")
    assert infer_symbolic_relationships(sentences, "architecture") == []


def test_symbolic_inference_skips_explicit_duplicate() -> None:
    sentences = split_sentences(OPEN_EPHYRA_SENTENCE)
    existing = frozenset({"classic qa pipeline"})
    assert infer_symbolic_relationships(
        sentences,
        "architecture",
        existing_values=existing,
    ) == []


def test_real_section_extracts_all_four_via_symbolic_and_explicit() -> None:
    phrases = extract_enumerated_phrases(REAL_PDF_SECTION, "architecture")
    assert phrases == [
        "Enterprise search stack",
        "Classic QA pipeline",
        "Ontology and knowledge-graph stack",
        "Traceability and citation graph",
    ]


def test_end_to_end_includes_symbolic_debug_trace(tmp_path: Path) -> None:
    source = tmp_path / "arch_symbolic.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(f"# Existing architectures\n\n{REAL_PDF_SECTION}", encoding="utf-8")

    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(QUESTION, processed.document_id, db_path=str(db_path))

    assert answer.retrieval_strategy == RETRIEVAL_STRATEGY_SECTION
    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    assert answer.structured_answer is not None
    assert "1. Enterprise search stack" in answer.structured_answer
    assert "2. Classic QA pipeline" in answer.structured_answer
    assert "3. Ontology and knowledge-graph stack" in answer.structured_answer
    assert "4. Traceability and citation graph" in answer.structured_answer
    trace_text = "\n".join(answer.debug_trace)
    assert "inference=open_ephyra_pipeline_inference" in trace_text


def test_compose_structured_answer_with_symbolic_inference() -> None:
    card = EvidenceCard(
        chunk_id="c1",
        document_name="arch.pdf",
        section_title="Existing architectures",
        start_line=1,
        end_line=20,
        snippet=REAL_PDF_SECTION,
        matched_terms=["architecture"],
        score=3.0,
        confidence="HIGH",
        why_matched="section-level retrieval",
        citation="arch.pdf | lines 1-20",
    )
    answer = compose_structured_answer(QUESTION, [card])
    entries = extract_enumerated_phrases_with_trace(
        "\n".join(split_sentences(REAL_PDF_SECTION)),
        "architecture",
    )

    assert answer is not None
    assert any(
        entry.inference_type == INFERENCE_SYMBOLIC
        and entry.pattern_name == "open_ephyra_pipeline_inference"
        for entry in entries
    )
