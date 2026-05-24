"""Deterministic heading and section detection."""

from __future__ import annotations

import re

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


def _match_heading(line: str) -> tuple[str, int] | None:
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

    return None


def _assign_parent_sections(sections: list[DocumentSection]) -> None:
    stack: list[DocumentSection] = []
    for section in sections:
        while stack and stack[-1].level >= section.level:
            stack.pop()
        section.parent_section_id = stack[-1].section_id if stack else None
        stack.append(section)


def _assign_end_lines(sections: list[DocumentSection], line_count: int) -> None:
    for index, section in enumerate(sections):
        next_start = None
        for candidate in sections[index + 1 :]:
            if candidate.level <= section.level:
                next_start = candidate.start_line
                break
        section.end_line = (next_start - 1) if next_start else line_count


def detect_sections(text: str) -> list[DocumentSection]:
    """
    Detect document sections using deterministic, explainable heading rules.

    Supported patterns include markdown headings, numbered headings,
    uppercase titles, appendix/section labels, and numbered titles.
    """
    if not text:
        return []

    lines = text.split("\n")
    sections: list[DocumentSection] = []

    for line_number, line in enumerate(lines, start=1):
        match = _match_heading(line)
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

    _assign_parent_sections(sections)
    _assign_end_lines(sections, len(lines))
    return sections
