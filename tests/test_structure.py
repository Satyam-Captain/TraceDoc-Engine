"""Tests for structure extraction and chunking."""

from __future__ import annotations

import hashlib

from app.structure import (
    chunk_document,
    detect_sections,
    structure_document,
)
from app.structure.chunker import _make_chunk_id


def test_numbered_heading_detection() -> None:
    text = "1. Introduction\nBody\n1.1 Scope\nMore"
    sections = detect_sections(text)

    assert len(sections) == 2
    assert sections[0].title == "1 Introduction"
    assert sections[0].level == 1
    assert sections[1].title == "1.1 Scope"
    assert sections[1].level == 2
    assert sections[1].parent_section_id == sections[0].section_id


def test_deep_numbered_heading_detection() -> None:
    text = "2.3.4 Requirement Details\nDetail body"
    sections = detect_sections(text)

    assert len(sections) == 1
    assert sections[0].title == "2.3.4 Requirement Details"
    assert sections[0].level == 3


def test_markdown_heading_detection() -> None:
    text = "# Top\n## Sub\nContent"
    sections = detect_sections(text)

    assert [(section.title, section.level) for section in sections] == [
        ("Top", 1),
        ("Sub", 2),
    ]
    assert sections[1].parent_section_id == sections[0].section_id


def test_uppercase_heading_detection() -> None:
    text = "INTRODUCTION\nIntro text"
    sections = detect_sections(text)

    assert len(sections) == 1
    assert sections[0].title == "INTRODUCTION"
    assert sections[0].level == 1


def test_appendix_heading_detection() -> None:
    text = "Appendix A\nAppendix content\nSection 4\nSection body"
    sections = detect_sections(text)

    assert sections[0].title == "Appendix A"
    assert sections[1].title == "Section 4"


def test_section_and_number_title_detection() -> None:
    text = "4 Requirements\nRequirement text"
    sections = detect_sections(text)

    assert len(sections) == 1
    assert sections[0].title == "4 Requirements"


def test_basic_chunk_creation() -> None:
    text = "Alpha paragraph.\n\nBeta paragraph."
    chunks = chunk_document("demo.txt", text)

    assert len(chunks) >= 2
    assert all(chunk.document_name == "demo.txt" for chunk in chunks)
    assert {chunk.chunk_type for chunk in chunks} <= {
        "section",
        "paragraph",
        "overflow",
    }


def test_chunk_line_numbers() -> None:
    text = "Line one\n\nLine three"
    chunks = chunk_document("lines.txt", text)

    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 1
    assert chunks[1].start_line == 3
    assert chunks[1].end_line == 3


def test_stable_deterministic_chunk_ids() -> None:
    text = "Stable chunk id check."
    first = chunk_document("stable.txt", text)
    second = chunk_document("stable.txt", text)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    chunk = first[0]
    expected = hashlib.sha256(
        f"stable.txt{chunk.start_line}{chunk.end_line}{chunk.text}".encode()
    ).hexdigest()[:12]
    assert chunk.chunk_id == expected
    assert chunk.chunk_id == _make_chunk_id(
        "stable.txt", chunk.start_line, chunk.end_line, chunk.text
    )


def test_section_title_attached_to_chunks() -> None:
    text = "# Overview\n\nOverview body paragraph."
    sections, chunks = structure_document("overview.md", text)

    assert len(sections) == 1
    section_chunks = [chunk for chunk in chunks if chunk.chunk_type == "section"]
    body_chunks = [chunk for chunk in chunks if chunk.chunk_type == "paragraph"]

    assert section_chunks[0].section_title == "Overview"
    assert body_chunks[0].section_title == "Overview"
    assert body_chunks[0].section_id == sections[0].section_id


def test_long_paragraph_overflow_chunking() -> None:
    long_line = "word " * 400
    text = f"{long_line}\n{long_line}"
    chunks = chunk_document("overflow.txt", text, max_chars=500)

    assert any(chunk.chunk_type == "overflow" for chunk in chunks)
    assert len(chunks) >= 2
    assert all(chunk.end_line >= chunk.start_line for chunk in chunks)


def test_empty_text_handling() -> None:
    assert detect_sections("") == []
    assert chunk_document("empty.txt", "") == []
    sections, chunks = structure_document("empty.txt", "")
    assert sections == []
    assert chunks == []
