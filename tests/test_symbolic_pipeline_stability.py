"""End-to-end stability tests for the symbolic QA pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evidence.models import ANSWER_MODE_STRUCTURED_EXTRACTIVE
from app.pipeline import process_document
from app.qa import RETRIEVAL_STRATEGY_SECTION, ask_document
from app.structure import structure_document

STABILITY_DOCUMENT = (
    "Existing architectures\n"
    "The most common pre-generative architecture is the enterprise search stack.\n"
    "OpenEphyra embodied a modular implementation with question analysis, query generation, "
    "search, and answer extraction/selection.\n"
    "A third architecture is the ontology and knowledge-graph stack.\n"
    "A fourth architecture is the traceability and citation graph.\n"
    "\n"
    "Design patterns for implementation\n"
    "The first critical design pattern is section-aware ingestion.\n"
    "The second pattern is multi-granular indexing.\n"
    "The third pattern is deterministic query interpretation.\n"
    "The fourth pattern is citation-first answer composition.\n"
    "The fifth pattern is symbolic enrichment.\n"
    "The sixth pattern is security and audit by design.\n"
    "\n"
    "Open-source building blocks\n"
    "For ingestion, the most useful tools are Apache Tika and Apache PDFBox.\n"
    "For retrieval, the core building blocks are Lucene, Solr, and OpenSearch.\n"
)

ARCHITECTURE_QUESTION = "what are different architectures mentioned in the pdf?"
DESIGN_PATTERN_QUESTION = "what are different design pattern mentioned in the pdf?"

ARCHITECTURE_ENTITIES = (
    "Enterprise search stack",
    "Ontology and knowledge-graph stack",
    "Traceability and citation graph",
)

DESIGN_PATTERN_ENTITIES = (
    "Section-aware ingestion",
    "Multi-granular indexing",
    "Deterministic query interpretation",
    "Citation-first answer composition",
    "Symbolic enrichment",
    "Security and audit by design",
)

ARCHITECTURE_FORBIDDEN_IN_DESIGN = (
    "classic qa pipeline",
    "enterprise search stack",
    "ontology and knowledge-graph stack",
    "traceability and citation graph",
)

DESIGN_FORBIDDEN_IN_ARCHITECTURE = (
    "multi-granular indexing",
    "citation-first answer composition",
    "symbolic enrichment",
    "section-aware ingestion",
)


@pytest.fixture
def stability_db(tmp_path: Path) -> tuple[Path, int]:
    source = tmp_path / "symbolic_stability.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(STABILITY_DOCUMENT, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))
    return db_path, processed.document_id


def _answer_body(answer: str | None) -> str:
    assert answer is not None
    return answer.split("Supporting evidence:")[0].lower()


def test_architecture_question_section_and_entities(stability_db: tuple[Path, int]) -> None:
    db_path, document_id = stability_db
    answer = ask_document(ARCHITECTURE_QUESTION, document_id, db_path=str(db_path))

    assert answer.retrieval_strategy == RETRIEVAL_STRATEGY_SECTION
    assert answer.retrieved_section_title == "Existing architectures"
    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    body = _answer_body(answer.structured_answer)
    assert "enterprise search stack" in body
    for forbidden in DESIGN_FORBIDDEN_IN_ARCHITECTURE:
        assert forbidden not in body

    trace = "\n".join(answer.debug_trace)
    assert "target_category=architecture" in trace


def test_design_pattern_question_section_and_entities(stability_db: tuple[Path, int]) -> None:
    db_path, document_id = stability_db
    answer = ask_document(DESIGN_PATTERN_QUESTION, document_id, db_path=str(db_path))

    assert answer.retrieval_strategy == RETRIEVAL_STRATEGY_SECTION
    assert answer.retrieved_section_title == "Design patterns for implementation"
    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    body = _answer_body(answer.structured_answer)
    for entity in DESIGN_PATTERN_ENTITIES:
        assert entity.lower() in body
    for forbidden in ARCHITECTURE_FORBIDDEN_IN_DESIGN:
        assert forbidden not in body

    trace = "\n".join(answer.debug_trace)
    assert "target_category=design_pattern" in trace


def test_evidence_cards_match_retrieved_section(stability_db: tuple[Path, int]) -> None:
    db_path, document_id = stability_db
    answer = ask_document(DESIGN_PATTERN_QUESTION, document_id, db_path=str(db_path))

    assert answer.retrieved_section_title == "Design patterns for implementation"
    for card in answer.cards:
        assert card.section_title == answer.retrieved_section_title


def test_design_pattern_chunks_inside_section_range() -> None:
    sections, chunks = structure_document("stability.txt", STABILITY_DOCUMENT)
    design = next(s for s in sections if s.title == "Design patterns for implementation")
    design_chunks = [
        c
        for c in chunks
        if c.chunk_type != "section"
        and c.section_title == "Design patterns for implementation"
    ]
    assert design_chunks
    for chunk in design_chunks:
        assert design.start_line <= chunk.start_line <= design.end_line
        assert chunk.end_line <= design.end_line


def test_chunk_section_titles_align_with_inferred_ranges() -> None:
    sections, chunks = structure_document("stability.txt", STABILITY_DOCUMENT)
    arch = next(s for s in sections if s.title == "Existing architectures")
    arch_chunks = [
        c for c in chunks if c.chunk_type != "section" and "architecture" in (c.section_title or "").lower()
    ]
    for chunk in arch_chunks:
        assert arch.start_line <= chunk.start_line <= arch.end_line
