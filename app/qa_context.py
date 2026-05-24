"""Unified answer context for section-level symbolic QA."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.evidence.composer import EVIDENCE_EXPLANATION, NO_EVIDENCE_EXPLANATION, NO_EVIDENCE_MESSAGE
from app.evidence.extraction_runtime import (
    GrammarExecutionResult,
    execute_discovered_grammar_with_result,
)
from app.evidence.models import (
    ANSWER_MODE_EVIDENCE_ONLY,
    ANSWER_MODE_NO_EVIDENCE,
    ANSWER_MODE_STRUCTURED_EXTRACTIVE,
    AnswerPackage,
)
from app.evidence.selector import select_evidence_cards
from app.evidence.structured_composer import (
    compose_structured_answer_from_context,
    grammar_execution_debug_lines,
)
from app.retrieval.models import SearchResult
from app.retrieval.section_searcher import collect_section_chunks, extract_topic_terms
from app.schema.models import DiscoveredPattern, DocumentSchema
from app.schema.registry import primary_grammar_for_category
from app.structure.chunk_section import (
    chunk_overlaps_section,
    clip_chunk_text_to_section,
)
from app.structure.models import DocumentChunk
from app.storage.models import StoredSection

SHORT_EXTRACTION_THRESHOLD = 120


@dataclass
class AnswerContext:
    """Single source of truth for section-level retrieval, extraction, and composition."""

    question: str
    document_name: str
    target_category: str | None = None
    selected_section: StoredSection | None = None
    selected_section_title: str | None = None
    selected_section_range: tuple[int, int] | None = None
    collected_chunks: list[DocumentChunk] = field(default_factory=list)
    primary_section_text: str = ""
    extraction_text: str = ""
    context_expansion_applied: bool = False
    extraction_text_line_range: tuple[int, int] = (0, 0)
    grammar: DiscoveredPattern | None = None
    grammar_result: GrammarExecutionResult | None = None
    raw_extracted_entities: list[str] = field(default_factory=list)
    validated_entities: list[str] = field(default_factory=list)
    rejected_entities: list[str] = field(default_factory=list)
    structured_answer_generated: bool = False
    structured_extraction_failed_reason: str | None = None
    search_results: list[SearchResult] = field(default_factory=list)
    section_score: float = 0.0
    debug_trace: list[str] = field(default_factory=list)


def _heading_like(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith("#"):
        return True
    lines = [line for line in stripped.splitlines() if line.strip()]
    if len(lines) == 1 and len(stripped) < 80:
        words = stripped.split()
        if len(words) <= 10 and stripped[0].isupper():
            return True
    return False


def _needs_section_expansion(text: str, chunks: list[DocumentChunk]) -> bool:
    if not text.strip():
        return True
    if len(text.strip()) < SHORT_EXTRACTION_THRESHOLD:
        return True
    if chunks and all(chunk.chunk_type == "section" for chunk in chunks):
        return True
    return _heading_like(text)


def build_section_extraction_text(
    section: StoredSection,
    chunks: list[DocumentChunk],
) -> tuple[str, list[DocumentChunk], tuple[int, int], bool]:
    """
    Merge in-section chunk text (clipped to section lines).

    When the merge is short or heading-only, include every overlapping chunk
    clipped to the section range so extraction matches expanded evidence.
    """
    section_chunks = collect_section_chunks(section, chunks, max_chunks=50)
    if not section_chunks:
        section_chunks = [
            chunk for chunk in sorted(chunks, key=lambda c: (c.start_line, c.chunk_id))
            if chunk_overlaps_section(chunk, section)
        ]

    def _merge(chunk_list: list[DocumentChunk]) -> str:
        parts = [
            clip_chunk_text_to_section(chunk, section).strip()
            for chunk in chunk_list
        ]
        return "\n\n".join(part for part in parts if part)

    primary = _merge(section_chunks)
    expanded = False
    if _needs_section_expansion(primary, section_chunks):
        overlap_chunks = [
            chunk
            for chunk in sorted(chunks, key=lambda c: (c.start_line, c.chunk_id))
            if chunk_overlaps_section(chunk, section)
        ]
        overlap_text = _merge(overlap_chunks)
        if len(overlap_text) > len(primary):
            primary = overlap_text
            section_chunks = overlap_chunks
            expanded = True

    if section_chunks:
        start_line = max(section.start_line, min(c.start_line for c in section_chunks))
        end_line = min(section.end_line, max(c.end_line for c in section_chunks))
    else:
        start_line = section.start_line
        end_line = section.end_line

    return primary, section_chunks, (start_line, end_line), expanded


def _run_category_extraction(
    extraction_text: str,
    *,
    target_category: str,
    document_schema: DocumentSchema,
    section_title: str,
) -> tuple[DiscoveredPattern | None, GrammarExecutionResult | None]:
    grammar = primary_grammar_for_category(document_schema, target_category)
    if grammar is None:
        return None, None

    from app.evidence.extraction_validator import (
        build_extraction_validation_registry,
        filter_text_to_category_sentences,
    )

    scoped = filter_text_to_category_sentences(
        extraction_text,
        target_category,
        document_schema,
    )
    grammar_text = scoped or extraction_text
    validation_registry = build_extraction_validation_registry(
        document_schema,
        full_text_by_category={target_category: grammar_text},
    )
    result = execute_discovered_grammar_with_result(
        grammar_text,
        grammar,
        category=target_category,
        validation_registry=validation_registry,
        section_title=section_title,
    )
    return grammar, result


def build_section_answer_context(
    *,
    question: str,
    document_name: str,
    section: StoredSection,
    chunks: list[DocumentChunk],
    section_score: float,
    target_category: str | None,
    document_schema: DocumentSchema | None,
) -> AnswerContext:
    """Build a unified context after section selection."""
    extraction_text, collected_chunks, line_range, expanded = build_section_extraction_text(
        section, chunks
    )
    preview = extraction_text.replace("\n", " ").strip()[:160]
    if len(extraction_text) > 160:
        preview += "..."

    ctx = AnswerContext(
        question=question,
        document_name=document_name,
        target_category=target_category,
        selected_section=section,
        selected_section_title=section.title,
        selected_section_range=(section.start_line, section.end_line),
        collected_chunks=collected_chunks,
        primary_section_text=extraction_text,
        extraction_text=extraction_text,
        context_expansion_applied=expanded,
        extraction_text_line_range=line_range,
        section_score=section_score,
    )
    ctx.debug_trace.extend(
        [
            f"selected_section={section.title}",
            f"selected_section_range={section.start_line}-{section.end_line}",
            f"collected_section_chunks={len(collected_chunks)}",
            f"collected_chunk_ranges=[{','.join(f'{c.start_line}-{c.end_line}' for c in collected_chunks)}]",
            f"context_expansion_applied={expanded}",
            f"extraction_text_line_range={line_range[0]}-{line_range[1]}",
            f"extraction_text_preview={preview!r}",
        ]
    )

    if document_schema is not None and target_category:
        grammar, grammar_result = _run_category_extraction(
            extraction_text,
            target_category=target_category,
            document_schema=document_schema,
            section_title=section.title,
        )
        ctx.grammar = grammar
        ctx.grammar_result = grammar_result
        if grammar is not None:
            ctx.debug_trace.append(f"grammar_used={grammar.pattern_name}")
            ctx.debug_trace.append(
                f"grammar_confidence={grammar.confidence_score:.2f}"
            )
            template_preview = ";".join(grammar.sentence_templates[:4])
            ctx.debug_trace.append(
                f"grammar_sentence_templates=[{template_preview}]"
            )
        if grammar_result is not None:
            ctx.debug_trace.extend(grammar_execution_debug_lines(grammar_result))
            ctx.raw_extracted_entities = list(grammar_result.entities)
            ctx.validated_entities = list(
                grammar_result.validated_entities or grammar_result.entities
            )
            ctx.rejected_entities = list(grammar_result.rejected_entities)

    query_terms = sorted(extract_topic_terms(question))
    matched_terms = [
        term
        for term in query_terms
        if term in extraction_text.lower()
    ]
    expansion_note = ""
    if expanded:
        expansion_note = (
            " Context expanded from all chunks overlapping the selected section range."
        )
    why_matched = (
        f"Matched by section-level retrieval from section '{section.title}'."
        f"{expansion_note}"
    )
    ctx.search_results = [
        SearchResult(
            chunk_id=collected_chunks[0].chunk_id if collected_chunks else section.section_id,
            document_name=document_name,
            text=extraction_text,
            score=section_score + 0.5,
            matched_terms=matched_terms,
            term_scores={term: 1.0 for term in matched_terms},
            start_line=line_range[0],
            end_line=line_range[1],
            section_title=section.title,
            section_id=section.section_id,
            chunk_type="section_bundle",
            why_matched=why_matched,
        )
    ]
    return ctx


def finalize_answer_context(
    ctx: AnswerContext,
    *,
    document_schema: DocumentSchema | None = None,
    max_cards: int = 3,
) -> AnswerPackage:
    """Compose evidence cards and structured answer from one AnswerContext."""
    if not ctx.extraction_text.strip():
        ctx.structured_extraction_failed_reason = "empty_extraction_text"
        ctx.debug_trace.append(
            f"structured_extraction_failed_reason={ctx.structured_extraction_failed_reason}"
        )
        ctx.debug_trace.append("structured_answer_generated=False")
        return AnswerPackage(
            question=ctx.question,
            answer_mode=ANSWER_MODE_NO_EVIDENCE,
            cards=[],
            no_evidence_message=NO_EVIDENCE_MESSAGE,
            explanation=NO_EVIDENCE_EXPLANATION,
        )

    structured = compose_structured_answer_from_context(
        ctx,
        document_schema=document_schema,
    )
    cards = select_evidence_cards(
        question=ctx.question,
        search_results=ctx.search_results,
        max_cards=max_cards,
    )

    if structured:
        ctx.structured_answer_generated = True
        ctx.structured_extraction_failed_reason = None
        ctx.debug_trace.append("structured_answer_generated=True")
        _STRUCTURED_SUFFIX = (
            " A structured extractive summary was composed only from retrieved evidence text."
        )

        return AnswerPackage(
            question=ctx.question,
            answer_mode=ANSWER_MODE_STRUCTURED_EXTRACTIVE,
            cards=cards,
            structured_answer=structured,
            no_evidence_message=None,
            explanation=EVIDENCE_EXPLANATION + _STRUCTURED_SUFFIX,
        )

    reason = ctx.structured_extraction_failed_reason or "no_entities_extracted"
    ctx.structured_extraction_failed_reason = reason
    ctx.structured_answer_generated = False
    ctx.debug_trace.append("structured_answer_generated=False")
    ctx.debug_trace.append(f"structured_extraction_failed_reason={reason}")

    if not cards:
        return AnswerPackage(
            question=ctx.question,
            answer_mode=ANSWER_MODE_NO_EVIDENCE,
            cards=[],
            no_evidence_message=NO_EVIDENCE_MESSAGE,
            explanation=NO_EVIDENCE_EXPLANATION,
        )

    return AnswerPackage(
        question=ctx.question,
        answer_mode=ANSWER_MODE_EVIDENCE_ONLY,
        cards=cards,
        structured_answer=None,
        no_evidence_message=None,
        explanation=EVIDENCE_EXPLANATION,
    )


def context_debug_trace(ctx: AnswerContext) -> list[str]:
    """Return debug lines describing unified extraction state."""
    lines = list(ctx.debug_trace)
    if ctx.target_category:
        lines.append(f"target_category={ctx.target_category}")
    if ctx.validated_entities:
        preview = ", ".join(ctx.validated_entities[:8])
        lines.append(f"validated_entities=[{preview}]")
    if ctx.rejected_entities:
        preview = ", ".join(ctx.rejected_entities[:8])
        lines.append(f"rejected_entities=[{preview}]")
    lines.append(f"structured_answer_generated={ctx.structured_answer_generated}")
    if ctx.structured_extraction_failed_reason:
        lines.append(
            f"structured_extraction_failed_reason={ctx.structured_extraction_failed_reason}"
        )
    return lines
