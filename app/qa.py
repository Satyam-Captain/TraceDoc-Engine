"""Document question-answer orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.audit import log_audit_event
from app.evidence import compose_answer_package, compose_structured_answer
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
from app.query.models import INTENT_LIST_REQUEST, QueryIntent
from app.retrieval import (
    collect_section_chunks,
    find_relevant_sections,
    search_chunks,
)
from app.retrieval.models import SearchResult
from app.structure.models import DocumentChunk
from app.storage import (
    document_has_index,
    get_chunks_for_document,
    get_document_by_id,
    get_sections_for_document,
    list_documents,
    load_bm25_statistics,
    load_index_for_document,
)
from app.storage.models import StoredSection
from app.indexing.normalizer import normalize_token
from app.indexing.tokenizer import tokenize


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


STRUCTURED_ANSWER_EXPLANATION_SUFFIX = (
    " A structured extractive summary was composed only from retrieved evidence text."
)


def _apply_structured_answer(package: AnswerPackage, question: str) -> AnswerPackage:
    """Upgrade answer package to STRUCTURED_EXTRACTIVE when rules match evidence."""
    if package.answer_mode == "NO_EVIDENCE" or not package.cards:
        return package

    structured = compose_structured_answer(question, package.cards)
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


def _should_use_section_retrieval(question: str, intent: QueryIntent) -> bool:
    lower = question.strip().lower()
    if not lower:
        return False
    if intent.intent_type == INTENT_LIST_REQUEST:
        return True
    if lower.startswith("what are") or lower.startswith("list"):
        return True
    if any(term in lower for term in ("different", "types", "kinds")):
        return True
    plural_targets = ("architectures", "patterns", "steps", "capabilities")
    return any(term in lower for term in plural_targets)


def _score_section_chunk(chunk: DocumentChunk, query_terms: set[str], rank: int) -> float:
    text_terms = {
        normalize_token(token) for token in tokenize(chunk.text) if normalize_token(token)
    }
    overlap = len(query_terms.intersection(text_terms))
    base = 1.0 + (0.3 * overlap)
    position_decay = max(0.05, 0.6 - (rank * 0.03))
    return base + position_decay


def _section_results_from_chunks(
    section: StoredSection,
    chunks: list[DocumentChunk],
    retrieval_query: str,
) -> list[SearchResult]:
    query_terms = {
        normalize_token(token)
        for token in tokenize(retrieval_query)
        if normalize_token(token)
    }
    for singular, plural in (
        ("architecture", "architectures"),
        ("capability", "capabilities"),
        ("pattern", "patterns"),
    ):
        if singular in query_terms:
            query_terms.add(plural)
        if plural in query_terms:
            query_terms.add(singular)
    section_chunks = collect_section_chunks(section, chunks, max_chunks=12)
    results: list[SearchResult] = []
    for rank, chunk in enumerate(section_chunks):
        matched_terms = sorted(
            [term for term in query_terms if term in chunk.text.lower()]
        )
        if not matched_terms and rank > 0:
            # Keep mostly explanatory chunks after heading, but avoid
            # pulling distant unrelated text.
            continue
        score = _score_section_chunk(chunk, query_terms, rank)
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
                section_title=chunk.section_title,
                chunk_type=chunk.chunk_type,
                why_matched=(
                    "Section-level retrieval for list/enumeration query; "
                    "chunk selected from ranked relevant section."
                ),
                section_id=chunk.section_id,
            )
        )
    return results


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
        search_results: list[SearchResult] = []
        if _should_use_section_retrieval(question, query_intent):
            sections = get_sections_for_document(db_path, document_id)
            ranked_sections = find_relevant_sections(
                retrieval_query,
                sections,
                top_k=3,
            )
            if ranked_sections:
                search_results = _section_results_from_chunks(
                    ranked_sections[0],
                    chunks,
                    retrieval_query,
                )
            else:
                search_results = []
        if not search_results:
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
        package = _apply_structured_answer(
            compose_answer_package(
                question,
                search_results,
                max_cards=max_cards,
                all_chunks=chunks,
            ),
            question,
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

    for document in documents:
        if not document_has_index(db_path, document.id):
            continue
        chunks_by_document[document.id] = get_chunks_for_document(db_path, document.id)
        indexed_count += 1
        doc_results: list[SearchResult] = []
        if _should_use_section_retrieval(question, query_intent):
            sections = get_sections_for_document(db_path, document.id)
            ranked_sections = find_relevant_sections(
                retrieval_query,
                sections,
                top_k=1,
            )
            if ranked_sections:
                doc_results = _section_results_from_chunks(
                    ranked_sections[0],
                    chunks_by_document[document.id],
                    retrieval_query,
                )
            else:
                doc_results = []
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
    package = _apply_structured_answer(
        compose_answer_package(
            question,
            sorted_results,
            max_cards=max_cards,
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
    )
