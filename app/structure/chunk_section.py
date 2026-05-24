"""Clip chunk text to a section line range."""

from __future__ import annotations

from typing import Protocol


class ChunkLike(Protocol):
    text: str
    start_line: int
    end_line: int
    chunk_type: str


class SectionLike(Protocol):
    start_line: int
    end_line: int


def chunk_overlaps_section(chunk: ChunkLike, section: SectionLike) -> bool:
    return chunk.start_line <= section.end_line and chunk.end_line >= section.start_line


def chunk_within_section(chunk: ChunkLike, section: SectionLike) -> bool:
    return (
        section.start_line <= chunk.start_line <= section.end_line
        and chunk.end_line <= section.end_line
    )


def clip_chunk_text_to_section(chunk: ChunkLike, section: SectionLike) -> str:
    """Return only the lines of a chunk that fall inside a section range."""
    if chunk_within_section(chunk, section):
        return chunk.text

    lines = chunk.text.split("\n")
    if not lines:
        return chunk.text

    kept: list[str] = []
    for offset, line in enumerate(lines):
        line_number = chunk.start_line + offset
        if section.start_line <= line_number <= section.end_line:
            kept.append(line)
    return "\n".join(kept) if kept else chunk.text
