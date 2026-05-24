"""Traversal helpers for document knowledge graphs."""

from __future__ import annotations

from collections import deque

from app.graph.models import GraphEdge, GraphNode, KnowledgeGraph, normalize_graph_label


def find_nodes_by_label(graph: KnowledgeGraph, label: str) -> list[GraphNode]:
    """Return nodes whose label or normalized label matches."""
    target = normalize_graph_label(label)
    return [
        node
        for node in graph.nodes
        if node.normalized_label == target
        or node.label.strip().lower() == target
    ]


def _edges_from(graph: KnowledgeGraph) -> dict[str, list[GraphEdge]]:
    outgoing: dict[str, list[GraphEdge]] = {}
    for edge in graph.edges:
        outgoing.setdefault(edge.source_node_id, []).append(edge)
    return outgoing


def get_neighbors(
    graph: KnowledgeGraph,
    node_id: str,
    relation: str | None = None,
) -> list[GraphNode]:
    """Return target nodes reachable by outgoing edges from node_id."""
    nodes = graph.node_by_id()
    relation_key = relation.strip().lower().replace(" ", "_") if relation else None
    neighbors: list[GraphNode] = []
    seen: set[str] = set()
    for edge in graph.edges:
        if edge.source_node_id != node_id:
            continue
        if relation_key and edge.relation != relation_key:
            continue
        target = nodes.get(edge.target_node_id)
        if target is None or target.node_id in seen:
            continue
        seen.add(target.node_id)
        neighbors.append(target)
    return neighbors


def find_edges_by_relation(graph: KnowledgeGraph, relation: str) -> list[GraphEdge]:
    """Return all edges with a given relation key."""
    relation_key = relation.strip().lower().replace(" ", "_")
    return [edge for edge in graph.edges if edge.relation == relation_key]


def get_subgraph_for_node(
    graph: KnowledgeGraph,
    node_id: str,
    depth: int = 1,
) -> KnowledgeGraph:
    """Return a shallow subgraph reachable within depth hops."""
    if depth < 0:
        depth = 0

    nodes_by_id = graph.node_by_id()
    if node_id not in nodes_by_id:
        return KnowledgeGraph(document_id=graph.document_id, nodes=[], edges=[])

    included_nodes: set[str] = {node_id}
    included_edges: list[GraphEdge] = []
    outgoing = _edges_from(graph)

    frontier = deque([(node_id, 0)])
    visited: set[str] = {node_id}

    while frontier:
        current_id, current_depth = frontier.popleft()
        if current_depth >= depth:
            continue
        for edge in outgoing.get(current_id, []):
            included_edges.append(edge)
            target_id = edge.target_node_id
            included_nodes.add(current_id)
            included_nodes.add(target_id)
            if target_id not in visited:
                visited.add(target_id)
                frontier.append((target_id, current_depth + 1))

    return KnowledgeGraph(
        document_id=graph.document_id,
        nodes=[nodes_by_id[nid] for nid in included_nodes if nid in nodes_by_id],
        edges=included_edges,
    )
