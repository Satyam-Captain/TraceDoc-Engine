"""Build deterministic question graphs from user questions."""

from __future__ import annotations

import hashlib
import re
from app.evidence.phrase_cleanup import clean_extracted_phrase
from app.indexing.normalizer import normalize_token
from app.indexing.tokenizer import tokenize
from app.query.models import (
    INTENT_DEFINITION_LOOKUP,
    INTENT_EXPLANATION_LOOKUP,
    INTENT_GENERAL_SEARCH,
    INTENT_LIST_REQUEST,
    QueryIntent,
)
from app.question_graph.intent_mapper import (
    fallback_relation_for_intent,
    intent_type_for_graph,
    is_definition_intent,
)
from app.question_graph.models import (
    UNKNOWN_SLOT_LABEL,
    QuestionEdge,
    QuestionGraph,
    QuestionNode,
    normalize_question_label,
)
from app.schema.models import DocumentSchema
from app.schema.query_category import resolve_query_target_category

_RELATION_FORWARD: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("uses", re.compile(r"(?i)^what\s+does\s+(.+?)\s+use\??\s*$")),
    ("contains", re.compile(r"(?i)^what\s+does\s+(.+?)\s+contain\??\s*$")),
    ("includes", re.compile(r"(?i)^what\s+does\s+(.+?)\s+include\??\s*$")),
    (
        "depends_on",
        re.compile(r"(?i)^what\s+does\s+(.+?)\s+depend\s+on\??\s*$"),
    ),
    ("refers_to", re.compile(r"(?i)^what\s+does\s+(.+?)\s+refer\s+to\??\s*$")),
    ("links_to", re.compile(r"(?i)^what\s+does\s+(.+?)\s+link\s+to\??\s*$")),
    ("implements", re.compile(r"(?i)^what\s+does\s+(.+?)\s+implement\??\s*$")),
)

_RELATION_REVERSE: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("implements", re.compile(r"(?i)^what\s+implements\s+(.+?)\??\s*$")),
)

_DEFINITION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)^what\s+is\s+(.+?)\??\s*$"),
    re.compile(r"(?i)^define\s+(.+?)\??\s*$"),
    re.compile(r"(?i)^explain\s+(.+?)\??\s*$"),
    re.compile(r"(?i)^what\s+does\s+(.+?)\s+mean\??\s*$"),
    re.compile(r"(?i)^describe\s+(.+?)\??\s*$"),
)

_CATEGORY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)^what\s+(?:are\s+)?(?:the\s+)?(?:different\s+)?(.+?)\s+(?:are\s+)?mentioned\b"
    ),
    re.compile(r"(?i)^what\s+(?:are\s+)?(?:the\s+)?(.+?)\s+(?:are\s+)?mentioned\b"),
    re.compile(r"(?i)^list\s+(?:all\s+)?(.+?)\s*$"),
    re.compile(r"(?i)^what\s+(?:are\s+)?(?:the\s+)?(.+?)\s+in\s+(?:the\s+)?(?:pdf|document)\b"),
)

_WEAK_QUESTION = re.compile(
    r"(?i)^(?:tell\s+me\s+something|anything|help|what\s+can\s+you\s+find)\b"
)


def _stable_node_id(label: str, node_type: str) -> str:
    payload = f"{node_type}:{normalize_question_label(label)}"
    return f"qnode-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:10]}"


def _normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip())


def _clean_entity(raw: str) -> str:
    cleaned = clean_extracted_phrase(raw.strip().rstrip("?"))
    return cleaned if cleaned else raw.strip()


def _is_plausible_entity(label: str) -> bool:
    if len(label) < 2 or len(label) > 120:
        return False
    tokens = [normalize_token(token) for token in tokenize(label)]
    tokens = [token for token in tokens if token]
    return len(tokens) >= 1


class _QuestionGraphBuilder:
    def __init__(self, question: str, intent: QueryIntent | None) -> None:
        self.question = question
        self.intent = intent
        self.intent_type = intent_type_for_graph(intent)
        self.nodes: dict[str, QuestionNode] = {}
        self.edges: list[QuestionEdge] = []
        self.unknown_slots: list[str] = []
        self.target_relation: str | None = None
        self.target_category: str | None = None

    def _add_node(self, label: str, node_type: str) -> QuestionNode:
        node_id = _stable_node_id(label, node_type)
        existing = self.nodes.get(node_id)
        if existing is not None:
            return existing
        node = QuestionNode(
            node_id=node_id,
            label=label,
            normalized_label=normalize_question_label(label),
            node_type=node_type,
        )
        self.nodes[node_id] = node
        return node

    def _unknown_node(self) -> QuestionNode:
        node = self._add_node(UNKNOWN_SLOT_LABEL, "unknown")
        if node.node_id not in self.unknown_slots:
            self.unknown_slots.append(node.node_id)
        return node

    def _add_query_edge(
        self,
        source: QuestionNode,
        relation: str,
        target: QuestionNode,
    ) -> None:
        relation_key = relation.strip().lower().replace(" ", "_")
        self.edges.append(
            QuestionEdge(
                source_node_id=source.node_id,
                relation=relation_key,
                target_node_id=target.node_id,
                is_query_edge=True,
            )
        )

    def _relation_forward(self, subject_label: str, relation: str) -> None:
        subject = self._add_node(subject_label, "entity")
        obj = self._unknown_node()
        self.target_relation = relation
        self._add_query_edge(subject, relation, obj)

    def _relation_reverse(self, object_label: str, relation: str) -> None:
        subject = self._unknown_node()
        obj = self._add_node(object_label, "relation_target")
        self.target_relation = relation
        self._add_query_edge(subject, relation, obj)

    def _definition_graph(self, entity_label: str) -> None:
        entity = self._add_node(entity_label, "entity")
        obj = self._unknown_node()
        self.intent_type = INTENT_DEFINITION_LOOKUP
        self.target_relation = "definition"
        self._add_query_edge(entity, "definition", obj)

    def _category_graph(self, category: str, *, relation: str = "mentions") -> None:
        category_label = category.replace("_", " ")
        subject = self._unknown_node()
        category_node = self._add_node(category_label, "category")
        self.target_category = category
        self.intent_type = INTENT_LIST_REQUEST
        self.target_relation = relation
        self._add_query_edge(subject, relation, category_node)

    def _generic_graph(self) -> None:
        self._unknown_node()
        self.intent_type = intent_type_for_graph(self.intent)
        relation = fallback_relation_for_intent(self.intent)
        if relation:
            self.target_relation = relation

    def build(self) -> QuestionGraph:
        return QuestionGraph(
            question=self.question,
            nodes=list(self.nodes.values()),
            edges=self.edges,
            intent_type=self.intent_type,
            target_relation=self.target_relation,
            target_category=self.target_category,
            unknown_slots=list(self.unknown_slots),
        )


def _match_relation_forward(normalized: str) -> tuple[str, str] | None:
    for relation, pattern in _RELATION_FORWARD:
        match = pattern.match(normalized)
        if not match:
            continue
        subject = _clean_entity(match.group(1))
        if _is_plausible_entity(subject):
            return subject, relation
    return None


def _match_relation_reverse(normalized: str) -> tuple[str, str] | None:
    for relation, pattern in _RELATION_REVERSE:
        match = pattern.match(normalized)
        if not match:
            continue
        obj = _clean_entity(match.group(1))
        if _is_plausible_entity(obj):
            return obj, relation
    return None


def _match_definition(normalized: str) -> str | None:
    for pattern in _DEFINITION_PATTERNS:
        match = pattern.match(normalized)
        if not match:
            continue
        entity = _clean_entity(match.group(1))
        if _is_plausible_entity(entity):
            return entity
    return None


def _category_from_question(
    normalized: str,
    schema: DocumentSchema | None,
) -> str | None:
    if schema is not None:
        resolved = resolve_query_target_category(normalized, schema)
        if resolved:
            return resolved

    lower = normalized.lower()
    if "design" in lower and "pattern" in lower:
        return "design_pattern"
    if "architect" in lower:
        return "architecture"
    if "capabilit" in lower:
        return "capability"

    for pattern in _CATEGORY_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        phrase = match.group(1).strip()
        if schema is not None:
            resolved = resolve_query_target_category(phrase, schema)
            if resolved:
                return resolved
        if "design" in phrase.lower() and "pattern" in phrase.lower():
            return "design_pattern"
        if "architect" in phrase.lower():
            return "architecture"
        if "capabilit" in phrase.lower():
            return "capability"
    return None


def _is_category_question(normalized: str) -> bool:
    lower = normalized.lower()
    if "mentioned" in lower and any(
        token in lower
        for token in (
            "architect",
            "pattern",
            "capabilit",
            "design",
            "different",
        )
    ):
        return True
    if lower.startswith("list "):
        return True
    return bool(
        re.search(
            r"(?i)what\s+(?:are\s+)?(?:the\s+)?(?:different\s+)?\w+",
            normalized,
        )
        and "mentioned" in lower
    )


def build_question_graph(
    question: str,
    query_intent: QueryIntent | None = None,
    schema: DocumentSchema | None = None,
) -> QuestionGraph:
    """
    Convert a user question into a symbolic query graph.

    Deterministic pattern rules only; no LLM or embeddings.
    """
    normalized = _normalize_question(question)
    builder = _QuestionGraphBuilder(question, query_intent)

    if not normalized:
        builder._generic_graph()
        return builder.build()

    if _WEAK_QUESTION.search(normalized):
        builder._generic_graph()
        return builder.build()

    forward = _match_relation_forward(normalized)
    if forward is not None:
        subject, relation = forward
        builder._relation_forward(subject, relation)
        return builder.build()

    reverse = _match_relation_reverse(normalized)
    if reverse is not None:
        obj, relation = reverse
        builder._relation_reverse(obj, relation)
        return builder.build()

    entity = _match_definition(normalized)
    if entity is not None:
        builder._definition_graph(entity)
        return builder.build()

    if is_definition_intent(query_intent) and query_intent is not None:
        for candidate in query_intent.entities:
            if _is_plausible_entity(candidate):
                builder._definition_graph(_clean_entity(candidate))
                return builder.build()

    if _is_category_question(normalized):
        category = _category_from_question(normalized, schema)
        if category:
            builder._category_graph(category)
            return builder.build()

    category = _category_from_question(normalized, schema)
    if category and any(
        token in normalized.lower()
        for token in ("what are", "list", "different", "mentioned")
    ):
        builder._category_graph(category)
        return builder.build()

    if query_intent is not None and query_intent.entities:
        entity = _clean_entity(query_intent.entities[0])
        if _is_plausible_entity(entity) and is_definition_intent(query_intent):
            builder._definition_graph(entity)
            return builder.build()

    builder._generic_graph()
    return builder.build()


def question_graph_debug_lines(graph: QuestionGraph) -> list[str]:
    """Debug trace lines for QA integration."""
    lines = [
        "question_graph_built=True",
        f"qgraph_nodes={len(graph.nodes)}",
        f"qgraph_edges={len(graph.edges)}",
    ]
    if graph.target_relation:
        lines.append(f"qgraph_target_relation={graph.target_relation}")
    if graph.target_category:
        lines.append(f"qgraph_target_category={graph.target_category}")
    return lines
