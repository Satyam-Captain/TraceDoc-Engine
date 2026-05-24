"""Deterministic document knowledge graph."""

from app.graph.builder import build_knowledge_graph
from app.graph.extractor import (
    extract_relations_from_sentence,
    split_object_list,
)
from app.graph.models import GraphEdge, GraphNode, KnowledgeGraph, normalize_graph_label
from app.graph.answer_composer import (
    GraphAnswer,
    compose_graph_answer,
    graph_answer_debug_lines,
    graph_matches_to_evidence_cards,
    is_relationship_style_question,
    should_use_graph_answer,
)
from app.graph.matcher import (
    GraphMatch,
    graph_match_debug_lines,
    label_match_score,
    match_question_graph,
)
from app.graph.traversal import (
    find_edges_by_relation,
    find_nodes_by_label,
    get_neighbors,
    get_subgraph_for_node,
)

__all__ = [
    "GraphAnswer",
    "GraphMatch",
    "compose_graph_answer",
    "graph_answer_debug_lines",
    "graph_matches_to_evidence_cards",
    "is_relationship_style_question",
    "should_use_graph_answer",
    "GraphEdge",
    "GraphNode",
    "KnowledgeGraph",
    "build_knowledge_graph",
    "extract_relations_from_sentence",
    "find_edges_by_relation",
    "find_nodes_by_label",
    "get_neighbors",
    "get_subgraph_for_node",
    "graph_match_debug_lines",
    "label_match_score",
    "match_question_graph",
    "normalize_graph_label",
    "split_object_list",
]
