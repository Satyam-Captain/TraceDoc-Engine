"""Deterministic matching between question graphs and knowledge graphs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.graph.models import GraphEdge, GraphNode, KnowledgeGraph, normalize_graph_label
from app.question_graph.models import UNKNOWN_SLOT_LABEL, QuestionGraph, QuestionNode

_SCORE_EXACT_LABEL = 5.0
_SCORE_SUBSTRING_LABEL = 3.0
_SCORE_RELATION = 5.0
_SCORE_CATEGORY_TYPE = 3.0
_SCORE_SOURCE_SENTENCE = 1.0
_SCORE_SECTION = 1.0

_CATEGORY_NODE_TYPES: dict[str, frozenset[str]] = {
    "architecture": frozenset({"architecture", "entity"}),
    "design_pattern": frozenset({"pattern", "entity"}),
    "pattern": frozenset({"pattern", "entity"}),
    "capability": frozenset({"capability", "entity"}),
    "requirement": frozenset({"requirement", "entity"}),
    "tool": frozenset({"tool", "entity", "building_block"}),
}

_DEFINITION_RELATIONS = frozenset(
    {"definition", "is_a", "refers_to", "mentions", "links_to"}
)

_PUNCTUATION_RE = re.compile(r"[^\w\s-]+")


@dataclass
class GraphMatch:
    """One deterministic match between a question graph and document graph."""

    matched: bool
    score: float
    matched_nodes: list[GraphNode] = field(default_factory=list)
    matched_edges: list[GraphEdge] = field(default_factory=list)
    answer_entities: list[str] = field(default_factory=list)
    explanation: str = ""
    source_sentences: list[str] = field(default_factory=list)


def _normalize_match_label(label: str) -> str:
    collapsed = normalize_graph_label(label)
    return _PUNCTUATION_RE.sub("", collapsed).strip()


def _label_variants(label: str) -> set[str]:
    base = _normalize_match_label(label)
    if not base:
        return set()
    variants = {base}
    if base.endswith("s") and len(base) > 3:
        variants.add(base[:-1])
    elif not base.endswith("s"):
        variants.add(f"{base}s")
    if base.endswith("ies") and len(base) > 4:
        variants.add(base[:-3] + "y")
    elif base.endswith("y"):
        variants.add(base[:-1] + "ies")
    return variants


def label_match_score(query_label: str, candidate_label: str) -> float:
    """
    Score label similarity deterministically.

    Exact normalized match scores highest; substring match scores lower.
    """
    query = _normalize_match_label(query_label)
    candidate = _normalize_match_label(candidate_label)
    if not query or not candidate:
        return 0.0
    if query == candidate:
        return _SCORE_EXACT_LABEL
    if query in candidate or candidate in query:
        return _SCORE_SUBSTRING_LABEL
    if _label_variants(query_label) & _label_variants(candidate_label):
        return _SCORE_EXACT_LABEL
    return 0.0


def _relation_key(relation: str | None) -> str:
    if not relation:
        return ""
    return relation.strip().lower().replace(" ", "_")


def _is_unknown_node(node: QuestionNode) -> bool:
    return node.node_type == "unknown" or node.label.strip() == UNKNOWN_SLOT_LABEL


def _question_entity_nodes(question_graph: QuestionGraph) -> list[QuestionNode]:
    return [
        node
        for node in question_graph.nodes
        if node.node_type == "entity" and not _is_unknown_node(node)
    ]


def _question_target_nodes(question_graph: QuestionGraph) -> list[QuestionNode]:
    return [
        node
        for node in question_graph.nodes
        if node.node_type == "relation_target" and not _is_unknown_node(node)
    ]


def _edge_bonus(edge: GraphEdge) -> float:
    bonus = 0.0
    if edge.source_sentence.strip():
        bonus += _SCORE_SOURCE_SENTENCE
    if edge.source_section.strip():
        bonus += _SCORE_SECTION
    return bonus


def _build_match(
    *,
    score: float,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    answer_entities: list[str],
    explanation: str,
) -> GraphMatch:
    sentences: list[str] = []
    seen_sentences: set[str] = set()
    for edge in edges:
        sentence = edge.source_sentence.strip()
        if sentence and sentence not in seen_sentences:
            seen_sentences.add(sentence)
            sentences.append(sentence)
    return GraphMatch(
        matched=True,
        score=score,
        matched_nodes=nodes,
        matched_edges=edges,
        answer_entities=answer_entities,
        explanation=explanation,
        source_sentences=sentences,
    )


def _match_forward_relation(
    question_graph: QuestionGraph,
    knowledge_graph: KnowledgeGraph,
) -> list[GraphMatch]:
    relation = _relation_key(question_graph.target_relation)
    if not relation:
        return []

    entities = _question_entity_nodes(question_graph)
    if not entities:
        return []

    nodes_by_id = knowledge_graph.node_by_id()
    matches: list[GraphMatch] = []

    for entity in entities:
        for edge in knowledge_graph.edges:
            if edge.relation != relation:
                continue
            source = nodes_by_id.get(edge.source_node_id)
            target = nodes_by_id.get(edge.target_node_id)
            if source is None or target is None:
                continue
            label_score = label_match_score(entity.label, source.label)
            if label_score <= 0:
                continue
            total = label_score + _SCORE_RELATION + _edge_bonus(edge)
            matches.append(
                _build_match(
                    score=total,
                    nodes=[source, target],
                    edges=[edge],
                    answer_entities=[target.label],
                    explanation=(
                        f"{source.label} --{relation}--> {target.label}"
                    ),
                )
            )
    return matches


def _match_reverse_relation(
    question_graph: QuestionGraph,
    knowledge_graph: KnowledgeGraph,
) -> list[GraphMatch]:
    relation = _relation_key(question_graph.target_relation)
    if not relation:
        return []

    targets = _question_target_nodes(question_graph)
    if not targets:
        return []

    nodes_by_id = knowledge_graph.node_by_id()
    matches: list[GraphMatch] = []

    for target_node in targets:
        for edge in knowledge_graph.edges:
            if edge.relation != relation:
                continue
            source = nodes_by_id.get(edge.source_node_id)
            target = nodes_by_id.get(edge.target_node_id)
            if source is None or target is None:
                continue
            label_score = label_match_score(target_node.label, target.label)
            if label_score <= 0:
                continue
            total = label_score + _SCORE_RELATION + _edge_bonus(edge)
            matches.append(
                _build_match(
                    score=total,
                    nodes=[source, target],
                    edges=[edge],
                    answer_entities=[source.label],
                    explanation=(
                        f"{source.label} --{relation}--> {target.label}"
                    ),
                )
            )
    return matches


def _node_matches_category(node: GraphNode, category: str) -> bool:
    category_key = _relation_key(category.replace("-", "_"))
    allowed_types = _CATEGORY_NODE_TYPES.get(
        category_key, frozenset({category_key, "entity"})
    )
    if node.node_type not in allowed_types:
        return False
    if node.node_type in {"document", "section", "concept"}:
        return False
    metadata_category = str(node.metadata.get("category", "")).lower()
    if metadata_category and (
        metadata_category == category_key
        or category_key in metadata_category
    ):
        return True
    label = node.normalized_label
    category_words = category_key.replace("_", " ")
    if category_key == "design_pattern":
        return "pattern" in label or "design pattern" in label
    if category_words in label or label in category_words:
        return True
    return node.node_type == category_key


def _match_category_query(
    question_graph: QuestionGraph,
    knowledge_graph: KnowledgeGraph,
) -> list[GraphMatch]:
    category = question_graph.target_category
    if not category:
        return []

    matches: list[GraphMatch] = []
    for node in knowledge_graph.nodes:
        if not _node_matches_category(node, category):
            continue
        score = _SCORE_CATEGORY_TYPE + _SCORE_EXACT_LABEL
        if node.source_section:
            score += _SCORE_SECTION
        matches.append(
            _build_match(
                score=score,
                nodes=[node],
                edges=[],
                answer_entities=[node.label],
                explanation=f"category node ({category}): {node.label}",
            )
        )
    return matches


def _match_definition_query(
    question_graph: QuestionGraph,
    knowledge_graph: KnowledgeGraph,
) -> list[GraphMatch]:
    relation = _relation_key(question_graph.target_relation)
    if relation != "definition":
        return []

    entities = _question_entity_nodes(question_graph)
    if not entities:
        return []

    nodes_by_id = knowledge_graph.node_by_id()
    matches: list[GraphMatch] = []

    for entity in entities:
        seed_nodes = [
            node
            for node in knowledge_graph.nodes
            if label_match_score(entity.label, node.label) > 0
        ]
        entity_matches: list[GraphMatch] = []
        for seed in seed_nodes:
            for edge in knowledge_graph.edges:
                if edge.source_node_id != seed.node_id:
                    continue
                if edge.relation not in _DEFINITION_RELATIONS:
                    continue
                target = nodes_by_id.get(edge.target_node_id)
                if target is None:
                    continue
                total = (
                    label_match_score(entity.label, seed.label)
                    + _SCORE_RELATION
                    + _edge_bonus(edge)
                )
                entity_matches.append(
                    _build_match(
                        score=total,
                        nodes=[seed, target],
                        edges=[edge],
                        answer_entities=[target.label],
                        explanation=(
                            f"{seed.label} --{edge.relation}--> {target.label}"
                        ),
                    )
                )
        if not entity_matches and seed_nodes:
            seed = seed_nodes[0]
            entity_matches.append(
                _build_match(
                    score=label_match_score(entity.label, seed.label)
                    + _SCORE_EXACT_LABEL,
                    nodes=[seed],
                    edges=[],
                    answer_entities=[seed.label],
                    explanation=f"definition seed node: {seed.label}",
                )
            )
        matches.extend(entity_matches)
    return matches


def _sort_matches(matches: list[GraphMatch]) -> list[GraphMatch]:
    return sorted(
        matches,
        key=lambda item: (
            -item.score,
            item.source_sentences[0] if item.source_sentences else "",
            item.answer_entities[0].lower() if item.answer_entities else "",
        ),
    )


def _dedupe_matches(matches: list[GraphMatch]) -> list[GraphMatch]:
    seen: set[tuple[str, str]] = set()
    unique: list[GraphMatch] = []
    for match in matches:
        entity_key = (
            match.answer_entities[0].lower() if match.answer_entities else ""
        )
        edge_key = match.matched_edges[0].edge_id if match.matched_edges else ""
        key = (entity_key, edge_key)
        if key in seen:
            continue
        seen.add(key)
        unique.append(match)
    return unique


def match_question_graph(
    question_graph: QuestionGraph,
    knowledge_graph: KnowledgeGraph,
    top_k: int = 5,
) -> list[GraphMatch]:
    """
    Match a question graph against a document knowledge graph.

    Returns ranked graph matches with answer entity candidates.
    """
    if top_k <= 0:
        return []
    if not knowledge_graph.nodes:
        return []

    matches: list[GraphMatch] = []

    if question_graph.target_category:
        matches.extend(_match_category_query(question_graph, knowledge_graph))
    elif _question_target_nodes(question_graph) and question_graph.target_relation:
        matches.extend(_match_reverse_relation(question_graph, knowledge_graph))
    elif _relation_key(question_graph.target_relation) == "definition":
        matches.extend(_match_definition_query(question_graph, knowledge_graph))
    elif question_graph.target_relation and _question_entity_nodes(question_graph):
        matches.extend(_match_forward_relation(question_graph, knowledge_graph))

    matches = _dedupe_matches(_sort_matches(matches))
    return matches[:top_k]


def graph_match_debug_lines(matches: list[GraphMatch]) -> list[str]:
    """Debug trace lines for graph matching in QA."""
    if not matches:
        return [
            "graph_matching_used=True",
            "graph_match_count=0",
            "graph_top_match=",
            "graph_answer_entities=[]",
        ]
    top = matches[0]
    entity_list = []
    seen: set[str] = set()
    for match in matches:
        for entity in match.answer_entities:
            key = entity.lower()
            if key in seen:
                continue
            seen.add(key)
            entity_list.append(entity)
    entity_preview = ", ".join(entity_list[:8])
    return [
        "graph_matching_used=True",
        f"graph_match_count={len(matches)}",
        f"graph_top_match={top.explanation}",
        f"graph_answer_entities=[{entity_preview}]",
    ]
