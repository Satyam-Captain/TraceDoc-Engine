"""Document question-answer orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.audit import log_audit_event
from app.evidence import compose_answer_package, compose_structured_answer
from app.evidence.extraction_runtime import execute_discovered_grammar_with_result
from app.evidence.structured_composer import (
    architecture_evidence_text,
    architecture_extraction_trace,
    grammar_execution_debug_lines,
)
from app.evidence.composer import NO_EVIDENCE_EXPLANATION, NO_EVIDENCE_MESSAGE
from app.evidence.models import (
    ANSWER_MODE_STRUCTURED_EXTRACTIVE,
    AnswerPackage,
    EvidenceCard,
)
from app.query import (
    build_retrieval_query,
    compose_intent_explanation,
    interpret_query,
)
from app.query.models import QueryIntent
from app.retrieval import (
    collect_section_chunks,
    derive_sections_from_chunks,
    extract_topic_terms,
    find_relevant_sections,
    score_section_relevance,
    search_chunks,
    should_use_section_retrieval,
)
from app.structure.hierarchy import infer_section_ranges
from app.structure.models import DocumentChunk, DocumentSection
from app.structure.section_assignment import reassign_chunk_sections
from app.retrieval.models import SearchResult
from app.schema.discovery import format_category_normalization_trace, match_question_to_schema_category
from app.schema.query_category import resolve_query_target_category
from app.schema.registry import (
    build_pattern_registry,
    primary_grammar_for_category,
)
from app.schema.models import DocumentSchema
from app.storage import (
    document_has_index,
    get_chunks_for_document,
    get_document_by_id,
    get_sections_for_document,
    list_documents,
    load_bm25_statistics,
    load_document_schema,
    load_index_for_document,
)
from app.storage.models import StoredSection


@dataclass
class DocumentQAResult:
    """Evidence-only answer for a question against one stored document."""

    question: str
    document_id: int
    document_name: str
    answer_mode: str
    cards: list[EvidenceCard] = field(default_factory=list)
    structured_answer: str | None = None
    no_evidence_message: str | None = None
    explanation: str = ""
    query_intent: QueryIntent | None = None
    section_retrieval_used: bool = False
    retrieved_section_title: str | None = None
    retrieval_strategy: str = "BM25_CHUNK"
    debug_trace: list[str] = field(default_factory=list)


RETRIEVAL_STRATEGY_SECTION = "SECTION_LEVEL"
RETRIEVAL_STRATEGY_BM25 = "BM25_CHUNK"


@dataclass
class AllDocumentsQAResult:
    """Evidence-only answer aggregated across all stored documents."""

    question: str
    answer_mode: str
    cards: list[EvidenceCard] = field(default_factory=list)
    structured_answer: str | None = None
    no_evidence_message: str | None = None
    explanation: str = ""
    document_count: int = 0
    section_retrieval_used: bool = False
    retrieved_section_title: str | None = None
    retrieval_strategy: str = "BM25_CHUNK"


STRUCTURED_ANSWER_EXPLANATION_SUFFIX = (
    " A structured extractive summary was composed only from retrieved evidence text."
)


def _apply_structured_answer(
    package: AnswerPackage,
    question: str,
    document_schema: DocumentSchema | None = None,
    *,
    target_category: str | None = None,
) -> AnswerPackage:
    """Upgrade answer package to STRUCTURED_EXTRACTIVE when rules match evidence."""
    if package.answer_mode == "NO_EVIDENCE" or not package.cards:
        return package

    structured = compose_structured_answer(
        question,
        package.cards,
        document_schema=document_schema,
        target_category=target_category,
    )
    if not structured:
        return package

    explanation = package.explanation + STRUCTURED_ANSWER_EXPLANATION_SUFFIX
    return AnswerPackage(
        question=package.question,
        answer_mode=ANSWER_MODE_STRUCTURED_EXTRACTIVE,
        cards=package.cards,
        structured_answer=structured,
        no_evidence_message=package.no_evidence_message,
        explanation=explanation,
    )


def _no_evidence_result(
    question: str,
    document_id: int,
    document_name: str,
    query_intent: QueryIntent | None = None,
) -> DocumentQAResult:
    intent = query_intent or interpret_query(question)
    return DocumentQAResult(
        question=question,
        document_id=document_id,
        document_name=document_name,
        answer_mode="NO_EVIDENCE",
        cards=[],
        no_evidence_message=NO_EVIDENCE_MESSAGE,
        explanation=compose_intent_explanation(intent, NO_EVIDENCE_EXPLANATION),
        query_intent=intent,
    )


def _require_document_index(db_path: str, document_id: int) -> None:
    if not document_has_index(db_path, document_id):
        raise ValueError(
            f"No lexical index found for document id={document_id}. "
            "Process the document before asking questions."
        )
    statistics = load_bm25_statistics(db_path, document_id)
    if not statistics:
        raise ValueError(
            f"No BM25 statistics found for document id={document_id}. "
            "Process the document before asking questions."
        )


def _question_audit_details(
    *,
    document_id: int | None,
    document_name: str | None,
    question: str,
    answer_mode: str | None = None,
    evidence_card_count: int | None = None,
    top_score: float | None = None,
    error: str | None = None,
) -> dict:
    details: dict = {"question": question}
    if document_id is not None:
        details["document_id"] = document_id
    if document_name is not None:
        details["document_name"] = document_name
    if answer_mode is not None:
        details["answer_mode"] = answer_mode
    if evidence_card_count is not None:
        details["evidence_card_count"] = evidence_card_count
    if top_score is not None:
        details["top_score"] = top_score
    if error is not None:
        details["error"] = error
    return details


def _top_score(cards: list[EvidenceCard]) -> float | None:
    if not cards:
        return None
    return max(card.score for card in cards)


def _format_candidate_sections(
    question: str,
    sections: list[StoredSection],
    top_k: int = 5,
) -> str:
    scored: list[tuple[float, StoredSection]] = []
    for section in sections:
        score = score_section_relevance(question, section)
        if score > 0:
            scored.append((score, section))
    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].start_line,
            item[1].section_id,
        )
    )
    if not scored:
        return "[]"
    labels = [f"{section.title}:{score:.2f}" for score, section in scored[:top_k]]
    return "[" + ", ".join(labels) + "]"


def _normalize_section_title_key(title: str) -> str:
    import re

    cleaned = re.sub(r"^\s*#+\s*", "", title.strip())
    return cleaned.lower()


def _sections_with_inferred_ranges(
    db_path: str,
    document_id: int,
    chunks: list[DocumentChunk],
    debug_trace: list[str] | None = None,
) -> list[StoredSection]:
    import re

    stored_sections = get_sections_for_document(db_path, document_id)
    derived_sections = derive_sections_from_chunks(chunks)
    if debug_trace is not None:
        debug_trace.append(f"stored_section_count={len(stored_sections)}")

    merged_by_title: dict[str, StoredSection] = {}
    for section in stored_sections:
        key = _normalize_section_title_key(section.title)
        cleaned_title = re.sub(r"^\s*#+\s*", "", section.title.strip())
        merged_by_title[key] = StoredSection(
            section_id=section.section_id,
            title=cleaned_title,
            level=section.level,
            start_line=section.start_line,
            end_line=section.end_line,
            parent_section_id=section.parent_section_id,
        )
    for section in derived_sections:
        key = _normalize_section_title_key(section.title)
        cleaned_title = re.sub(r"^\s*#+\s*", "", section.title.strip())
        candidate = StoredSection(
            section_id=section.section_id,
            title=cleaned_title,
            level=section.level,
            start_line=section.start_line,
            end_line=section.end_line,
            parent_section_id=section.parent_section_id,
        )
        existing = merged_by_title.get(key)
        if existing is None or candidate.end_line > existing.end_line:
            merged_by_title[key] = candidate

    if not merged_by_title:
        if debug_trace is not None:
            debug_trace.append("sections_source=derived_from_chunks")
        return derived_sections

    if debug_trace is not None:
        if stored_sections:
            debug_trace.append("sections_source=stored_with_semantic_merge")
        else:
            debug_trace.append("sections_source=derived_from_chunks")

    document_sections = [
        DocumentSection(
            section_id=section.section_id,
            title=section.title,
            level=section.level,
            start_line=section.start_line,
            end_line=section.end_line,
            parent_section_id=section.parent_section_id,
        )
        for section in sorted(
            merged_by_title.values(),
            key=lambda item: (item.start_line, item.section_id),
        )
    ]
    total_lines = max((chunk.end_line for chunk in chunks), default=1)
    if document_sections:
        total_lines = max(total_lines, max(section.end_line for section in document_sections))

    ranged_sections = infer_section_ranges(document_sections, total_lines)
    return [
        StoredSection(
            section_id=section.section_id,
            title=section.title,
            level=section.level,
            start_line=section.start_line,
            end_line=section.end_line,
            parent_section_id=section.parent_section_id,
        )
        for section in ranged_sections
    ]


def _matched_terms_for_chunk(chunk: DocumentChunk, query_terms: set[str]) -> list[str]:
    chunk_text = chunk.text.lower()
    return sorted(term for term in query_terms if term in chunk_text)


def _section_results_from_chunks(
    section: StoredSection,
    chunks: list[DocumentChunk],
    question: str,
    section_score: float,
) -> list[SearchResult]:
    query_terms = extract_topic_terms(question)

    section_chunks = collect_section_chunks(section, chunks, max_chunks=20)
    results: list[SearchResult] = []
    for rank, chunk in enumerate(section_chunks):
        matched_terms = _matched_terms_for_chunk(chunk, query_terms)
        score = section_score + max(0.05, 0.5 - (rank * 0.02))
        in_range = (
            section.start_line <= chunk.start_line <= section.end_line
            and chunk.end_line <= section.end_line
        )
        why = (
            f"Matched by section-level retrieval from section '{section.title}'."
        )
        if not in_range:
            why += " context_expanded=True"
        results.append(
            SearchResult(
                chunk_id=chunk.chunk_id,
                document_name=chunk.document_name,
                text=chunk.text,
                score=score,
                matched_terms=matched_terms,
                term_scores={term: 1.0 for term in matched_terms},
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                section_title=section.title,
                chunk_type=chunk.chunk_type,
                why_matched=why,
                section_id=section.section_id,
            )
        )
    return results


def _align_chunks_to_inferred_sections(
    chunks: list[DocumentChunk],
    sections: list[StoredSection],
    *,
    total_lines: int,
) -> list[DocumentChunk]:
    """Reassign chunk section metadata using inferred section line ranges."""
    document_sections = [
        DocumentSection(
            section_id=section.section_id,
            title=section.title,
            level=section.level,
            start_line=section.start_line,
            end_line=section.end_line,
            parent_section_id=section.parent_section_id,
        )
        for section in sections
    ]
    return reassign_chunk_sections(
        chunks,
        document_sections,
        total_lines=total_lines,
    )


def ask_document(
    question: str,
    document_id: int,
    db_path: str = "data/tracedoc.db",
    top_k: int = 5,
    max_cards: int = 3,
) -> DocumentQAResult:
    """
    Answer a question using persisted index, retrieval, and evidence cards.

    Raises:
        ValueError: If the document, index, or BM25 statistics are missing.
    """
    document_name: str | None = None

    try:
        document = get_document_by_id(db_path, document_id)
        if document is None:
            raise ValueError(f"Document not found: id={document_id}")

        document_name = document.file_name

        query_intent = interpret_query(question)

        if not question.strip():
            result = _no_evidence_result(
                question, document_id, document.file_name, query_intent=query_intent
            )
            log_audit_event(
                db_path,
                "question_asked",
                _question_audit_details(
                    document_id=document_id,
                    document_name=document.file_name,
                    question=question,
                    answer_mode=result.answer_mode,
                    evidence_card_count=0,
                    top_score=None,
                ),
            )
            return result

        _require_document_index(db_path, document_id)

        retrieval_query = build_retrieval_query(question, query_intent)
        chunks = get_chunks_for_document(db_path, document_id)
        document_schema = load_document_schema(db_path, document_id)
        matched_schema_category = None
        target_category: str | None = None
        debug_trace: list[str] = [
            f"intent_type={query_intent.intent_type}",
            f"retrieval_query={retrieval_query!r}",
            f"chunk_count={len(chunks)}",
        ]
        total_lines = max((chunk.end_line for chunk in chunks), default=1)
        inferred_sections = _sections_with_inferred_ranges(
            db_path, document_id, chunks, debug_trace=debug_trace
        )
        chunks = _align_chunks_to_inferred_sections(
            chunks, inferred_sections, total_lines=total_lines
        )
        if document_schema is not None:
            category_names = sorted(
                category.normalized_name for category in document_schema.categories
            )
            debug_trace.append(f"discovered_categories=[{','.join(category_names)}]")
            debug_trace.extend(
                format_category_normalization_trace(document_schema.categories)
            )
            debug_trace.append(
                f"graph_candidates_count={len(document_schema.graph_candidates)}"
            )
            target_category = resolve_query_target_category(question, document_schema)
            if target_category:
                debug_trace.append(f"target_category={target_category}")
            matched_schema_category = match_question_to_schema_category(
                question, document_schema
            )
            if matched_schema_category is not None:
                debug_trace.append(
                    f"schema_category_match={matched_schema_category.normalized_name}"
                )
                debug_trace.append(
                    f"schema_category_confidence={matched_schema_category.confidence_score:.2f}"
                )
                debug_trace.append(
                    "category_match_reason=semantic_heading_normalization"
                )
                registry = build_pattern_registry(document_schema)
                pattern_names = registry.get(
                    matched_schema_category.normalized_name, []
                )
                debug_trace.append(f"schema_patterns=[{','.join(pattern_names)}]")
        search_results: list[SearchResult] = []
        section_retrieval_used = False
        retrieved_section_title: str | None = None
        retrieval_strategy = RETRIEVAL_STRATEGY_BM25
        effective_max_cards = max_cards

        use_section_retrieval = should_use_section_retrieval(
            question, query_intent.intent_type
        )
        debug_trace.append(f"should_use_section_retrieval={use_section_retrieval}")

        if use_section_retrieval:
            topic_terms = sorted(extract_topic_terms(question))
            debug_trace.append(f"topic_terms={topic_terms}")
            sections = inferred_sections
            debug_trace.append(f"section_count={len(sections)}")

            if not sections:
                debug_trace.append("fallback_reason=no_sections")
            else:
                debug_trace.append(
                    "candidate_sections="
                    + _format_candidate_sections(question, sections)
                )
                ranked_sections = find_relevant_sections(
                    question,
                    sections,
                    top_k=3,
                    document_schema=document_schema,
                )
                if not ranked_sections:
                    debug_trace.append("fallback_reason=no_relevant_section")
                else:
                    best_section = ranked_sections[0]
                    if document_schema is not None:
                        target_category = resolve_query_target_category(
                            question,
                            document_schema,
                            selected_section_title=best_section.title,
                        )
                        matched_schema_category = match_question_to_schema_category(
                            question,
                            document_schema,
                            selected_section_title=best_section.title,
                        )
                        if target_category:
                            debug_trace.append(
                                f"target_category={target_category}"
                            )
                        if matched_schema_category is not None:
                            debug_trace.append(
                                "schema_category_match="
                                f"{matched_schema_category.normalized_name}"
                            )
                    debug_trace.append(f"selected_section={best_section.title}")
                    debug_trace.append(
                        "selected_section_range="
                        f"{best_section.start_line}-{best_section.end_line}"
                    )
                    section_score = score_section_relevance(
                        question,
                        best_section,
                        document_schema=document_schema,
                    )
                    debug_trace.append(f"selected_section_score={section_score:.2f}")
                    section_chunks = collect_section_chunks(
                        best_section, chunks, max_chunks=20
                    )
                    debug_trace.append(
                        f"collected_section_chunks={len(section_chunks)}"
                    )
                    chunk_ranges = [
                        f"{chunk.start_line}-{chunk.end_line}"
                        for chunk in section_chunks
                    ]
                    debug_trace.append(
                        f"collected_chunk_ranges=[{','.join(chunk_ranges)}]"
                    )
                    if not section_chunks:
                        debug_trace.append("fallback_reason=no_chunks_in_section")
                    else:
                        if document_schema is not None and target_category:
                            grammar = primary_grammar_for_category(
                                document_schema, target_category
                            )
                            if grammar is not None:
                                debug_trace.append(f"grammar_used={grammar.pattern_name}")
                                debug_trace.append(
                                    f"grammar_confidence={grammar.confidence_score:.2f}"
                                )
                                template_preview = ";".join(
                                    grammar.sentence_templates[:4]
                                )
                                debug_trace.append(
                                    f"grammar_sentence_templates=[{template_preview}]"
                                )
                                from app.evidence.extraction_validator import (
                                    build_extraction_validation_registry,
                                    filter_text_to_category_sentences,
                                )

                                from app.structure.chunk_section import (
                                    clip_chunk_text_to_section,
                                )

                                grammar_text = "\n".join(
                                    clip_chunk_text_to_section(chunk, best_section)
                                    for chunk in section_chunks
                                )
                                scoped_by_category = {
                                    target_category: filter_text_to_category_sentences(
                                        grammar_text,
                                        target_category,
                                        document_schema,
                                    )
                                }
                                validation_registry = (
                                    build_extraction_validation_registry(
                                        document_schema,
                                        full_text_by_category=scoped_by_category,
                                    )
                                )
                                grammar_result = execute_discovered_grammar_with_result(
                                    scoped_by_category[target_category]
                                    or grammar_text,
                                    grammar,
                                    category=target_category,
                                    validation_registry=validation_registry,
                                    section_title=best_section.title,
                                )
                                debug_trace.extend(
                                    grammar_execution_debug_lines(grammar_result)
                                )
                                if grammar_result.validated_entities:
                                    preview = ", ".join(
                                        grammar_result.validated_entities[:8]
                                    )
                                    debug_trace.append(
                                        f"validated_entities=[{preview}]"
                                    )
                                if grammar_result.rejected_entities:
                                    preview = ", ".join(
                                        grammar_result.rejected_entities[:8]
                                    )
                                    debug_trace.append(
                                        f"rejected_entities=[{preview}]"
                                    )

                        section_results = _section_results_from_chunks(
                            best_section,
                            chunks,
                            question,
                            section_score,
                        )
                        if section_results:
                            search_results = section_results
                            section_retrieval_used = True
                            retrieved_section_title = best_section.title
                            retrieval_strategy = RETRIEVAL_STRATEGY_SECTION
                            effective_max_cards = max(
                                max_cards,
                                min(len(search_results), 12),
                            )
        else:
            debug_trace.append("section_retrieval_skipped=trigger_false")

        if not search_results:
            if use_section_retrieval and not any(
                line.startswith("fallback_reason=") for line in debug_trace
            ):
                debug_trace.append("fallback_reason=section_path_empty_results")
            debug_trace.append("using_bm25_fallback=True")
            index = load_index_for_document(db_path, document_id)
            bm25_stats = load_bm25_statistics(db_path, document_id)
            search_results = search_chunks(
                retrieval_query,
                index,
                bm25_stats,
                top_k=top_k,
                intent_type=query_intent.intent_type,
                entities=query_intent.entities,
            )
            debug_trace.append(f"bm25_result_count={len(search_results)}")
        else:
            debug_trace.append("using_bm25_fallback=False")

        debug_trace.append(f"retrieval_strategy={retrieval_strategy}")
        if target_category is None and document_schema is not None:
            target_category = resolve_query_target_category(
                question, document_schema
            )
            if target_category:
                debug_trace.append(f"target_category={target_category}")

        package = _apply_structured_answer(
            compose_answer_package(
                question,
                search_results,
                max_cards=effective_max_cards,
                all_chunks=chunks,
            ),
            question,
            document_schema=document_schema,
            target_category=target_category,
        )
        if package.structured_answer and "architect" in question.lower():
            debug_trace.extend(
                architecture_extraction_trace(
                    architecture_evidence_text(package.cards)
                )
            )

        result = DocumentQAResult(
            question=package.question,
            document_id=document_id,
            document_name=document.file_name,
            answer_mode=package.answer_mode,
            cards=package.cards,
            structured_answer=package.structured_answer,
            no_evidence_message=package.no_evidence_message,
            explanation=compose_intent_explanation(query_intent, package.explanation),
            query_intent=query_intent,
            section_retrieval_used=section_retrieval_used,
            retrieved_section_title=retrieved_section_title,
            retrieval_strategy=retrieval_strategy,
            debug_trace=debug_trace,
        )

        log_audit_event(
            db_path,
            "question_asked",
            _question_audit_details(
                document_id=document_id,
                document_name=document.file_name,
                question=question,
                answer_mode=result.answer_mode,
                evidence_card_count=len(result.cards),
                top_score=_top_score(result.cards),
            ),
        )
        return result
    except Exception as error:
        log_audit_event(
            db_path,
            "question_failed",
            _question_audit_details(
                document_id=document_id,
                document_name=document_name,
                question=question,
                error=str(error),
            ),
        )
        raise


def _sort_search_results(results: list[SearchResult]) -> list[SearchResult]:
    return sorted(
        results,
        key=lambda item: (
            -item.score,
            item.document_name,
            item.start_line,
            item.chunk_id,
        ),
    )


def ask_all_documents(
    question: str,
    db_path: str = "data/tracedoc.db",
    top_k_per_document: int = 3,
    max_cards: int = 5,
) -> AllDocumentsQAResult:
    """
    Search all indexed documents and compose one evidence-only answer package.
    """
    documents = list_documents(db_path)
    if not question.strip():
        return AllDocumentsQAResult(
            question=question,
            answer_mode="NO_EVIDENCE",
            cards=[],
            no_evidence_message=NO_EVIDENCE_MESSAGE,
            explanation=NO_EVIDENCE_EXPLANATION,
            document_count=len(documents),
        )

    query_intent = interpret_query(question)
    retrieval_query = build_retrieval_query(question, query_intent)
    combined_results: list[SearchResult] = []
    indexed_count = 0
    chunks_by_document: dict[int, list[DocumentChunk]] = {}
    section_retrieval_used = False
    retrieved_section_title: str | None = None
    retrieval_strategy = RETRIEVAL_STRATEGY_BM25

    for document in documents:
        if not document_has_index(db_path, document.id):
            continue
        chunks_by_document[document.id] = get_chunks_for_document(db_path, document.id)
        indexed_count += 1
        doc_results: list[SearchResult] = []
        if should_use_section_retrieval(question, query_intent.intent_type):
            sections = _sections_with_inferred_ranges(
                db_path,
                document.id,
                chunks_by_document[document.id],
            )
            ranked_sections = find_relevant_sections(question, sections, top_k=1)
            if ranked_sections:
                best_section = ranked_sections[0]
                section_score = score_section_relevance(question, best_section)
                doc_results = _section_results_from_chunks(
                    best_section,
                    chunks_by_document[document.id],
                    question,
                    section_score,
                )
                if doc_results:
                    section_retrieval_used = True
                    retrieved_section_title = best_section.title
                    retrieval_strategy = RETRIEVAL_STRATEGY_SECTION
        if not doc_results:
            statistics = load_bm25_statistics(db_path, document.id)
            if not statistics:
                continue
            index = load_index_for_document(db_path, document.id)
            doc_results = search_chunks(
                retrieval_query,
                index,
                statistics,
                top_k=top_k_per_document,
                intent_type=query_intent.intent_type,
                entities=query_intent.entities,
            )
        combined_results.extend(doc_results)

    if indexed_count == 0:
        raise ValueError(
            "No indexed documents found. Process documents before asking questions."
        )

    sorted_results = _sort_search_results(combined_results)
    all_chunks = [
        chunk
        for document in documents
        for chunk in chunks_by_document.get(document.id, [])
    ]
    effective_max_cards = max_cards
    if section_retrieval_used:
        effective_max_cards = max(max_cards, min(len(sorted_results), 12))

    package = _apply_structured_answer(
        compose_answer_package(
            question,
            sorted_results,
            max_cards=effective_max_cards,
            all_chunks=all_chunks or None,
        ),
        question,
    )

    return AllDocumentsQAResult(
        question=package.question,
        answer_mode=package.answer_mode,
        cards=package.cards,
        structured_answer=package.structured_answer,
        no_evidence_message=package.no_evidence_message,
        explanation=compose_intent_explanation(query_intent, package.explanation),
        document_count=indexed_count,
        section_retrieval_used=section_retrieval_used,
        retrieved_section_title=retrieved_section_title,
        retrieval_strategy=retrieval_strategy,
    )
