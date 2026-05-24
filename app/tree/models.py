"""Deterministic document semantic tree models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

NodeType = Literal[
    "document",
    "section",
    "paragraph",
    "sentence",
    "list_item",
    "table_row",
]


@dataclass
class TreeNode:
    """One node in a document semantic tree."""

    node_id: str
    node_type: NodeType
    text: str
    start_line: int
    end_line: int
    title: str | None = None
    parent_id: str | None = None
    children: list[TreeNode] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "title": self.title,
            "text": self.text,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TreeNode:
        children = [cls.from_dict(item) for item in data.get("children", [])]
        return cls(
            node_id=str(data["node_id"]),
            node_type=data["node_type"],
            title=data.get("title"),
            text=str(data.get("text", "")),
            start_line=int(data["start_line"]),
            end_line=int(data["end_line"]),
            parent_id=data.get("parent_id"),
            children=children,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class DocumentTree:
    """Rooted semantic tree for one document."""

    document_name: str
    root: TreeNode
    document_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_name": self.document_name,
            "document_id": self.document_id,
            "root": self.root.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentTree:
        return cls(
            document_name=str(data.get("document_name", "")),
            document_id=data.get("document_id"),
            root=TreeNode.from_dict(data["root"]),
        )
