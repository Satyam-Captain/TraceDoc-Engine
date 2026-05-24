"""Deterministic heading and section detection."""

from __future__ import annotations

import re

from app.structure.heading_heuristics import is_probable_heading
from app.structure.hierarchy import build_section_hierarchy, infer_section_ranges
from app.structure.models import DocumentSection

_MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.+?)\s*$")
_SECTION_LABEL = re.compile(r"^Section\s+(\d+)\s*(?:[:.\-]\s*)?(.*)$", re.IGNORECASE)
_APPENDIX = re.compile(
    r"^Appendix\s+([A-Z])(?:\s*[:.\-]\s*(.+))?\s*$", re.IGNORECASE
)
_NUMBER_TITLE = re.compile(r"^(\d+)\s+([A-Za-z].+?)\s*$")
_UPPERCASE_HEADING = re.compile(r"^[A-Z][A-Z0-9\s\-/&(),]+$")


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:48] or "section"


def _make_section_id(start_line: int, title: str) -> str:
    return f"sec-{start_line:05d}-{_slugify(title)}"


def _is_uppercase_heading(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 4 or len(stripped) > 100:
        return False
    if not stripped.isupper():
        return False
    if not _UPPERCASE_HEADING.match(stripped):
        return False
    if stripped.endswith("."):
        return False
    letter_count = sum(character.isalpha() for character in stripped)
    return letter_count >= 3


def _match_heading(
    line: str,
    *,
    previous_line: str | None = None,
    next_line: str | None = None,
) -> tuple[str, int] | None:
    """Return (title, level) if the line is a heading, else None."""
    stripped = line.strip()
    if not stripped:
        return None

    markdown = _MARKDOWN_HEADING.match(stripped)
    if markdown:
        return markdown.group(2).strip(), len(markdown.group(1))

    appendix = _APPENDIX.match(stripped)
    if appendix:
        suffix = (appendix.group(2) or "").strip()
        title = f"Appendix {appendix.group(1)}"
        if suffix:
            title = f"{title}: {suffix}"
        return title, 1

    section_label = _SECTION_LABEL.match(stripped)
    if section_label:
        suffix = section_label.group(2).strip()
        title = f"Section {section_label.group(1)}"
        if suffix:
            title = f"{title}: {suffix}"
        return title, 1

    numbered = _NUMBERED_HEADING.match(stripped)
    if numbered:
        number = numbered.group(1)
        title = numbered.group(2).strip()
        if title:
            level = number.count(".") + 1
            return f"{number} {title}", level
        return None

    number_title = _NUMBER_TITLE.match(stripped)
    if number_title and "." not in number_title.group(1):
        return f"{number_title.group(1)} {number_title.group(2).strip()}", 1

    if _is_uppercase_heading(stripped):
        return stripped, 1

    if is_probable_heading(line, previous_line, next_line):
        return stripped, 1

    return None


def detect_sections(text: str) -> list[DocumentSection]:
    """
    Detect document sections using deterministic, explainable heading rules.

    Supported patterns include markdown headings, numbered headings,
    uppercase titles, appendix/section labels, numbered titles, and
    PDF-friendly layout heuristics for short title-like lines.
    """
    if not text:
        return []

    lines = text.split("\n")
    sections: list[DocumentSection] = []

    for line_number, line in enumerate(lines, start=1):
        previous_line = lines[line_number - 2] if line_number > 1 else None
        next_line = lines[line_number] if line_number < len(lines) else None
        match = _match_heading(
            line,
            previous_line=previous_line,
            next_line=next_line,
        )
        if match is None:
            continue
        title, level = match
        sections.append(
            DocumentSection(
                section_id=_make_section_id(line_number, title),
                title=title,
                level=level,
                start_line=line_number,
                end_line=line_number,
            )
        )

    if not sections:
        return []

    sections = build_section_hierarchy(sections)
    return infer_section_ranges(sections, len(lines))
