"""Tests for end-to-end document processing pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.pipeline import process_document, process_documents
from app.retrieval import search_chunks
from app.storage import (
    get_chunks_for_document,
    list_documents,
    load_bm25_statistics,
    load_index_for_document,
)


def _write_sample_txt(path: Path) -> None:
    path.write_text(
        "# Security Policy\n\n"
        "HPC6 cluster memory requirements are documented.\n\n"
        "REQ-001 defines baseline controls.\n",
        encoding="utf-8",
    )


def test_txt_document_processed_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "policy.txt"
    db_path = tmp_path / "tracedoc.db"
    _write_sample_txt(source)

    result = process_document(str(source), db_path=str(db_path))

    assert result.duplicate is False
    assert result.document_id > 0
    assert result.file_name == "policy.txt"
    assert result.section_count >= 1
    assert result.chunk_count >= 1
    assert result.indexed_term_count > 0
    assert db_path.exists()


def test_document_listed_after_processing(tmp_path: Path) -> None:
    source = tmp_path / "policy.txt"
    db_path = tmp_path / "tracedoc.db"
    _write_sample_txt(source)

    result = process_document(str(source), db_path=str(db_path))
    documents = list_documents(db_path)

    assert len(documents) == 1
    assert documents[0].id == result.document_id


def test_chunks_persisted(tmp_path: Path) -> None:
    source = tmp_path / "policy.txt"
    db_path = tmp_path / "tracedoc.db"
    _write_sample_txt(source)

    result = process_document(str(source), db_path=str(db_path))
    chunks = get_chunks_for_document(db_path, result.document_id)

    assert len(chunks) == result.chunk_count
    assert any("HPC6" in chunk.text for chunk in chunks)


def test_index_and_bm25_loaded(tmp_path: Path) -> None:
    source = tmp_path / "policy.txt"
    db_path = tmp_path / "tracedoc.db"
    _write_sample_txt(source)

    result = process_document(str(source), db_path=str(db_path))
    index = load_index_for_document(db_path, result.document_id)
    stats = load_bm25_statistics(db_path, result.document_id)

    assert index.vocabulary_size == result.indexed_term_count
    assert stats["avgdl"] > 0
    assert "hpc6" in stats["idf"]


def test_loaded_index_can_be_searched(tmp_path: Path) -> None:
    source = tmp_path / "policy.txt"
    db_path = tmp_path / "tracedoc.db"
    _write_sample_txt(source)

    result = process_document(str(source), db_path=str(db_path))
    index = load_index_for_document(db_path, result.document_id)
    stats = load_bm25_statistics(db_path, result.document_id)

    results = search_chunks("hpc6 memory", index, stats, top_k=3)

    assert results
    assert results[0].score > 0
    assert "hpc6" in results[0].matched_terms


def test_duplicate_processing_returns_duplicate_true(tmp_path: Path) -> None:
    source = tmp_path / "policy.txt"
    db_path = tmp_path / "tracedoc.db"
    _write_sample_txt(source)

    first = process_document(str(source), db_path=str(db_path))
    second = process_document(str(source), db_path=str(db_path))

    assert first.duplicate is False
    assert second.duplicate is True
    assert second.document_id == first.document_id
    assert len(list_documents(db_path)) == 1
    assert any("already indexed" in warning for warning in second.warnings)


def test_unsupported_file_raises_value_error(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    db_path = tmp_path / "tracedoc.db"
    source.write_text("a,b,c", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported file type"):
        process_document(str(source), db_path=str(db_path))


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"

    with pytest.raises(FileNotFoundError, match="File not found"):
        process_document(str(tmp_path / "missing.txt"), db_path=str(db_path))


def test_process_documents_processes_multiple_files(tmp_path: Path) -> None:
    first = tmp_path / "one.txt"
    second = tmp_path / "two.txt"
    db_path = tmp_path / "tracedoc.db"
    first.write_text("Alpha document content.", encoding="utf-8")
    second.write_text("Beta document content.", encoding="utf-8")

    results = process_documents([str(first), str(second)], db_path=str(db_path))

    assert len(results) == 2
    assert len(list_documents(db_path)) == 2
