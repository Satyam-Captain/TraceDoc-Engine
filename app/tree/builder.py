"""Build a deterministic semantic tree from sections and chunks."""

from __future__ import annotations

import hashlib
import re

from app.evidence.sentence_splitter import split_sentences
from app.structure.hierarchy import build_section_hierarchy, infer_section_ranges
from app.structure.models import DocumentChunk, DocumentSection
from app.tree.models import DocumentTree, TreeNode

_LIST_ITEM_LINE = re.compile(r"^\s*(?:[-*•]|\d+[\.\)])\s+.+")
_TABLE_ROW_LINE = re.compile(r"^\s*\|.+\|\s*$|^\s*[^|]+\|[^|]+\s*$")


def _stable_node_id(node_type: str, start_line: int, end_line: int, text: str) -> str:
    payload = f"{node_type}:{start_line}:{end_line}:{text[:80]}"
    return f"{node_type}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:10]}"


def _section_for_line(
    line_number: int, sections: list[DocumentSection]
) -> DocumentSection | None:
    """Return the deepest (innermost) section containing a line."""
    matches = [
        section
        for section in sections
        if section.start_line <= line_number <= section.end_line
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: (item.level, item.start_line))


def _line_items_for_chunk(chunk: DocumentChunk) -> list[tuple[int, str]]:
    lines = chunk.text.split("\n")
    if not lines:
        return []
    items: list[tuple[int, str]] = []
    for offset, line in enumerate(lines):
        items.append((chunk.start_line + offset, line))
    return items


def _sentence_nodes(
    paragraph_text: str,
    start_line: int,
    end_line: int,
    parent_id: str,
) -> list[TreeNode]:
    sentences = split_sentences(paragraph_text)
    if not sentences:
        return []
    nodes: list[TreeNode] = []
    search_from = 0
    for sentence in sentences:
        index = paragraph_text.find(sentence, search_from)
        if index < 0:
            index = search_from
        search_from = index + len(sentence)
        nodes.append(
            TreeNode(
                node_id=_stable_node_id("sentence", start_line, end_line, sentence),
                node_type="sentence",
                text=sentence.strip(),
                start_line=start_line,
                end_line=end_line,
                parent_id=parent_id,
            )
        )
    return nodes


def _paragraph_children(
    chunk: DocumentChunk,
    parent_id: str,
) -> list[TreeNode]:
    line_items = _line_items_for_chunk(chunk)
    if not line_items:
        return []

    paragraph_id = _stable_node_id(
        "paragraph", chunk.start_line, chunk.end_line, chunk.text
    )
    children: list[TreeNode] = []
    buffer: list[tuple[int, str]] = []

    def flush_buffer() -> None:
        if not buffer:
            return
        block_start = buffer[0][0]
        block_end = buffer[-1][0]
        block_text = "\n".join(line for _, line in buffer)
        block_id = _stable_node_id("paragraph", block_start, block_end, block_text)
        block_children: list[TreeNode] = []

        if _LIST_ITEM_LINE.match(block_text.strip()) and "\n" not in block_text.strip():
            block_children.append(
                TreeNode(
                    node_id=_stable_node_id("list_item", block_start, block_end, block_text),
                    node_type="list_item",
                    text=block_text.strip(),
                    start_line=block_start,
                    end_line=block_end,
                    parent_id=block_id,
                )
            )
        elif _TABLE_ROW_LINE.match(block_text.strip()):
            block_children.append(
                TreeNode(
                    node_id=_stable_node_id("table_row", block_start, block_end, block_text),
                    node_type="table_row",
                    text=block_text.strip(),
                    start_line=block_start,
                    end_line=block_end,
                    parent_id=block_id,
                )
            )
        else:
            block_children.extend(
                _sentence_nodes(block_text, block_start, block_end, block_id)
            )

        children.append(
            TreeNode(
                node_id=block_id,
                node_type="paragraph",
                text=block_text,
                start_line=block_start,
                end_line=block_end,
                parent_id=parent_id,
                children=block_children,
            )
        )
        buffer.clear()

    for item in line_items:
        line = item[1]
        if _LIST_ITEM_LINE.match(line.strip()) or _TABLE_ROW_LINE.match(line.strip()):
            flush_buffer()
            line_no, content = item
            node_type = (
                "table_row"
                if _TABLE_ROW_LINE.match(content.strip())
                else "list_item"
            )
            children.append(
                TreeNode(
                    node_id=_stable_node_id(node_type, line_no, line_no, content),
                    node_type=node_type,
                    text=content.strip(),
                    start_line=line_no,
                    end_line=line_no,
                    parent_id=parent_id,
                )
            )
            continue
        buffer.append(item)

    flush_buffer()

    if children:
        return children

    return [
        TreeNode(
            node_id=paragraph_id,
            node_type="paragraph",
            text=chunk.text,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            parent_id=parent_id,
            children=_sentence_nodes(
                chunk.text, chunk.start_line, chunk.end_line, paragraph_id
            ),
        )
    ]


def _merge_section_text(section_node: TreeNode) -> str:
    parts: list[str] = []
    if section_node.title and section_node.title not in parts:
        title = section_node.title.strip()
        if title and not any(
            title.lower() in child.text.lower()
            for child in section_node.children
            if child.node_type == "paragraph"
        ):
            parts.append(title)

    for child in section_node.children:
        if child.node_type == "paragraph":
            if child.text.strip():
                parts.append(child.text.strip())
        elif child.node_type in {"list_item", "table_row", "sentence"}:
            if child.text.strip():
                parts.append(child.text.strip())
        else:
            nested = _merge_section_text(child)
            if nested.strip():
                parts.append(nested.strip())
    return "\n\n".join(parts)


def build_document_tree(
    sections: list[DocumentSection],
    chunks: list[DocumentChunk],
    *,
    document_name: str = "",
    document_id: int | None = None,
) -> DocumentTree:
    """
    Build a deterministic document → section → paragraph → sentence tree.

    Section boundaries use inferred line ranges (next same/higher-level section).
    """
    total_lines = 1
    if chunks:
        total_lines = max(total_lines, max(chunk.end_line for chunk in chunks))
    if sections:
        total_lines = max(total_lines, max(section.end_line for section in sections))

    hierarchy = build_section_hierarchy(sections) if sections else []
    ranged_sections = infer_section_ranges(hierarchy, total_lines)

    root = TreeNode(
        node_id="document-root",
        node_type="document",
        title=document_name or "document",
        text="",
        start_line=1,
        end_line=total_lines,
        parent_id=None,
        metadata={"document_name": document_name},
    )

    section_nodes_by_id: dict[str, TreeNode] = {}
    for section in ranged_sections:
        section_node = TreeNode(
            node_id=_stable_node_id(
                "section", section.start_line, section.end_line, section.title
            ),
            node_type="section",
            title=section.title,
            text=section.title,
            start_line=section.start_line,
            end_line=section.end_line,
            parent_id=root.node_id,
            metadata={
                "section_id": section.section_id,
                "level": section.level,
            },
        )
        section_nodes_by_id[section.section_id] = section_node
        root.children.append(section_node)

    ordered_chunks = sorted(chunks, key=lambda item: (item.start_line, item.chunk_id))
    for chunk in ordered_chunks:
        if chunk.chunk_type == "section":
            section = _section_for_line(chunk.start_line, ranged_sections)
            if section and section.section_id in section_nodes_by_id:
                node = section_nodes_by_id[section.section_id]
                if not node.title or node.title == node.text:
                    heading = chunk.text.strip().split("\n")[0].strip()
                    if heading:
                        node.title = heading
                        node.text = heading
            continue

        if chunk.chunk_type not in {"paragraph", "overflow"}:
            continue

        section = _section_for_line(chunk.start_line, ranged_sections)
        if section is None:
            continue
        section_node = section_nodes_by_id.get(section.section_id)
        if section_node is None:
            continue

        section_node.children.extend(
            _paragraph_children(chunk, section_node.node_id)
        )

    for section_node in root.children:
        if section_node.node_type != "section":
            continue
        section_node.text = _merge_section_text(section_node)

    return DocumentTree(
        document_name=document_name,
        document_id=document_id,
        root=root,
    )
