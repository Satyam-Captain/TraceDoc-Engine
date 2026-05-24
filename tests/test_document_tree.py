"""Tests for deterministic document semantic tree."""

from __future__ import annotations

from app.structure import structure_document
from app.tree import (
    build_document_tree,
    find_section_by_title,
    get_section_sentences,
    get_section_text,
)
from app.tree.traversal import iter_nodes

TREE_FIXTURE = (
    "Existing architectures\n"
    "The most common pre-generative architecture is the enterprise search stack.\n"
    "A second architecture is the classic QA pipeline.\n"
    "A third architecture is the ontology and knowledge-graph stack.\n"
    "A fourth architecture is the traceability and citation graph.\n"
    "\n"
    "Design patterns for implementation\n"
    "The first critical design pattern is section-aware ingestion.\n"
    "The second pattern is multi-granular indexing.\n"
    "The third pattern is deterministic query interpretation.\n"
    "The fourth pattern is citation-first answer composition.\n"
    "The fifth pattern is symbolic enrichment.\n"
    "The sixth pattern is security and audit by design.\n"
)


def _build_tree() -> tuple[object, object]:
    sections, chunks = structure_document("tree_fixture.txt", TREE_FIXTURE)
    tree = build_document_tree(sections, chunks, document_name="tree_fixture.txt")
    return tree, sections


def test_tree_has_document_root() -> None:
    tree, _ = _build_tree()
    assert tree.root.node_type == "document"
    assert tree.root.node_id == "document-root"


def test_tree_has_required_section_nodes() -> None:
    tree, _ = _build_tree()
    section_titles = {
        node.title
        for node in iter_nodes(tree.root)
        if node.node_type == "section"
    }
    assert "Existing architectures" in section_titles
    assert "Design patterns for implementation" in section_titles


def test_architecture_section_text_is_complete_and_isolated() -> None:
    tree, _ = _build_tree()
    arch = find_section_by_title(tree, "Existing architectures")
    assert arch is not None
    text = get_section_text(arch).lower()
    assert "enterprise search stack" in text
    assert "classic qa pipeline" in text
    assert "ontology and knowledge-graph stack" in text
    assert "traceability and citation graph" in text
    assert "section-aware ingestion" not in text
    assert "multi-granular indexing" not in text


def test_design_pattern_section_text_is_complete_and_isolated() -> None:
    tree, _ = _build_tree()
    design = find_section_by_title(tree, "Design patterns for implementation")
    assert design is not None
    text = get_section_text(design).lower()
    for marker in (
        "section-aware ingestion",
        "multi-granular indexing",
        "deterministic query interpretation",
        "citation-first answer composition",
        "symbolic enrichment",
        "security and audit by design",
    ):
        assert marker in text
    assert "enterprise search stack" not in text
    assert "traceability and citation graph" not in text


def test_section_sentences_cover_ordinal_lines() -> None:
    tree, _ = _build_tree()
    arch = find_section_by_title(tree, "Existing architectures")
    assert arch is not None
    sentences = get_section_sentences(arch)
    joined = " ".join(sentences).lower()
    assert "second architecture" in joined
    assert "fourth architecture" in joined
