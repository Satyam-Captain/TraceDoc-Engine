"""Tests for evidence engine and answer cards."""

from __future__ import annotations

from dataclasses import fields

from app.evidence import (
    classify_confidence,
    compose_answer_package,
    extract_snippet,
    format_citation,
    highlight_terms,
    select_evidence_cards,
)
from app.evidence.models import AnswerPackage
from app.retrieval.models import SearchResult


def _result(
    *,
    chunk_id: str = "c1",
    text: str = "HPC6 memory is required for the cluster.",
    score: float = 4.0,
    matched_terms: list[str] | None = None,
    section_title: str | None = "Security",
    document_name: str = "policy.txt",
) -> SearchResult:
    terms = matched_terms or ["hpc6", "memory"]
    return SearchResult(
        chunk_id=chunk_id,
        document_name=document_name,
        text=text,
        score=score,
        matched_terms=terms,
        term_scores={term: 1.0 for term in terms},
        start_line=10,
        end_line=12,
        section_title=section_title,
        chunk_type="paragraph",
        why_matched="Matched terms: hpc6, memory. Ranked using deterministic BM25 over lexical index.",
    )


def test_evidence_cards_created_from_search_results() -> None:
    cards = select_evidence_cards("What is HPC6 memory?", [_result()])

    assert len(cards) == 1
    assert cards[0].chunk_id == "c1"
    assert cards[0].matched_terms == ["hpc6", "memory"]


def test_low_score_results_filtered() -> None:
    cards = select_evidence_cards(
        "query",
        [_result(score=0.005), _result(chunk_id="c2", score=2.0)],
    )

    assert len(cards) == 1
    assert cards[0].chunk_id == "c2"


def test_max_cards_respected() -> None:
    results = [
        _result(
            chunk_id=f"c{index}",
            text=f"Unique evidence text number {index} about HPC6 memory.",
            score=5.0 - index,
        )
        for index in range(5)
    ]
    cards = select_evidence_cards("query", results, max_cards=2)

    assert len(cards) == 2


def test_duplicate_snippets_removed() -> None:
    duplicate_text = "HPC6 memory is required."
    results = [
        _result(chunk_id="c1", text=duplicate_text, score=5.0),
        _result(chunk_id="c2", text="  hpc6   memory is required. ", score=4.0),
    ]

    cards = select_evidence_cards("query", results, max_cards=3)

    assert len(cards) == 1


def test_citation_with_section_title() -> None:
    citation = format_citation("policy.txt", 10, 12, "Security")

    assert citation == "policy.txt | section: Security | lines 10-12"


def test_citation_without_section_title() -> None:
    citation = format_citation("policy.txt", 3, 5, None)

    assert citation == "policy.txt | lines 3-5"


def test_long_snippet_is_trimmed() -> None:
    prefix = "intro " * 200
    text = prefix + "HPC6 memory is required." + (" tail" * 200)
    snippet = extract_snippet(text, ["hpc6"])

    assert len(snippet) <= 700 + 6  # allow ellipsis markers
    assert snippet.startswith("...")
    assert snippet.endswith("...")
    assert "HPC6" in snippet or "hpc6" in snippet.lower()


def test_matched_terms_highlighted() -> None:
    highlighted = highlight_terms("HPC6 memory is required", ["hpc6"])

    assert highlighted == "[[HPC6]] memory is required"


def test_highlighting_preserves_original_casing() -> None:
    highlighted = highlight_terms("REQ-001 defines controls", ["req-001"])

    assert "[[REQ-001]]" in highlighted


def test_highlighting_avoids_double_highlighting() -> None:
    highlighted = highlight_terms("[[HPC6]] memory", ["hpc6", "memory"])

    assert highlighted == "[[HPC6]] [[memory]]"
    assert "[[[[HPC6]]" not in highlighted


def test_confidence_levels() -> None:
    assert classify_confidence(3.5, 2) == "HIGH"
    assert classify_confidence(1.2, 1) == "MEDIUM"
    assert classify_confidence(0.5, 1) == "LOW"


def test_no_evidence_when_no_results() -> None:
    package = compose_answer_package("question", [])

    assert package.answer_mode == "NO_EVIDENCE"
    assert package.cards == []
    assert package.no_evidence_message is not None


def test_no_evidence_when_results_below_threshold() -> None:
    package = compose_answer_package("question", [_result(score=0.001)])

    assert package.answer_mode == "NO_EVIDENCE"


def test_answer_package_has_no_generated_answer_field() -> None:
    package = compose_answer_package("What is HPC6?", [_result()])
    field_names = {field.name for field in fields(AnswerPackage)}

    assert "answer" not in field_names
    assert "generated_answer" not in field_names
    assert package.answer_mode == "EVIDENCE_ONLY"
    assert package.explanation
    assert package.cards[0].snippet
