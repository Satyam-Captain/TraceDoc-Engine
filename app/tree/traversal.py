"""Traversal helpers for document semantic trees."""

from __future__ import annotations

from app.schema.normalization import extract_candidate_category
from app.tree.models import DocumentTree, TreeNode

_NODE_TYPES_WITH_TEXT = frozenset(
    {"paragraph", "sentence", "list_item", "table_row"}
)


def iter_nodes(node: TreeNode) -> list[TreeNode]:
    """Depth-first list of node and descendants."""
    ordered = [node]
    for child in node.children:
        ordered.extend(iter_nodes(child))
    return ordered


def find_section_by_title(tree: DocumentTree, title: str) -> TreeNode | None:
    """Return the first section node whose title matches (case-insensitive)."""
    target = title.strip().lower()
    if not target:
        return None
    for node in iter_nodes(tree.root):
        if node.node_type != "section":
            continue
        node_title = (node.title or "").strip().lower()
        if node_title == target or target in node_title:
            return node
    return None


def find_sections_by_category(tree: DocumentTree, category: str) -> list[TreeNode]:
    """Return section nodes whose title maps to a schema category."""
    normalized = category.strip().lower()
    found: list[TreeNode] = []
    for node in iter_nodes(tree.root):
        if node.node_type != "section":
            continue
        section_category = extract_candidate_category(node.title or "")
        if section_category == normalized:
            found.append(node)
    return found


def get_section_text(section_node: TreeNode) -> str:
    """
    Return full logical text for a section node.

    Uses pre-merged section text when present; otherwise aggregates descendants.
    """
    if section_node.node_type != "section":
        return section_node.text.strip()

    if section_node.text and section_node.text.strip() != (section_node.title or "").strip():
        body = section_node.text.strip()
        title = (section_node.title or "").strip()
        if title and body.startswith(title):
            return body
        if body and title and title not in body:
            return f"{title}\n\n{body}"
        return body

    parts: list[str] = []
    for child in section_node.children:
        if child.node_type == "paragraph":
            if child.text.strip():
                parts.append(child.text.strip())
        elif child.node_type in _NODE_TYPES_WITH_TEXT:
            if child.text.strip():
                parts.append(child.text.strip())
        else:
            nested = get_section_text(child)
            if nested.strip():
                parts.append(nested.strip())
    return "\n\n".join(parts)


def get_section_sentences(section_node: TreeNode) -> list[str]:
    """Collect sentence node texts under a section in document order."""
    sentences: list[str] = []
    for node in iter_nodes(section_node):
        if node.node_type == "sentence" and node.text.strip():
            sentences.append(node.text.strip())
        elif node.node_type == "list_item" and node.text.strip():
            sentences.append(node.text.strip())
    if sentences:
        return sentences

    from app.evidence.sentence_splitter import split_sentences

    return [s for s in split_sentences(get_section_text(section_node)) if s.strip()]
