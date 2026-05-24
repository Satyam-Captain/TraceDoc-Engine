"""End-to-end document processing orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.audit import log_audit_event
from app.indexing import prepare_document_chunks
from app.ingestion import extract_document
from app.storage import (
    get_document_processing_counts,
    initialize_database,
    save_document_bundle,
    save_document_tree,
    save_knowledge_graph,
    save_index_bundle,
)
from app.graph import build_knowledge_graph
from app.tree import build_document_tree
from app.schema import discover_document_schema
from app.storage import save_document_schema
from app.structure import structure_document


@dataclass
class ProcessedDocumentResult:
    """Summary of a completed document processing run."""

    document_id: int
    file_name: str
    checksum_sha256: str
    section_count: int
    chunk_count: int
    indexed_term_count: int
    duplicate: bool
    warnings: list[str] = field(default_factory=list)


def _processing_audit_details(
    *,
    file_name: str,
    document_id: int | None = None,
    checksum_sha256: str | None = None,
    section_count: int | None = None,
    chunk_count: int | None = None,
    indexed_term_count: int | None = None,
    warnings: list[str] | None = None,
    duplicate: bool | None = None,
    error: str | None = None,
) -> dict:
    details: dict = {"file_name": file_name}
    if document_id is not None:
        details["document_id"] = document_id
    if checksum_sha256 is not None:
        details["checksum_sha256"] = checksum_sha256
    if section_count is not None:
        details["section_count"] = section_count
    if chunk_count is not None:
        details["chunk_count"] = chunk_count
    if indexed_term_count is not None:
        details["indexed_term_count"] = indexed_term_count
    if warnings is not None:
        details["warnings"] = warnings
    if duplicate is not None:
        details["duplicate"] = duplicate
    if error is not None:
        details["error"] = error
    return details


def process_document(
    file_path: str,
    db_path: str = "data/tracedoc.db",
) -> ProcessedDocumentResult:
    """
    Ingest, structure, index, and persist one document deterministically.

    Raises:
        FileNotFoundError: If the source file does not exist.
        ValueError: If the file type is unsupported.
    """
    file_name = Path(file_path).name
    extraction = None
    document_id: int | None = None
    checksum_sha256: str | None = None
    warnings: list[str] = []

    try:
        extraction = extract_document(file_path)
        file_name = Path(file_path).name
        checksum_sha256 = extraction.checksum_sha256
        warnings = list(extraction.extraction_warnings)

        initialize_database(db_path)

        sections, chunks = structure_document(file_name, extraction.text)
        index, bm25_stats = prepare_document_chunks(chunks)

        document_id, created = save_document_bundle(
            db_path, extraction, sections, chunks
        )
        duplicate = not created

        if created:
            schema = discover_document_schema(document_id, sections, chunks)
            save_document_schema(db_path, schema)
            document_tree = build_document_tree(
                sections,
                chunks,
                document_name=file_name,
                document_id=document_id,
            )
            save_document_tree(db_path, document_id, document_tree)
            knowledge_graph = build_knowledge_graph(
                document_id, document_tree, schema
            )
            save_knowledge_graph(db_path, document_id, knowledge_graph)
            save_index_bundle(db_path, document_id, index, bm25_stats)
            section_count = len(sections)
            chunk_count = len(chunks)
            indexed_term_count = index.vocabulary_size
        else:
            section_count, chunk_count, indexed_term_count = (
                get_document_processing_counts(db_path, document_id)
            )
            warnings.append(
                f"Document already indexed (checksum {extraction.checksum_sha256})."
            )

        result = ProcessedDocumentResult(
            document_id=document_id,
            file_name=file_name,
            checksum_sha256=extraction.checksum_sha256,
            section_count=section_count,
            chunk_count=chunk_count,
            indexed_term_count=indexed_term_count,
            duplicate=duplicate,
            warnings=warnings,
        )

        log_audit_event(
            db_path,
            "document_processed",
            _processing_audit_details(
                file_name=file_name,
                document_id=result.document_id,
                checksum_sha256=result.checksum_sha256,
                section_count=result.section_count,
                chunk_count=result.chunk_count,
                indexed_term_count=result.indexed_term_count,
                warnings=result.warnings,
                duplicate=result.duplicate,
            ),
        )
        if duplicate:
            log_audit_event(
                db_path,
                "duplicate_document_detected",
                _processing_audit_details(
                    file_name=file_name,
                    document_id=result.document_id,
                    checksum_sha256=result.checksum_sha256,
                    section_count=result.section_count,
                    chunk_count=result.chunk_count,
                    indexed_term_count=result.indexed_term_count,
                    warnings=result.warnings,
                    duplicate=True,
                ),
            )
        return result
    except Exception as error:
        log_audit_event(
            db_path,
            "document_processing_failed",
            _processing_audit_details(
                file_name=file_name,
                document_id=document_id,
                checksum_sha256=checksum_sha256,
                warnings=warnings,
                error=str(error),
            ),
        )
        raise


def process_documents(
    file_paths: list[str],
    db_path: str = "data/tracedoc.db",
) -> list[ProcessedDocumentResult]:
    """Process multiple documents independently. Raises on the first failure."""
    return [process_document(file_path, db_path=db_path) for file_path in file_paths]
