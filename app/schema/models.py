"""Deterministic document schema models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DiscoveredPattern:
    """A symbolic extraction grammar discovered from document text."""

    pattern_name: str
    category: str
    trigger_phrases: list[str] = field(default_factory=list)
    example_sentences: list[str] = field(default_factory=list)
    ordinal_type_phrase: str = ""
    sentence_templates: list[str] = field(default_factory=list)
    confidence_score: float = 0.0
    type_phrases: list[str] = field(default_factory=list)
    grammar_family: str = ""


@dataclass
class DiscoveredCategory:
    """A semantic category inferred from section headings."""

    name: str
    normalized_name: str
    source_section: str
    confidence_score: float
    discovered_patterns: list[str] = field(default_factory=list)


@dataclass
class GraphCandidate:
    """A deterministic subject-relation-object triple candidate."""

    subject: str
    relation: str
    object: str
    source_sentence: str
    confidence_score: float


@dataclass
class DocumentSchema:
    """Discovered semantic structure for one document."""

    document_id: int
    categories: list[DiscoveredCategory] = field(default_factory=list)
    discovered_patterns: list[DiscoveredPattern] = field(default_factory=list)
    graph_candidates: list[GraphCandidate] = field(default_factory=list)
    discovered_sections: list[str] = field(default_factory=list)


def discovered_pattern_to_dict(pattern: DiscoveredPattern) -> dict[str, Any]:
    return {
        "pattern_name": pattern.pattern_name,
        "category": pattern.category,
        "trigger_phrases": list(pattern.trigger_phrases),
        "example_sentences": list(pattern.example_sentences),
        "ordinal_type_phrase": pattern.ordinal_type_phrase,
        "sentence_templates": list(pattern.sentence_templates),
        "confidence_score": pattern.confidence_score,
        "type_phrases": list(pattern.type_phrases),
        "grammar_family": pattern.grammar_family,
    }


def discovered_pattern_from_dict(data: dict[str, Any]) -> DiscoveredPattern:
    return DiscoveredPattern(
        pattern_name=str(data["pattern_name"]),
        category=str(data["category"]),
        trigger_phrases=list(data.get("trigger_phrases", [])),
        example_sentences=list(data.get("example_sentences", [])),
        ordinal_type_phrase=str(data.get("ordinal_type_phrase", "")),
        sentence_templates=list(data.get("sentence_templates", [])),
        confidence_score=float(data.get("confidence_score", 0.0)),
        type_phrases=list(data.get("type_phrases", [])),
        grammar_family=str(data.get("grammar_family", "")),
    )


def discovered_category_to_dict(category: DiscoveredCategory) -> dict[str, Any]:
    return {
        "name": category.name,
        "normalized_name": category.normalized_name,
        "source_section": category.source_section,
        "confidence_score": category.confidence_score,
        "discovered_patterns": list(category.discovered_patterns),
    }


def discovered_category_from_dict(data: dict[str, Any]) -> DiscoveredCategory:
    return DiscoveredCategory(
        name=str(data["name"]),
        normalized_name=str(data["normalized_name"]),
        source_section=str(data["source_section"]),
        confidence_score=float(data.get("confidence_score", 0.0)),
        discovered_patterns=list(data.get("discovered_patterns", [])),
    )


def graph_candidate_to_dict(candidate: GraphCandidate) -> dict[str, Any]:
    return {
        "subject": candidate.subject,
        "relation": candidate.relation,
        "object": candidate.object,
        "source_sentence": candidate.source_sentence,
        "confidence_score": candidate.confidence_score,
    }


def graph_candidate_from_dict(data: dict[str, Any]) -> GraphCandidate:
    return GraphCandidate(
        subject=str(data["subject"]),
        relation=str(data["relation"]),
        object=str(data["object"]),
        source_sentence=str(data["source_sentence"]),
        confidence_score=float(data.get("confidence_score", 0.0)),
    )


def document_schema_to_dict(schema: DocumentSchema) -> dict[str, Any]:
    return {
        "document_id": schema.document_id,
        "categories": [discovered_category_to_dict(item) for item in schema.categories],
        "discovered_patterns": [
            discovered_pattern_to_dict(item) for item in schema.discovered_patterns
        ],
        "graph_candidates": [
            graph_candidate_to_dict(item) for item in schema.graph_candidates
        ],
        "discovered_sections": list(schema.discovered_sections),
    }


def document_schema_from_dict(data: dict[str, Any]) -> DocumentSchema:
    return DocumentSchema(
        document_id=int(data["document_id"]),
        categories=[
            discovered_category_from_dict(item) for item in data.get("categories", [])
        ],
        discovered_patterns=[
            discovered_pattern_from_dict(item)
            for item in data.get("discovered_patterns", [])
        ],
        graph_candidates=[
            graph_candidate_from_dict(item) for item in data.get("graph_candidates", [])
        ],
        discovered_sections=list(data.get("discovered_sections", [])),
    )
