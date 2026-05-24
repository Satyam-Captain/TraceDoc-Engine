"""End-to-end document processing orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.indexing import prepare_document_chunks
from app.ingestion import extract_document
from app.storage import (
    get_document_processing_counts,
    initialize_database,
    save_document_bundle,
    save_index_bundle,
)
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
    extraction = extract_document(file_path)
    file_name = Path(file_path).name
    warnings = list(extraction.extraction_warnings)

    initialize_database(db_path)

    sections, chunks = structure_document(file_name, extraction.text)
    index, bm25_stats = prepare_document_chunks(chunks)

    document_id, created = save_document_bundle(
        db_path, extraction, sections, chunks
    )
    duplicate = not created

    if created:
        save_index_bundle(db_path, document_id, index, bm25_stats)
        section_count = len(sections)
        chunk_count = len(chunks)
        indexed_term_count = index.vocabulary_size
    else:
        section_count, chunk_count, indexed_term_count = get_document_processing_counts(
            db_path, document_id
        )
        warnings.append(
            f"Document already indexed (checksum {extraction.checksum_sha256})."
        )

    return ProcessedDocumentResult(
        document_id=document_id,
        file_name=file_name,
        checksum_sha256=extraction.checksum_sha256,
        section_count=section_count,
        chunk_count=chunk_count,
        indexed_term_count=indexed_term_count,
        duplicate=duplicate,
        warnings=warnings,
    )


def process_documents(
    file_paths: list[str],
    db_path: str = "data/tracedoc.db",
) -> list[ProcessedDocumentResult]:
    """Process multiple documents independently. Raises on the first failure."""
    return [process_document(file_path, db_path=db_path) for file_path in file_paths]
