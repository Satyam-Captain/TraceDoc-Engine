"""Reassign chunk section metadata from inferred section line ranges."""

from __future__ import annotations

from app.structure.hierarchy import build_section_hierarchy, infer_section_ranges
from app.structure.models import DocumentChunk, DocumentSection


def reassign_chunk_sections(
    chunks: list[DocumentChunk],
    sections: list[DocumentSection],
    *,
    total_lines: int | None = None,
) -> list[DocumentChunk]:
    """
    Align chunk section_title and section_id with inferred section ranges.

    Returns new chunk objects; input chunks are not mutated.
    """
    if not chunks or not sections:
        return list(chunks)

    line_total = total_lines
    if line_total is None:
        line_total = max(chunk.end_line for chunk in chunks)

    ranged = infer_section_ranges(build_section_hierarchy(sections), line_total)
    section_for_line = _line_to_section_map(ranged)

    updated: list[DocumentChunk] = []
    for chunk in chunks:
        section = section_for_line.get(chunk.start_line)
        if section is None:
            for line_number in range(chunk.start_line, chunk.end_line + 1):
                section = section_for_line.get(line_number)
                if section is not None:
                    break
        updated.append(
            DocumentChunk(
                chunk_id=chunk.chunk_id,
                document_name=chunk.document_name,
                text=chunk.text,
                chunk_type=chunk.chunk_type,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                section_title=section.title if section else chunk.section_title,
                section_id=section.section_id if section else chunk.section_id,
                metadata=dict(chunk.metadata),
            )
        )
    return updated


def _line_to_section_map(
    sections: list[DocumentSection],
) -> dict[int, DocumentSection]:
    mapping: dict[int, DocumentSection] = {}
    for section in sections:
        for line_number in range(section.start_line, section.end_line + 1):
            mapping[line_number] = section
    return mapping
