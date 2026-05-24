"""Tests for SQLite storage and index persistence."""

from __future__ import annotations

from pathlib import Path

from app.indexing import prepare_document_chunks
from app.ingestion.models import DocumentExtractionResult
from app.retrieval import search_chunks
from app.storage import (
    get_chunks_for_document,
    get_document_by_checksum,
    initialize_database,
    list_audit_events,
    list_documents,
    load_bm25_statistics,
    load_index_for_document,
    save_document_bundle,
    save_index_bundle,
)
from app.storage.database import connect
from app.structure import structure_document


def _sample_extraction(
    *,
    checksum: str = "abc123checksum",
    file_name: str = "policy.txt",
    text: str | None = None,
) -> DocumentExtractionResult:
    body = text or (
        "# Security Policy\n\n"
        "HPC6 cluster memory requirements are documented.\n\n"
        "REQ-001 defines baseline controls."
    )
    return DocumentExtractionResult(
        file_path=f"/tmp/{file_name}",
        file_name=file_name,
        file_type="txt",
        file_size_bytes=len(body.encode("utf-8")),
        checksum_sha256=checksum,
        page_count=None,
        text=body,
        metadata={"source": "test"},
        extraction_warnings=[],
    )


def test_database_initializes(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"
    initialize_database(db_path)

    with connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {
        "documents",
        "sections",
        "chunks",
        "index_terms",
        "chunk_term_frequencies",
        "bm25_statistics",
        "audit_events",
    }.issubset(tables)


def test_document_saved(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"
    extraction = _sample_extraction()
    sections, chunks = structure_document(extraction.file_name, extraction.text)

    document_id, _ = save_document_bundle(db_path, extraction, sections, chunks)
    saved = get_document_by_checksum(db_path, extraction.checksum_sha256)

    assert document_id == saved.id
    assert saved.file_name == "policy.txt"
    assert len(list_documents(db_path)) == 1


def test_duplicate_checksum_not_duplicated(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"
    extraction = _sample_extraction()
    sections, chunks = structure_document(extraction.file_name, extraction.text)

    first_id, first_created = save_document_bundle(db_path, extraction, sections, chunks)
    second_id, second_created = save_document_bundle(db_path, extraction, sections, chunks)

    assert first_id == second_id
    assert first_created is True
    assert second_created is False
    assert len(list_documents(db_path)) == 1


def test_sections_saved(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"
    extraction = _sample_extraction()
    sections, chunks = structure_document(extraction.file_name, extraction.text)
    document_id, _ = save_document_bundle(db_path, extraction, sections, chunks)

    with connect(db_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM sections WHERE document_id = ?",
            (document_id,),
        ).fetchone()[0]

    assert count == len(sections)
    assert count >= 1


def test_chunks_saved(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"
    extraction = _sample_extraction()
    sections, chunks = structure_document(extraction.file_name, extraction.text)
    document_id, _ = save_document_bundle(db_path, extraction, sections, chunks)

    loaded_chunks = get_chunks_for_document(db_path, document_id)

    assert len(loaded_chunks) == len(chunks)
    assert loaded_chunks[0].text


def test_index_terms_saved(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"
    extraction = _sample_extraction()
    sections, chunks = structure_document(extraction.file_name, extraction.text)
    document_id, _ = save_document_bundle(db_path, extraction, sections, chunks)
    index, stats = prepare_document_chunks(chunks)
    save_index_bundle(db_path, document_id, index, stats)

    with connect(db_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM index_terms WHERE document_id = ?",
            (document_id,),
        ).fetchone()[0]

    assert count == index.vocabulary_size
    assert count > 0


def test_bm25_stats_saved_and_loaded(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"
    extraction = _sample_extraction()
    sections, chunks = structure_document(extraction.file_name, extraction.text)
    document_id, _ = save_document_bundle(db_path, extraction, sections, chunks)
    index, stats = prepare_document_chunks(chunks)
    save_index_bundle(db_path, document_id, index, stats)

    loaded = load_bm25_statistics(db_path, document_id)

    assert loaded["avgdl"] == stats["avgdl"]
    assert loaded["df"] == stats["df"]
    assert loaded["idf"]["hpc6"] == stats["idf"]["hpc6"]


def test_audit_event_created(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"
    extraction = _sample_extraction()
    sections, chunks = structure_document(extraction.file_name, extraction.text)
    document_id, _ = save_document_bundle(db_path, extraction, sections, chunks)

    events = list_audit_events(db_path, document_id=document_id)

    assert len(events) == 1
    assert events[0].event_type == "document_saved"
    assert events[0].details["chunk_count"] == len(chunks)


def test_loaded_index_can_be_searched(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"
    extraction = _sample_extraction()
    sections, chunks = structure_document(extraction.file_name, extraction.text)
    document_id, _ = save_document_bundle(db_path, extraction, sections, chunks)
    index, stats = prepare_document_chunks(chunks)
    save_index_bundle(db_path, document_id, index, stats)

    in_memory_results = search_chunks("hpc6 memory", index, stats, top_k=3)
    loaded_index = load_index_for_document(db_path, document_id)
    loaded_stats = load_bm25_statistics(db_path, document_id)
    persisted_results = search_chunks(
        "hpc6 memory", loaded_index, loaded_stats, top_k=3
    )

    assert len(persisted_results) == len(in_memory_results)
    assert [result.chunk_id for result in persisted_results] == [
        result.chunk_id for result in in_memory_results
    ]
    assert persisted_results[0].text == in_memory_results[0].text
