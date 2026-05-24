"""Deterministic section hierarchy and line-range inference."""

from __future__ import annotations

from app.structure.models import DocumentSection


def build_section_hierarchy(sections: list[DocumentSection]) -> list[DocumentSection]:
    """
    Assign parent_section_id from heading levels without mutating input sections.

    Higher-level sections become parents of lower-level sections. When a section
    level is the same or higher than the stack top, previous lower-level sections
    are closed before assigning the new parent.
    """
    ordered = sorted(sections, key=lambda section: (section.start_line, section.section_id))
    result: list[DocumentSection] = []
    stack: list[DocumentSection] = []

    for section in ordered:
        while stack and stack[-1].level >= section.level:
            stack.pop()

        parent_id = stack[-1].section_id if stack else None
        result.append(
            DocumentSection(
                section_id=section.section_id,
                title=section.title,
                level=section.level,
                start_line=section.start_line,
                end_line=section.end_line,
                parent_section_id=parent_id,
            )
        )
        stack.append(result[-1])

    return result


def infer_section_ranges(
    sections: list[DocumentSection],
    total_lines: int,
) -> list[DocumentSection]:
    """
    Infer section end_line values from the next same-or-higher-level section.

    Returns new section objects; input sections are not mutated.
    """
    ordered = sorted(sections, key=lambda section: (section.start_line, section.section_id))
    result: list[DocumentSection] = []

    for index, section in enumerate(ordered):
        next_start: int | None = None
        for candidate in ordered[index + 1 :]:
            if candidate.level <= section.level:
                next_start = candidate.start_line
                break

        end_line = (next_start - 1) if next_start is not None else total_lines
        result.append(
            DocumentSection(
                section_id=section.section_id,
                title=section.title,
                level=section.level,
                start_line=section.start_line,
                end_line=end_line,
                parent_section_id=section.parent_section_id,
            )
        )

    return result
