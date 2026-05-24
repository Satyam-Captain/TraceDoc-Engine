"""Tests for deterministic structured extractive answers."""

from __future__ import annotations

from pathlib import Path

from app.evidence.models import (
    ANSWER_MODE_EVIDENCE_ONLY,
    ANSWER_MODE_NO_EVIDENCE,
    ANSWER_MODE_STRUCTURED_EXTRACTIVE,
    EvidenceCard,
)
from app.evidence.pattern_extractor import extract_enumerated_phrases
from app.evidence.structured_composer import (
    compose_structured_answer,
    is_list_enumeration_question,
)
from app.schema.discovery import discover_document_schema
from app.structure import structure_document

DESIGN_PATTERN_TEXT = (
    "Design patterns for implementation\n\n"
    "The first critical design pattern is section-aware ingestion.\n"
    "The second pattern is multi-granular indexing.\n"
    "The third pattern is deterministic query interpretation.\n"
)

BOUNDARY_PDF_DOCUMENT = (
    "Existing architectures\n\n"
    "The most common architecture is the enterprise search stack.\n"
    "A second architecture is the classic QA pipeline.\n"
    "A third architecture is the ontology and knowledge-graph stack.\n"
    "A fourth architecture is the traceability and citation graph.\n\n"
    "Design patterns for implementation\n\n"
    "The first critical design pattern is section-aware ingestion.\n"
    "The second pattern is multi-granular indexing.\n"
    "The third pattern is deterministic query interpretation.\n"
    "The fourth pattern is citation-first answer composition.\n"
    "The fifth pattern is symbolic enrichment.\n"
)

REAL_PDF_STYLE_SECTION = (
    "The most common pre-generative architecture is the enterprise search stack: "
    "repository connectors ingest content, normalize text, and feed search indexes. "
    "OpenEphyra embodied a modular implementation with question analysis, query generation, "
    "search, and answer extraction/selection. "
    "If your stakeholder says 'no AI', this pipeline is still the cleanest conceptual answer "
    "for many teaching examples. "
    "A third architecture is the ontology and knowledge-graph stack. "
    "A fourth architecture is the traceability and citation graph."
)
from app.pipeline import process_document
from app.qa import ask_document
from app.retrieval.section_searcher import collect_section_chunks, find_relevant_sections
from app.storage.models import StoredChunk, StoredSection


def _card(snippet: str, *, chunk_id: str = "c1") -> EvidenceCard:
    return EvidenceCard(
        chunk_id=chunk_id,
        document_name="arch.txt",
        section_title="Architectures",
        start_line=1,
        end_line=5,
        snippet=snippet,
        matched_terms=["architecture"],
        score=2.0,
        confidence="HIGH",
        why_matched="test",
        citation="arch.txt | lines 1-5",
    )


def test_list_enumeration_question_detection() -> None:
    assert is_list_enumeration_question("different architectures?") is True
    assert is_list_enumeration_question("what are the storage types") is True
    assert is_list_enumeration_question("explain memory policy") is False


def test_architecture_answer_includes_only_evidence_phrases() -> None:
    cards = [
        _card(
            "The most common pre-generative architecture is the enterprise search stack.\n"
            "A second architecture is the classic QA pipeline."
        ),
    ]
    answer = compose_structured_answer("different architectures?", cards)

    assert answer is not None
    assert "Enterprise search stack" in answer
    assert "Classic QA pipeline" in answer
    assert "Ontology and knowledge-graph stack" not in answer
    assert "Traceability and citation graph" not in answer


def test_architecture_answer_all_four_when_present() -> None:
    snippet = (
        "The most common pre-generative architecture is the enterprise search stack.\n"
        "A second architecture is the classic QA pipeline.\n"
        "A third architecture is the ontology and knowledge-graph stack.\n"
        "A fourth architecture is the traceability and citation graph."
    )
    answer = compose_structured_answer("what are the architectures", [_card(snippet)])

    assert answer is not None
    assert "1. Enterprise search stack" in answer
    assert "2. Classic QA pipeline" in answer
    assert "3. Ontology and knowledge-graph stack" in answer
    assert "4. Traceability and citation graph" in answer


def test_unknown_list_question_returns_none() -> None:
    cards = [_card("Widgets are described as alpha and beta components.")]
    answer = compose_structured_answer("different widgets?", cards)

    assert answer is None


def test_generic_enumeration_from_ordinal_sentences() -> None:
    snippet = (
        "The first rule is memory isolation.\n"
        "The second rule is CPU binding."
    )
    answer = compose_structured_answer("list the rules", [_card(snippet)])

    assert answer is not None
    assert "memory isolation" in answer.lower()
    assert "cpu binding" in answer.lower()


def test_no_structured_answer_without_cards() -> None:
    assert compose_structured_answer("different architectures?", []) is None


def test_ask_document_structured_extractive_mode(tmp_path: Path) -> None:
    source = tmp_path / "architectures.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(
        "SYSTEM ARCHITECTURES\n\n"
        "The most common architecture is the enterprise search stack.\n"
        "A second architecture is the classic QA pipeline.\n"
        "A third architecture is the ontology and knowledge-graph stack.\n"
        "A fourth architecture is the traceability and citation graph.\n",
        encoding="utf-8",
    )
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "different architectures?",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    assert answer.structured_answer is not None
    assert "Enterprise search stack" in answer.structured_answer
    assert answer.cards
    assert len(answer.cards) >= 1


def test_different_architectures_uses_section_level_retrieval(tmp_path: Path) -> None:
    source = tmp_path / "architectures_section.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(
        "INTRODUCTION\n\n"
        "This section is unrelated.\n\n"
        "# Existing architectures\n\n"
        "The most common pre-generative architecture is the enterprise search stack.\n"
        "A second architecture is the classic QA pipeline.\n"
        "A third architecture is the ontology and knowledge-graph stack.\n"
        "A fourth architecture is the traceability and citation graph.\n",
        encoding="utf-8",
    )
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document("different architectures", processed.document_id, db_path=str(db_path))

    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    assert answer.structured_answer is not None
    assert "1. Enterprise search stack" in answer.structured_answer
    assert "2. Classic QA pipeline" in answer.structured_answer
    assert "3. Ontology and knowledge-graph stack" in answer.structured_answer
    assert "4. Traceability and citation graph" in answer.structured_answer
    assert "transformer architecture" not in answer.structured_answer.lower()
    assert len(answer.cards) >= 1
    assert any(
        "section-level retrieval" in card.why_matched.lower()
        for card in answer.cards
    )


def test_architecture_structured_answer_returns_only_present_items(tmp_path: Path) -> None:
    source = tmp_path / "architectures_partial.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(
        "# Existing architectures\n\n"
        "The most common architecture is the enterprise search stack.\n"
        "A second architecture is the classic QA pipeline.\n",
        encoding="utf-8",
    )
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document("different architectures", processed.document_id, db_path=str(db_path))

    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    assert answer.structured_answer is not None
    assert "these architecture families" in answer.structured_answer.lower()
    assert "Enterprise search stack" in answer.structured_answer
    assert "Classic QA pipeline" in answer.structured_answer
    assert "Ontology and knowledge-graph stack" not in answer.structured_answer
    assert "Traceability and citation graph" not in answer.structured_answer


def test_no_structured_answer_when_no_evidence(tmp_path: Path) -> None:
    source = tmp_path / "empty_topic.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text("Only unrelated network policy text.\n", encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "different architectures?",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.answer_mode == ANSWER_MODE_NO_EVIDENCE
    assert answer.structured_answer is None
    assert not answer.cards


def test_non_list_question_stays_evidence_only() -> None:
    cards = [_card("The enterprise search stack is documented here.")]
    answer = compose_structured_answer("where is search mentioned", cards)

    assert answer is None


def test_real_section_evidence_extracts_all_architecture_families() -> None:
    phrases = extract_enumerated_phrases(REAL_PDF_STYLE_SECTION, "architecture")
    assert len(phrases) == 4
    assert phrases[0] == "Enterprise search stack"
    assert phrases[1] == "Classic QA pipeline"


def test_real_section_structured_composer_lists_all_four() -> None:
    answer = compose_structured_answer(
        "what are different architectures mentioned in the pdf?",
        [
            _card(REAL_PDF_STYLE_SECTION),
        ],
    )
    assert answer is not None
    assert "1. Enterprise search stack" in answer
    assert "2. Classic QA pipeline" in answer
    assert "3. Ontology and knowledge-graph stack" in answer
    assert "4. Traceability and citation graph" in answer


def test_design_patterns_structured_answer_uses_grammar_execution() -> None:
    sections, chunks = structure_document("design.txt", DESIGN_PATTERN_TEXT)
    schema = discover_document_schema(1, sections, chunks)
    cards = [
        EvidenceCard(
            chunk_id="c-design",
            document_name="design.txt",
            section_title="Design patterns for implementation",
            start_line=1,
            end_line=5,
            snippet=(
                "The first critical design pattern is section-aware ingestion.\n"
                "The second pattern is multi-granular indexing.\n"
                "The third pattern is deterministic query interpretation."
            ),
            matched_terms=["design"],
            score=2.0,
            confidence="HIGH",
            why_matched="test",
            citation="design.txt | lines 1-5",
        ),
    ]
    answer = compose_structured_answer(
        "what design patterns are mentioned?",
        cards,
        document_schema=schema,
    )

    assert answer is not None
    assert "1. Section-aware ingestion" in answer
    assert "2. Multi-granular indexing" in answer
    assert "3. Deterministic query interpretation" in answer
    assert "mentions these design patterns" in answer.lower()
    assert "Supporting evidence:" in answer


def test_design_pattern_answer_excludes_architecture_entities() -> None:
    sections, chunks = structure_document("boundary.txt", BOUNDARY_PDF_DOCUMENT)
    schema = discover_document_schema(1, sections, chunks)
    mixed_snippet = (
        "The most common architecture is the enterprise search stack.\n"
        "A second architecture is the classic QA pipeline.\n"
        "A third architecture is the ontology and knowledge-graph stack.\n"
        "A fourth architecture is the traceability and citation graph.\n"
        "The first critical design pattern is section-aware ingestion.\n"
        "The second pattern is multi-granular indexing.\n"
        "The third pattern is deterministic query interpretation.\n"
        "The fourth pattern is citation-first answer composition.\n"
        "The fifth pattern is symbolic enrichment.\n"
    )
    cards = [
        _card(
            mixed_snippet,
            chunk_id="mixed",
        ),
    ]
    cards[0] = EvidenceCard(
        chunk_id="mixed",
        document_name="boundary.txt",
        section_title="Design patterns for implementation",
        start_line=10,
        end_line=20,
        snippet=mixed_snippet,
        matched_terms=["design", "pattern"],
        score=2.0,
        confidence="HIGH",
        why_matched="test",
        citation="boundary.txt | section: Design patterns for implementation | lines 10-20",
    )
    answer = compose_structured_answer(
        "what are different design pattern mentioned in the pdf?",
        cards,
        document_schema=schema,
    )

    assert answer is not None
    lowered = answer.lower()
    assert "section-aware ingestion" in lowered
    assert "citation-first answer composition" in lowered
    assert "symbolic enrichment" in lowered
    answer_body = answer.split("Supporting evidence:")[0].lower()
    assert "classic qa pipeline" not in answer_body
    assert "ontology and knowledge-graph stack" not in lowered
    assert "traceability and citation graph" not in lowered


def test_design_patterns_question_debug_trace_has_grammar_execution(tmp_path: Path) -> None:
    source = tmp_path / "design_runtime.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(BOUNDARY_PDF_DOCUMENT, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "what are different design pattern mentioned in the pdf?",
        processed.document_id,
        db_path=str(db_path),
    )

    trace = "\n".join(answer.debug_trace)
    assert answer.structured_answer is not None
    assert "grammar_execution_success=True" in trace
    assert "entity_validation_enabled=True" in trace
    assert "1. Section-aware ingestion" in answer.structured_answer
    answer_body = answer.structured_answer.split("Supporting evidence:")[0].lower()
    assert "classic qa pipeline" not in answer_body


def test_boundary_pdf_e2e_rejects_architecture_in_trace(tmp_path: Path) -> None:
    source = tmp_path / "boundary_pdf.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(BOUNDARY_PDF_DOCUMENT, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "what are different design pattern mentioned in the pdf?",
        processed.document_id,
        db_path=str(db_path),
    )

    trace = "\n".join(answer.debug_trace)
    assert answer.structured_answer is not None
    assert "entity_validation_enabled=True" in trace
    body = answer.structured_answer.split("Supporting evidence:")[0].lower()
    assert "classic qa pipeline" not in body
    assert "section-aware ingestion" in body


def test_section_searcher_and_chunk_collection() -> None:
    sections = [
        StoredSection(
            section_id="s1",
            title="Overview",
            level=1,
            start_line=1,
            end_line=4,
            parent_section_id=None,
        ),
        StoredSection(
            section_id="s2",
            title="Existing architectures",
            level=1,
            start_line=5,
            end_line=10,
            parent_section_id=None,
        ),
    ]
    ranked = find_relevant_sections("different architecture types", sections, top_k=1)

    assert ranked
    assert ranked[0].section_id == "s2"

    stored_like_chunks = [
        StoredChunk(
            chunk_id="c1",
            document_name="arch.txt",
            text="Existing architectures",
            chunk_type="section",
            start_line=5,
            end_line=5,
            section_title="Existing architectures",
            section_id="s2",
            metadata={},
        ),
        StoredChunk(
            chunk_id="c2",
            document_name="arch.txt",
            text="The enterprise search stack ...",
            chunk_type="paragraph",
            start_line=6,
            end_line=6,
            section_title="Existing architectures",
            section_id="s2",
            metadata={},
        ),
    ]
    selected = collect_section_chunks(ranked[0], stored_like_chunks, max_chunks=12)
    assert len(selected) == 2
