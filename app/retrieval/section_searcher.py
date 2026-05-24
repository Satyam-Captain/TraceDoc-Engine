"""Deterministic section-level retrieval for list/enumeration queries."""

from __future__ import annotations

from app.indexing.normalizer import normalize_token
from app.indexing.tokenizer import tokenize
from app.storage.models import StoredChunk, StoredSection

_VARIANT_PAIRS = (
    ("architecture", "architectures"),
    ("capability", "capabilities"),
    ("pattern", "patterns"),
)


def _question_terms(question: str) -> set[str]:
    terms = {normalize_token(token) for token in tokenize(question)}
    return {term for term in terms if term}


def _expand_variants(terms: set[str]) -> set[str]:
    expanded = set(terms)
    for singular, plural in _VARIANT_PAIRS:
        if singular in terms:
            expanded.add(plural)
        if plural in terms:
            expanded.add(singular)
    return expanded


def find_relevant_sections(
    question: str,
    sections: list[StoredSection],
    top_k: int = 3,
) -> list[StoredSection]:
    """Rank sections by lexical overlap between question and section title."""
    if top_k <= 0 or not sections:
        return []

    query_terms = _expand_variants(_question_terms(question))
    if not query_terms:
        return sections[:top_k]

    scored: list[tuple[float, StoredSection]] = []
    for section in sections:
        title_terms = _expand_variants(_question_terms(section.title))
        overlap = query_terms.intersection(title_terms)
        if not overlap:
            continue

        score = float(len(overlap))
        normalized_title = " ".join(tokenize(section.title.lower()))
        normalized_question = " ".join(tokenize(question.lower()))
        if section.title.strip().lower() in question.strip().lower():
            score += 2.0
        if normalized_title and normalized_title in normalized_question:
            score += 1.5
        if len(overlap) == len(title_terms) and title_terms:
            score += 1.0

        scored.append((score, section))

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].start_line,
            item[1].section_id,
        )
    )
    return [section for _, section in scored[:top_k]]


def collect_section_chunks(
    section: StoredSection,
    chunks: list[StoredChunk],
    max_chunks: int = 12,
) -> list[StoredChunk]:
    """Collect chunks inside section bounds, with deterministic fallback expansion."""
    if max_chunks <= 0:
        return []

    ordered = sorted(chunks, key=lambda item: (item.start_line, item.chunk_id))
    in_bounds = [
        chunk
        for chunk in ordered
        if chunk.start_line >= section.start_line and chunk.end_line <= section.end_line
    ]

    if len(in_bounds) >= 2:
        return in_bounds[:max_chunks]

    # Fallback when end_line is too narrow or section boundaries are imperfect:
    # collect from section start while section_id/title still align.
    selected: list[StoredChunk] = []
    started = False
    for chunk in ordered:
        if not started and chunk.start_line >= section.start_line:
            started = True
        if not started:
            continue

        same_section_id = bool(section.section_id) and chunk.section_id == section.section_id
        same_section_title = (
            bool(section.title)
            and bool(chunk.section_title)
            and chunk.section_title.strip().lower() == section.title.strip().lower()
        )

        if same_section_id or same_section_title:
            selected.append(chunk)
            if len(selected) >= max_chunks:
                break
            continue

        if selected:
            # Stop at first chunk that clearly belongs to another section.
            break

    return selected[:max_chunks]
