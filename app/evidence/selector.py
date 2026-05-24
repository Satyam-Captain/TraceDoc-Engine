"""Evidence selection and card construction."""

from __future__ import annotations

import re

from app.evidence.highlighter import highlight_terms
from app.evidence.models import EvidenceCard
from app.retrieval.models import SearchResult

MAX_SNIPPET_CHARS = 700


def classify_confidence(score: float, matched_terms_count: int) -> str:
    """Classify evidence confidence from score and matched term count."""
    if score >= 3 and matched_terms_count >= 2:
        return "HIGH"
    if score >= 1 or matched_terms_count >= 2:
        return "MEDIUM"
    return "LOW"


def format_citation(
    document_name: str,
    start_line: int,
    end_line: int,
    section_title: str | None,
) -> str:
    """Build a deterministic citation string."""
    if section_title:
        return (
            f"{document_name} | section: {section_title} | "
            f"lines {start_line}-{end_line}"
        )
    return f"{document_name} | lines {start_line}-{end_line}"


def normalize_snippet(text: str) -> str:
    """Normalize snippet text for duplicate detection."""
    collapsed = re.sub(r"\s+", " ", text.strip().lower())
    return collapsed


def _first_match_position(text: str, matched_terms: list[str]) -> int:
    lower_text = text.lower()
    positions: list[int] = []
    for term in matched_terms:
        index = lower_text.find(term.lower())
        if index != -1:
            positions.append(index)
    return min(positions) if positions else 0


def extract_snippet(text: str, matched_terms: list[str]) -> str:
    """
    Return chunk text as snippet, trimming deterministically when too long.

    Long text is trimmed around the earliest matched term occurrence.
    """
    if len(text) <= MAX_SNIPPET_CHARS:
        return text

    anchor = _first_match_position(text, matched_terms)
    window = MAX_SNIPPET_CHARS
    start = max(0, anchor - window // 2)
    end = min(len(text), start + window)
    if end - start < window:
        start = max(0, end - window)

    snippet = text[start:end]
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


def _search_result_to_card(result: SearchResult) -> EvidenceCard:
    snippet = extract_snippet(result.text, result.matched_terms)
    highlighted_snippet = highlight_terms(snippet, result.matched_terms)
    matched_terms_count = len(result.matched_terms)

    return EvidenceCard(
        chunk_id=result.chunk_id,
        document_name=result.document_name,
        section_title=result.section_title,
        start_line=result.start_line,
        end_line=result.end_line,
        snippet=highlighted_snippet,
        matched_terms=list(result.matched_terms),
        score=result.score,
        confidence=classify_confidence(result.score, matched_terms_count),
        why_matched=result.why_matched,
        citation=format_citation(
            result.document_name,
            result.start_line,
            result.end_line,
            result.section_title,
        ),
    )


def select_evidence_cards(
    question: str,
    search_results: list[SearchResult],
    max_cards: int = 3,
    min_score: float = 0.01,
) -> list[EvidenceCard]:
    """
    Convert search results into deduplicated evidence cards.

    Results below min_score are discarded. Duplicate normalized snippets
    are removed while preserving retrieval ranking order.
    """
    del question  # reserved for future query-aware selection

    cards: list[EvidenceCard] = []
    seen_snippets: set[str] = set()

    for result in search_results:
        if result.score < min_score:
            continue

        card = _search_result_to_card(result)
        normalized = normalize_snippet(card.snippet.replace("[[", "").replace("]]", ""))
        if normalized in seen_snippets:
            continue
        seen_snippets.add(normalized)
        cards.append(card)

        if len(cards) >= max_cards:
            break

    return cards
