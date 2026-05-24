"""Compose deterministic answers from graph match results."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.evidence.models import ANSWER_MODE_GRAPH_STRUCTURED, EvidenceCard
from app.evidence.selector import classify_confidence, format_citation
from app.graph.matcher import GraphMatch
from app.question_graph.models import QuestionGraph, QuestionNode

DEFAULT_GRAPH_ANSWER_THRESHOLD = 8.0

_ENUMERATION_CATEGORIES = frozenset(
    {"architecture", "design_pattern", "pattern", "capability"}
)

_RELATION_DISPLAY: dict[str, str] = {
    "uses": "uses",
    "contains": "contains",
    "includes": "includes",
    "depends_on": "depends on",
    "refers_to": "refers to",
    "links_to": "links to",
    "implements": "implements",
    "mentions": "mentions",
    "definition": "definition",
    "is_a": "is",
}

GRAPH_ANSWER_EXPLANATION = (
    "This response is based on deterministic graph matching between the "
    "question structure and the document knowledge graph. No AI-generated "
    "answer was produced."
)


@dataclass
class GraphAnswer:
    """Structured answer derived from knowledge graph matches."""

    answer_mode: str = ANSWER_MODE_GRAPH_STRUCTURED
    structured_answer: str = ""
    matched_entities: list[str] = field(default_factory=list)
    source_sentences: list[str] = field(default_factory=list)
    confidence_score: float = 0.0
    explanation: str = GRAPH_ANSWER_EXPLANATION


def _is_unknown_node(node: QuestionNode) -> bool:
    return node.node_type == "unknown" or node.label.strip() == "?"


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


def _relation_display(relation: str | None) -> str:
    if not relation:
        return "relates to"
    key = relation.strip().lower().replace(" ", "_")
    return _RELATION_DISPLAY.get(key, key.replace("_", " "))


def _collect_entities(matches: list[GraphMatch], max_items: int) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for match in matches:
        for entity in match.answer_entities:
            key = entity.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(entity)
            if len(ordered) >= max_items:
                return ordered
    return ordered


def _collect_source_sentences(matches: list[GraphMatch]) -> list[str]:
    sentences: list[str] = []
    seen: set[str] = set()
    for match in matches:
        for sentence in match.source_sentences:
            cleaned = sentence.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            sentences.append(cleaned)
    return sentences


def _numbered_list_body(items: list[str]) -> str:
    lines = []
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item}")
    return "\n".join(lines)


def _compose_relation_answer(
    question_graph: QuestionGraph,
    matches: list[GraphMatch],
    entities: list[str],
    *,
    reverse: bool = False,
) -> str:
    relation = _relation_display(question_graph.target_relation)
    if reverse:
        targets = _question_target_nodes(question_graph)
        target_label = targets[0].label if targets else "the target"
        intro = f"The following items implement {target_label}:"
        body = _numbered_list_body(entities)
        return f"{intro}\n{body}"

    subjects = _question_entity_nodes(question_graph)
    subject_label = subjects[0].label if subjects else "The subject"
    intro = f"{subject_label} {relation}:"
    body = _numbered_list_body(entities)
    return f"{intro}\n{body}"


def _compose_category_answer(
    question_graph: QuestionGraph,
    entities: list[str],
) -> str:
    category = (question_graph.target_category or "item").replace("_", " ")
    if len(entities) == 1:
        intro = f"The document mentions this {category}:"
    else:
        intro = f"The document mentions these {category} items:"
    return f"{intro}\n{_numbered_list_body(entities)}"


def compose_graph_answer(
    question_graph: QuestionGraph,
    graph_matches: list[GraphMatch],
    max_items: int = 10,
    *,
    score_threshold: float = DEFAULT_GRAPH_ANSWER_THRESHOLD,
) -> GraphAnswer | None:
    """
    Build a graph-based structured answer when matches are strong enough.

    Returns None when there are no matches, score is below threshold,
    or no answer entities were extracted.
    """
    if not graph_matches:
        return None

    top_score = graph_matches[0].score
    if top_score < score_threshold:
        return None

    entities = _collect_entities(graph_matches, max_items)
    if not entities:
        return None

    source_sentences = _collect_source_sentences(graph_matches)
    relation_key = (question_graph.target_relation or "").replace(" ", "_")

    if question_graph.target_category and relation_key == "mentions":
        structured = _compose_category_answer(question_graph, entities)
    elif _question_target_nodes(question_graph) and relation_key:
        structured = _compose_relation_answer(
            question_graph, graph_matches, entities, reverse=True
        )
    elif relation_key and _question_entity_nodes(question_graph):
        structured = _compose_relation_answer(
            question_graph, graph_matches, entities, reverse=False
        )
    elif question_graph.target_category:
        structured = _compose_category_answer(question_graph, entities)
    else:
        structured = _numbered_list_body(entities)

    if source_sentences:
        structured = (
            f"{structured}\n\nSupporting source sentences:\n"
            + "\n".join(f"- {sentence}" for sentence in source_sentences[:6])
        )

    return GraphAnswer(
        answer_mode=ANSWER_MODE_GRAPH_STRUCTURED,
        structured_answer=structured,
        matched_entities=entities,
        source_sentences=source_sentences,
        confidence_score=top_score,
        explanation=GRAPH_ANSWER_EXPLANATION,
    )


def is_relationship_style_question(question_graph: QuestionGraph) -> bool:
    """True when the question graph targets a relation query (not list enumeration)."""
    if not question_graph.target_relation:
        return False
    relation = question_graph.target_relation.replace(" ", "_")
    if relation == "definition":
        return False
    if question_graph.target_category in _ENUMERATION_CATEGORIES:
        return False
    if question_graph.target_category and relation == "mentions":
        return False
    return True


def should_use_graph_answer(
    question_graph: QuestionGraph,
    graph_answer: GraphAnswer | None,
) -> bool:
    """Return True when graph answer should replace tree/section structured path."""
    if graph_answer is None:
        return False
    if not is_relationship_style_question(question_graph):
        return False
    return bool(graph_answer.matched_entities)


def graph_matches_to_evidence_cards(
    graph_matches: list[GraphMatch],
    document_name: str,
    max_cards: int = 3,
) -> list[EvidenceCard]:
    """Build evidence cards from graph match source sentences and edge metadata."""
    cards: list[EvidenceCard] = []
    seen: set[str] = set()

    for match_index, match in enumerate(graph_matches):
        terms = [term for term in match.answer_entities if term]
        for sentence_index, sentence in enumerate(match.source_sentences):
            normalized = sentence.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)

            section_title = ""
            start_line = 0
            end_line = 0
            if match.matched_edges:
                edge = match.matched_edges[0]
                section_title = edge.source_section or section_title
            if match.matched_nodes:
                node = match.matched_nodes[0]
                if node.source_line_start:
                    start_line = int(node.source_line_start)
                if node.source_line_end:
                    end_line = int(node.source_line_end)
                if not section_title and node.source_section:
                    section_title = node.source_section

            score = match.score - (sentence_index * 0.05)
            cards.append(
                EvidenceCard(
                    chunk_id=f"graph-match-{match_index}-{sentence_index}",
                    document_name=document_name,
                    section_title=section_title or None,
                    start_line=start_line,
                    end_line=end_line,
                    snippet=sentence,
                    matched_terms=terms,
                    score=score,
                    confidence=classify_confidence(score, len(terms)),
                    why_matched=(
                        "Matched by deterministic graph matching: "
                        f"{match.explanation}"
                    ),
                    citation=format_citation(
                        document_name,
                        start_line,
                        end_line,
                        section_title or None,
                    ),
                )
            )
            if len(cards) >= max_cards:
                return cards

    return cards


def graph_answer_debug_lines(
    graph_answer: GraphAnswer | None,
    *,
    candidate: bool,
    used: bool,
) -> list[str]:
    """Debug trace lines for graph answer composition."""
    lines = [
        f"graph_answer_candidate={str(candidate)}",
        f"graph_answer_used={str(used)}",
    ]
    if graph_answer is None:
        lines.append("graph_answer_confidence=0.00")
        lines.append("graph_answer_entities=[]")
        return lines
    preview = ", ".join(graph_answer.matched_entities[:8])
    lines.append(f"graph_answer_confidence={graph_answer.confidence_score:.2f}")
    lines.append(f"graph_answer_entities=[{preview}]")
    return lines
