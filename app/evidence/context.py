"""Context-window expansion for short or heading-only evidence matches."""

from __future__ import annotations

from app.retrieval.models import SearchResult
from app.structure.models import DocumentChunk

SHORT_SNIPPET_THRESHOLD = 120


def _is_heading_like(text: str) -> bool:
    """Heuristic: single short line or markdown-style heading."""
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith("#"):
        return True
    lines = [line for line in stripped.splitlines() if line.strip()]
    if len(lines) == 1 and len(stripped) < 80:
        words = stripped.split()
        if len(words) <= 10 and stripped[0].isupper():
            return True
    return False


def needs_context_expansion(result: SearchResult) -> bool:
    """Return True when neighboring chunks should be merged into evidence."""
    text = result.text.strip()
    if len(text) < SHORT_SNIPPET_THRESHOLD:
        return True
    if result.chunk_type == "section":
        return True
    return _is_heading_like(text)


def _same_section(anchor: DocumentChunk, other: DocumentChunk) -> bool:
    if anchor.section_id and other.section_id:
        return anchor.section_id == other.section_id
    if anchor.section_title and other.section_title:
        return anchor.section_title == other.section_title
    return False


def expand_result_context(
    search_result: SearchResult,
    all_chunks: list[DocumentChunk],
    window_before: int = 1,
    window_after: int = 3,
) -> SearchResult:
    """
    Expand a search result with nearby chunks from the same section.

    When the matched snippet is short, heading-like, or a section chunk,
    merges real text from preceding and following chunks in the same
    document section. Line numbers span the combined range.
    """
    doc_chunks = sorted(
        [c for c in all_chunks if c.document_name == search_result.document_name],
        key=lambda c: (c.start_line, c.chunk_id),
    )
    if not doc_chunks:
        return search_result

    try:
        idx = next(
            i for i, chunk in enumerate(doc_chunks) if chunk.chunk_id == search_result.chunk_id
        )
    except StopIteration:
        return search_result

    if not needs_context_expansion(search_result):
        return search_result

    anchor = doc_chunks[idx]
    before = doc_chunks[max(0, idx - window_before) : idx]
    after = doc_chunks[idx + 1 : idx + 1 + window_after]

    selected: list[DocumentChunk] = []
    seen_ids: set[str] = set()
    for chunk in before + [anchor] + after:
        if chunk.chunk_id in seen_ids:
            continue
        if not _same_section(anchor, chunk):
            continue
        seen_ids.add(chunk.chunk_id)
        selected.append(chunk)

    if len(selected) <= 1:
        return search_result

    selected.sort(key=lambda c: (c.start_line, c.chunk_id))
    combined_text = "\n\n".join(chunk.text for chunk in selected)

    expansion_note = (
        " Context expanded from neighboring chunks in the same section."
    )
    return SearchResult(
        chunk_id=search_result.chunk_id,
        document_name=search_result.document_name,
        text=combined_text,
        score=search_result.score,
        matched_terms=list(search_result.matched_terms),
        term_scores=dict(search_result.term_scores),
        start_line=selected[0].start_line,
        end_line=selected[-1].end_line,
        section_title=search_result.section_title,
        section_id=search_result.section_id,
        chunk_type=search_result.chunk_type,
        why_matched=search_result.why_matched + expansion_note,
    )
