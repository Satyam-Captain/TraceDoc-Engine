"""Build a deterministic knowledge graph from the semantic tree and schema."""

from __future__ import annotations

import hashlib

from app.evidence.extraction_runtime import execute_discovered_grammar_with_result
from app.evidence.pattern_extractor import extract_enumerated_phrases
from app.graph.extractor import (
    ExtractedRelation,
    extract_relations_from_sentence,
    stable_relation_id,
)
from app.graph.models import GraphEdge, GraphNode, KnowledgeGraph, normalize_graph_label
from app.schema.models import DocumentSchema, GraphCandidate
from app.schema.registry import primary_grammar_for_category
from app.tree.models import DocumentTree, TreeNode
from app.tree.traversal import get_section_sentences, get_section_text, iter_nodes


def _stable_node_id(label: str, node_type: str) -> str:
    payload = f"{node_type}:{normalize_graph_label(label)}"
    return f"node-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:12]}"


def _category_node_type(category: str) -> str:
    normalized = category.strip().lower()
    mapping = {
        "architecture": "architecture",
        "design_pattern": "pattern",
        "pattern": "pattern",
        "capability": "capability",
        "requirement": "requirement",
        "tool": "tool",
        "building_block": "tool",
    }
    return mapping.get(normalized, "entity")


class _GraphBuilderState:
    """Mutable registry while assembling one knowledge graph."""

    def __init__(self, document_id: int) -> None:
        self.document_id = document_id
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self._edge_keys: set[tuple[str, str, str]] = set()

    def add_node(
        self,
        label: str,
        node_type: str,
        *,
        source_section: str | None = None,
        source_line_start: int | None = None,
        source_line_end: int | None = None,
        metadata: dict | None = None,
    ) -> GraphNode:
        cleaned = label.strip()
        node_id = _stable_node_id(cleaned, node_type)
        existing = self.nodes.get(node_id)
        if existing is not None:
            return existing
        node = GraphNode(
            node_id=node_id,
            label=cleaned,
            normalized_label=normalize_graph_label(cleaned),
            node_type=node_type,
            source_section=source_section,
            source_line_start=source_line_start,
            source_line_end=source_line_end,
            metadata=dict(metadata or {}),
        )
        self.nodes[node_id] = node
        return node

    def add_edge(
        self,
        source: GraphNode,
        relation: str,
        target: GraphNode,
        *,
        source_sentence: str = "",
        source_section: str = "",
        confidence_score: float = 0.85,
        metadata: dict | None = None,
    ) -> None:
        relation_key = relation.strip().lower().replace(" ", "_")
        edge_key = (source.node_id, relation_key, target.node_id)
        if edge_key in self._edge_keys:
            return
        self._edge_keys.add(edge_key)
        edge_id = f"edge-{stable_relation_id(source.label, relation_key, target.label)}"
        self.edges.append(
            GraphEdge(
                edge_id=edge_id,
                source_node_id=source.node_id,
                relation=relation_key,
                target_node_id=target.node_id,
                source_sentence=source_sentence,
                source_section=source_section,
                confidence_score=confidence_score,
                metadata=dict(metadata or {}),
            )
        )

    def add_relation_triple(
        self,
        relation: ExtractedRelation,
        *,
        source_section: str,
        source_line_start: int,
        source_line_end: int,
        subject_type: str = "entity",
        object_type: str = "entity",
    ) -> None:
        subject = self.add_node(
            relation.subject,
            subject_type,
            source_section=source_section,
            source_line_start=source_line_start,
            source_line_end=source_line_end,
        )
        obj = self.add_node(
            relation.object,
            object_type,
            source_section=source_section,
            source_line_start=source_line_start,
            source_line_end=source_line_end,
        )
        self.add_edge(
            subject,
            relation.relation,
            obj,
            source_sentence=relation.source_sentence,
            source_section=source_section,
            confidence_score=relation.confidence_score,
        )


def _section_title_for_node(node: TreeNode, tree: DocumentTree) -> str:
    return (node.title or node.text or "").strip()


def _entities_from_schema_grammar(
    section_title: str,
    section_text: str,
    schema: DocumentSchema,
) -> list[tuple[str, str]]:
    """Return (entity_label, category) from grammar extraction on section text."""
    entities: list[tuple[str, str]] = []
    seen: set[str] = set()
    for category in schema.categories:
        grammar = primary_grammar_for_category(schema, category.normalized_name)
        if grammar is None:
            continue
        if category.source_section and category.source_section.lower() not in section_title.lower():
            if section_title.lower() not in category.source_section.lower():
                continue
        result = execute_discovered_grammar_with_result(
            section_text,
            grammar,
            category=category.normalized_name,
            section_title=section_title,
        )
        for entity in result.validated_entities or result.entities:
            key = entity.lower()
            if key in seen:
                continue
            seen.add(key)
            entities.append((entity, category.normalized_name))

    for phrase in extract_enumerated_phrases(section_text, "architecture", document_schema=schema):
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            entities.append((phrase, "architecture"))
    return entities


def _add_schema_graph_candidates(
    state: _GraphBuilderState,
    schema: DocumentSchema,
) -> None:
    for candidate in schema.graph_candidates:
        if not isinstance(candidate, GraphCandidate):
            continue
        relation = candidate.relation.strip().lower().replace(" ", "_")
        state.add_relation_triple(
            ExtractedRelation(
                subject=candidate.subject,
                relation=relation,
                object=candidate.object,
                source_sentence=candidate.source_sentence,
                confidence_score=candidate.confidence_score,
            ),
            source_section="",
            source_line_start=0,
            source_line_end=0,
        )


def build_knowledge_graph(
    document_id: int,
    tree: DocumentTree,
    schema: DocumentSchema | None = None,
) -> KnowledgeGraph:
    """
    Build a symbolic knowledge graph from a document tree and optional schema.

    Creates document/section structure, grammar entities, and rule-based relations.
    """
    state = _GraphBuilderState(document_id)
    document_label = tree.document_name or tree.root.title or "document"
    document_node = state.add_node(
        document_label,
        "document",
        source_line_start=tree.root.start_line,
        source_line_end=tree.root.end_line,
        metadata={"tree_node_id": tree.root.node_id},
    )

    section_nodes: list[tuple[TreeNode, GraphNode]] = []
    for node in iter_nodes(tree.root):
        if node.node_type != "section":
            continue
        title = _section_title_for_node(node, tree)
        section_graph_node = state.add_node(
            title,
            "section",
            source_section=title,
            source_line_start=node.start_line,
            source_line_end=node.end_line,
            metadata={"tree_node_id": node.node_id},
        )
        section_nodes.append((node, section_graph_node))
        state.add_edge(
            document_node,
            "contains",
            section_graph_node,
            source_section=title,
            confidence_score=0.95,
        )

        section_text = get_section_text(node)
        if schema is not None and section_text.strip():
            for entity_label, category in _entities_from_schema_grammar(
                title, section_text, schema
            ):
                entity_node = state.add_node(
                    entity_label,
                    _category_node_type(category),
                    source_section=title,
                    source_line_start=node.start_line,
                    source_line_end=node.end_line,
                    metadata={"category": category},
                )
                state.add_edge(
                    section_graph_node,
                    "contains",
                    entity_node,
                    source_section=title,
                    confidence_score=0.9,
                )

        for sentence in get_section_sentences(node):
            for relation in extract_relations_from_sentence(sentence):
                state.add_relation_triple(
                    relation,
                    source_section=title,
                    source_line_start=node.start_line,
                    source_line_end=node.end_line,
                )

    if schema is not None:
        _add_schema_graph_candidates(state, schema)
        for category in schema.categories:
            section_title = category.source_section
            if not section_title:
                continue
            category_node = state.add_node(
                category.name,
                "concept",
                source_section=section_title,
                metadata={"normalized_category": category.normalized_name},
            )
            for _tree_node, section_graph_node in section_nodes:
                if section_title.lower() in (section_graph_node.label or "").lower():
                    state.add_edge(
                        section_graph_node,
                        "mentions",
                        category_node,
                        source_section=section_title,
                        confidence_score=category.confidence_score,
                    )

    return KnowledgeGraph(
        document_id=document_id,
        nodes=list(state.nodes.values()),
        edges=state.edges,
    )
