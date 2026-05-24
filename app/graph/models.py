"""Deterministic knowledge graph models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def normalize_graph_label(label: str) -> str:
    """Normalize a label for deduplication and lookup."""
    collapsed = re.sub(r"\s+", " ", label.strip().lower())
    return collapsed


@dataclass
class GraphNode:
    """One node in a document knowledge graph."""

    node_id: str
    label: str
    normalized_label: str
    node_type: str
    source_section: str | None = None
    source_line_start: int | None = None
    source_line_end: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "normalized_label": self.normalized_label,
            "node_type": self.node_type,
            "source_section": self.source_section,
            "source_line_start": self.source_line_start,
            "source_line_end": self.source_line_end,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphNode:
        return cls(
            node_id=str(data["node_id"]),
            label=str(data["label"]),
            normalized_label=str(data.get("normalized_label", normalize_graph_label(data["label"]))),
            node_type=str(data["node_type"]),
            source_section=data.get("source_section"),
            source_line_start=data.get("source_line_start"),
            source_line_end=data.get("source_line_end"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class GraphEdge:
    """Directed subject-relation-object edge."""

    edge_id: str
    source_node_id: str
    relation: str
    target_node_id: str
    source_sentence: str = ""
    source_section: str = ""
    confidence_score: float = 0.85
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "relation": self.relation,
            "target_node_id": self.target_node_id,
            "source_sentence": self.source_sentence,
            "source_section": self.source_section,
            "confidence_score": self.confidence_score,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphEdge:
        return cls(
            edge_id=str(data["edge_id"]),
            source_node_id=str(data["source_node_id"]),
            relation=str(data["relation"]),
            target_node_id=str(data["target_node_id"]),
            source_sentence=str(data.get("source_sentence", "")),
            source_section=str(data.get("source_section", "")),
            confidence_score=float(data.get("confidence_score", 0.85)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class KnowledgeGraph:
    """Symbolic knowledge graph for one document."""

    document_id: int
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeGraph:
        return cls(
            document_id=int(data["document_id"]),
            nodes=[GraphNode.from_dict(item) for item in data.get("nodes", [])],
            edges=[GraphEdge.from_dict(item) for item in data.get("edges", [])],
        )

    def node_by_id(self) -> dict[str, GraphNode]:
        return {node.node_id: node for node in self.nodes}
