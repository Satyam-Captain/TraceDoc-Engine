"""Tests for section hierarchy helpers."""

from __future__ import annotations

from app.structure.hierarchy import build_section_hierarchy, infer_section_ranges
from app.structure.models import DocumentSection


def test_hierarchy_and_ranges_do_not_mutate_inputs() -> None:
    original = DocumentSection(
        section_id="s1",
        title="Parent",
        level=1,
        start_line=1,
        end_line=1,
        parent_section_id=None,
    )
    child = DocumentSection(
        section_id="s2",
        title="Child",
        level=2,
        start_line=3,
        end_line=3,
        parent_section_id=None,
    )

    hierarchy = build_section_hierarchy([original, child])
    ranged = infer_section_ranges(hierarchy, total_lines=10)

    assert original.parent_section_id is None
    assert original.end_line == 1
    assert hierarchy[1].parent_section_id == "s1"
    assert ranged[1].end_line == 10
