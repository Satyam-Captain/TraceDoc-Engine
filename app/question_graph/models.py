"""Symbolic question graph models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

UNKNOWN_SLOT_LABEL = "?"


def normalize_question_label(label: str) -> str:
    """Normalize a question graph label for comparison."""
    collapsed = re.sub(r"\s+", " ", label.strip().lower())
    return collapsed


@dataclass
class QuestionNode:
    """One node in a question query graph."""

    node_id: str
    label: str
    normalized_label: str
    node_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "normalized_label": self.normalized_label,
            "node_type": self.node_type,
            "metadata": self.metadata,
        }


@dataclass
class QuestionEdge:
    """Directed query edge with optional open slot."""

    source_node_id: str
    relation: str
    target_node_id: str
    is_query_edge: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_node_id": self.source_node_id,
            "relation": self.relation,
            "target_node_id": self.target_node_id,
            "is_query_edge": self.is_query_edge,
            "metadata": self.metadata,
        }


@dataclass
class QuestionGraph:
    """Deterministic symbolic representation of a user question."""

    question: str
    nodes: list[QuestionNode] = field(default_factory=list)
    edges: list[QuestionEdge] = field(default_factory=list)
    intent_type: str = "GENERAL_SEARCH"
    target_relation: str | None = None
    target_category: str | None = None
    unknown_slots: list[str] = field(default_factory=list)

    def node_by_id(self) -> dict[str, QuestionNode]:
        return {node.node_id: node for node in self.nodes}
