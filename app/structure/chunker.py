"""Deterministic, line-preserving document chunking."""

from __future__ import annotations

import hashlib

from app.structure.detector import detect_sections
from app.structure.models import DocumentChunk, DocumentSection

_CHUNK_TYPES = frozenset({"section", "paragraph", "overflow"})


def _make_chunk_id(
    document_name: str, start_line: int, end_line: int, text: str
) -> str:
    payload = f"{document_name}{start_line}{end_line}{text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _section_for_line(
    line_number: int, sections: list[DocumentSection]
) -> DocumentSection | None:
    for section in reversed(sections):
        if section.start_line <= line_number <= section.end_line:
            return section
    return None


def _build_chunk(
    document_name: str,
    chunk_type: str,
    line_items: list[tuple[int, str]],
    section: DocumentSection | None,
) -> DocumentChunk:
    if chunk_type not in _CHUNK_TYPES:
        raise ValueError(f"Unsupported chunk type: {chunk_type}")

    start_line = line_items[0][0]
    end_line = line_items[-1][0]
    text = "\n".join(content for _, content in line_items)
    return DocumentChunk(
        chunk_id=_make_chunk_id(document_name, start_line, end_line, text),
        document_name=document_name,
        text=text,
        chunk_type=chunk_type,
        start_line=start_line,
        end_line=end_line,
        section_title=section.title if section else None,
        section_id=section.section_id if section else None,
        metadata={"line_count": len(line_items)},
    )


def _split_paragraph_overflow(
    document_name: str,
    line_items: list[tuple[int, str]],
    max_chars: int,
    section: DocumentSection | None,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    current: list[tuple[int, str]] = []
    current_len = 0

    for item in line_items:
        line_len = len(item[1]) + (1 if current else 0)
        if current and current_len + line_len > max_chars:
            chunks.append(
                _build_chunk(document_name, "overflow", current, section)
            )
            current = []
            current_len = 0
        current.append(item)
        current_len += line_len

    if current:
        chunks.append(_build_chunk(document_name, "overflow", current, section))
    return chunks


def _chunk_paragraph_block(
    document_name: str,
    line_items: list[tuple[int, str]],
    max_chars: int,
    section: DocumentSection | None,
) -> list[DocumentChunk]:
    text = "\n".join(content for _, content in line_items)
    if len(text) <= max_chars:
        return [_build_chunk(document_name, "paragraph", line_items, section)]
    return _split_paragraph_overflow(document_name, line_items, max_chars, section)


def _apply_overlap(
    chunks: list[DocumentChunk], overlap_lines: int
) -> list[DocumentChunk]:
    if overlap_lines <= 0 or len(chunks) < 2:
        return chunks

    adjusted: list[DocumentChunk] = []
    previous_lines: list[str] = []

    for chunk in chunks:
        chunk_lines = chunk.text.split("\n")
        if (
            adjusted
            and previous_lines
            and chunk.chunk_type != "section"
            and adjusted[-1].chunk_type != "section"
            and adjusted[-1].end_line + 1 >= chunk.start_line
        ):
            overlap = previous_lines[-overlap_lines:]
            if overlap and not chunk.text.startswith(overlap[0]):
                merged_lines = overlap + chunk_lines
                start_line = chunk.start_line - len(overlap)
                merged_text = "\n".join(merged_lines)
                chunk = DocumentChunk(
                    chunk_id=_make_chunk_id(
                        chunk.document_name,
                        start_line,
                        chunk.end_line,
                        merged_text,
                    ),
                    document_name=chunk.document_name,
                    text=merged_text,
                    chunk_type=chunk.chunk_type,
                    start_line=start_line,
                    end_line=chunk.end_line,
                    section_title=chunk.section_title,
                    section_id=chunk.section_id,
                    metadata=dict(chunk.metadata),
                )
        adjusted.append(chunk)
        previous_lines = chunk.text.split("\n")

    return adjusted


def chunk_document(
    document_name: str,
    text: str,
    max_chars: int = 1200,
    overlap_lines: int = 1,
    sections: list[DocumentSection] | None = None,
) -> list[DocumentChunk]:
    """
    Split document text into deterministic chunks with line anchors.

    Chunking prefers section and paragraph boundaries and only splits
    inside a paragraph when it exceeds max_chars.
    """
    if not text:
        return []

    if sections is None:
        sections = detect_sections(text)

    lines = text.split("\n")
    section_start_lines = {section.start_line for section in sections}
    chunks: list[DocumentChunk] = []
    paragraph_buffer: list[tuple[int, str]] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_buffer
        if not paragraph_buffer:
            return
        start_line = paragraph_buffer[0][0]
        active = _section_for_line(start_line, sections)
        chunks.extend(
            _chunk_paragraph_block(
                document_name, paragraph_buffer, max_chars, active
            )
        )
        paragraph_buffer = []

    for line_number, line in enumerate(lines, start=1):
        if line_number in section_start_lines:
            flush_paragraph()
            section = next(
                item for item in sections if item.start_line == line_number
            )
            chunks.append(
                _build_chunk(
                    document_name,
                    "section",
                    [(line_number, line)],
                    section,
                )
            )
            continue

        if not line.strip():
            flush_paragraph()
            continue

        paragraph_buffer.append((line_number, line))

    flush_paragraph()
    return _apply_overlap(chunks, overlap_lines)


def structure_document(
    document_name: str, text: str
) -> tuple[list[DocumentSection], list[DocumentChunk]]:
    """Detect sections and build chunks for a document."""
    sections = detect_sections(text)
    line_count = len(text.split("\n")) if text else 0
    chunks = chunk_document(document_name, text, sections=sections)
    from app.structure.section_assignment import reassign_chunk_sections

    chunks = reassign_chunk_sections(chunks, sections, total_lines=line_count)
    return sections, chunks
