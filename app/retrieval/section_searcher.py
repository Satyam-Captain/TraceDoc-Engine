"""Deterministic section-level retrieval for broader-context questions."""

from __future__ import annotations

import re

from typing import TypeAlias

from app.indexing.normalizer import normalize_token
from app.indexing.tokenizer import tokenize
from app.schema.models import DocumentSchema
from app.schema.normalization import extract_candidate_category
from app.structure.hierarchy import build_section_hierarchy, infer_section_ranges
from app.structure.models import DocumentChunk, DocumentSection
from app.storage.models import StoredChunk, StoredSection

ChunkLike: TypeAlias = StoredChunk | DocumentChunk

_VARIANT_PAIRS = (
    ("architecture", "architectures"),
    ("capability", "capabilities"),
    ("pattern", "patterns"),
    ("section", "sections"),
    ("design_pattern", "design_patterns"),
    ("building_block", "building_blocks"),
    ("improvement", "improvements"),
    ("requirement", "requirements"),
    ("limitation", "limitations"),
)

_SPELLING_CORRECTIONS = {
    "architcture": "architecture",
    "architecure": "architecture",
    "architectur": "architecture",
    "architectues": "architectures",
}

_WEAK_WORDS = frozenset(
    {
        "what",
        "are",
        "different",
        "mentioned",
        "pdf",
        "document",
        "explain",
        "tell",
        "me",
        "the",
        "in",
        "of",
        "a",
        "an",
        "is",
        "was",
        "be",
        "this",
        "that",
        "how",
        "does",
        "do",
    }
)

_HEADING_LINE = re.compile(r"^[A-Z][\w\s\-/&(),]{2,79}$")


def _question_terms(question: str) -> set[str]:
    terms = {normalize_token(token) for token in tokenize(question)}
    return {term for term in terms if term}


def _correct_spelling(term: str) -> str:
    return _SPELLING_CORRECTIONS.get(term, term)


def _expand_variants(terms: set[str]) -> set[str]:
    expanded: set[str] = set()
    for term in terms:
        corrected = _correct_spelling(term)
        expanded.add(corrected)
    for singular, plural in _VARIANT_PAIRS:
        if singular in expanded:
            expanded.add(plural)
        if plural in expanded:
            expanded.add(singular)
    return expanded


def extract_topic_terms(question: str) -> set[str]:
    """
    Extract topic terms from a question for section ranking.

    Removes weak words, corrects common spelling variants, and expands
    singular/plural forms (architectures -> architecture).
    """
    raw_terms = _question_terms(question) - _WEAK_WORDS
    corrected = {_correct_spelling(term) for term in raw_terms}
    return _expand_variants(corrected)


def _content_terms(question: str) -> set[str]:
    return extract_topic_terms(question)


def _is_semantic_section_heading(line: str) -> bool:
    """True when a line is a short semantic heading (not an ordinal sentence)."""
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return False
    if " is " in stripped.lower():
        return False
    if stripped.endswith((".", "!", "?")):
        return False
    return extract_candidate_category(stripped) is not None


def _looks_like_inline_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return False
    if stripped.endswith(".") and " is " not in stripped.lower():
        return False
    if extract_candidate_category(stripped) is not None:
        return True
    if len(stripped.split()) > 14:
        return False
    if stripped.startswith("#"):
        return False
    if not stripped[0].isupper():
        return False
    return bool(_HEADING_LINE.match(stripped))


def derive_sections_from_chunks(chunks: list[DocumentChunk]) -> list[StoredSection]:
    """
    Build section records from section chunks or inline heading lines.

    Used when heading detection did not persist sections (e.g. plain-text PDFs).
    """
    if not chunks:
        return []

    section_chunks = sorted(
        [chunk for chunk in chunks if chunk.chunk_type == "section"],
        key=lambda item: (item.start_line, item.chunk_id),
    )
    document_sections: list[DocumentSection] = []

    seen_titles: set[str] = set()

    if section_chunks:
        for chunk in section_chunks:
            title = chunk.text.strip().split("\n")[0].strip()
            if not title:
                continue
            key = title.lower()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            document_sections.append(
                DocumentSection(
                    section_id=chunk.section_id or chunk.chunk_id,
                    title=title,
                    level=1,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    parent_section_id=None,
                )
            )

    for chunk in sorted(chunks, key=lambda item: (item.start_line, item.chunk_id)):
        if chunk.chunk_type == "section":
            continue
        for line_offset, raw_line in enumerate(chunk.text.splitlines()):
            heading_line = raw_line.strip()
            if not _is_semantic_section_heading(heading_line):
                continue
            key = heading_line.lower()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            line_number = chunk.start_line + line_offset
            document_sections.append(
                DocumentSection(
                    section_id=f"derived-{line_number:05d}",
                    title=heading_line,
                    level=1,
                    start_line=line_number,
                    end_line=chunk.end_line,
                    parent_section_id=None,
                )
            )

    if not document_sections:
        return []

    total_lines = max(chunk.end_line for chunk in chunks)
    hierarchy = build_section_hierarchy(document_sections)
    ranged = infer_section_ranges(hierarchy, total_lines)
    return [
        StoredSection(
            section_id=section.section_id,
            title=section.title,
            level=section.level,
            start_line=section.start_line,
            end_line=section.end_line,
            parent_section_id=section.parent_section_id,
        )
        for section in ranged
    ]


def _schema_category_boost(
    question: str,
    section: StoredSection,
    document_schema: DocumentSchema | None,
) -> float:
    if document_schema is None:
        return 0.0

    from app.schema.discovery import match_question_to_schema_category

    matched = match_question_to_schema_category(question, document_schema)
    if matched is None:
        return 0.0

    section_category = extract_candidate_category(section.title)
    if section_category == matched.normalized_name:
        return 6.0

    if matched.source_section.strip().lower() == section.title.strip().lower():
        return 6.0

    title_lower = section.title.lower()
    label = matched.normalized_name.replace("_", " ")
    if label in title_lower or label + "s" in title_lower:
        return 5.0

    if matched.normalized_name == "design_pattern":
        if "design" in title_lower and "pattern" in title_lower:
            return 5.5
        if "implementation" in title_lower and "pattern" in title_lower:
            return 4.5

    question_lower = question.lower()
    if (
        matched.normalized_name == "design_pattern"
        and "design" in question_lower
        and "pattern" in question_lower
        and "pattern" in title_lower
    ):
        return 4.0

    return 0.0


def score_section_relevance(
    question: str,
    section: StoredSection,
    document_schema: DocumentSchema | None = None,
) -> float:
    """Score a section title against question topic terms (higher is better)."""
    topic_terms = extract_topic_terms(question)
    score = 0.0

    if topic_terms:
        title_lower = section.title.lower()
        title_terms = _expand_variants(_question_terms(section.title))
        overlap = topic_terms.intersection(title_terms)

        score = float(len(overlap))
        for term in topic_terms:
            if term in title_lower:
                score += 1.0

        if section.title.strip().lower() in question.strip().lower():
            score += 2.0

        normalized_title = " ".join(tokenize(section.title.lower()))
        normalized_question = " ".join(tokenize(question.lower()))
        if normalized_title and normalized_title in normalized_question:
            score += 1.5
        if title_terms and overlap == title_terms:
            score += 1.0

    score += _schema_category_boost(question, section, document_schema)
    return score


def find_relevant_sections(
    question: str,
    sections: list[StoredSection],
    top_k: int = 3,
    document_schema: DocumentSchema | None = None,
) -> list[StoredSection]:
    """
    Rank sections by lexical overlap between question topic terms and section title.

    Ranking is deterministic: score descending, then start_line, then section_id.
    """
    if top_k <= 0 or not sections:
        return []

    scored: list[tuple[float, StoredSection]] = []
    for section in sections:
        score = score_section_relevance(
            question, section, document_schema=document_schema
        )
        if score > 0:
            scored.append((score, section))

    if not scored:
        return []

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
    chunks: list[ChunkLike],
    max_chunks: int = 20,
) -> list[ChunkLike]:
    """
    Collect chunks inside a section line range, with deterministic fallback.

    When strict line bounds miss chunks (narrow end_line), falls back to chunks
    sharing section_id or section_title from the section start line onward.
    """
    if max_chunks <= 0:
        return []

    ordered = sorted(chunks, key=lambda item: (item.start_line, item.chunk_id))
    in_bounds = [
        chunk
        for chunk in ordered
        if chunk.start_line >= section.start_line and chunk.end_line <= section.end_line
    ]
    if in_bounds:
        return in_bounds[:max_chunks]

    selected: list[ChunkLike] = []
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
        title_in_first_line = section.title.strip().lower() in chunk.text.split("\n")[0].lower()

        if same_section_id or same_section_title or title_in_first_line:
            selected.append(chunk)
            if len(selected) >= max_chunks:
                break
            continue

        if selected:
            break

    if selected:
        return selected[:max_chunks]

    # Last resort: include chunks starting at section line through next heading-like line.
    for chunk in ordered:
        if chunk.start_line < section.start_line:
            continue
        if chunk.start_line == section.start_line:
            selected.append(chunk)
            continue
        if selected and _looks_like_inline_heading(chunk.text.split("\n")[0]):
            break
        selected.append(chunk)
        if len(selected) >= max_chunks:
            break

    return selected[:max_chunks]
