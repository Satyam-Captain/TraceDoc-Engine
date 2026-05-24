"""SQLite persistence repository."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.indexing.models import ChunkIndexEntry, InvertedIndex
from app.ingestion.models import DocumentExtractionResult
from app.storage.database import connect, initialize_database
from app.storage.models import (
    AuditEventRecord,
    DocumentRecord,
    StoredSection,
)
from app.structure.models import DocumentChunk, DocumentSection


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def _row_to_document(row: Any) -> DocumentRecord:
    return DocumentRecord(
        id=int(row["id"]),
        file_path=row["file_path"],
        file_name=row["file_name"],
        file_type=row["file_type"],
        file_size_bytes=int(row["file_size_bytes"]),
        checksum_sha256=row["checksum_sha256"],
        page_count=row["page_count"],
        text=row["text"],
        metadata=_json_loads(row["metadata_json"], {}),
        extraction_warnings=_json_loads(row["extraction_warnings_json"], []),
        created_at=row["created_at"],
    )


def get_document_by_id(
    db_path: str | Path, document_id: int
) -> DocumentRecord | None:
    """Return a document by internal id, or None if it does not exist."""
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
    return _row_to_document(row) if row else None


def get_document_by_checksum(
    db_path: str | Path, checksum_sha256: str
) -> DocumentRecord | None:
    """Return a document by checksum, or None if it does not exist."""
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM documents WHERE checksum_sha256 = ?",
            (checksum_sha256,),
        ).fetchone()
    return _row_to_document(row) if row else None


def list_documents(db_path: str | Path) -> list[DocumentRecord]:
    """List all persisted documents ordered by id."""
    with connect(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM documents ORDER BY id ASC"
        ).fetchall()
    return [_row_to_document(row) for row in rows]


def get_chunks_for_document(
    db_path: str | Path, document_id: int
) -> list[DocumentChunk]:
    """Load structured chunks for a document."""
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT chunk_id, document_name, text, chunk_type, start_line, end_line,
                   section_title, section_id, metadata_json
            FROM chunks
            WHERE document_id = ?
            ORDER BY start_line ASC, chunk_id ASC
            """,
            (document_id,),
        ).fetchall()

    chunks: list[DocumentChunk] = []
    for row in rows:
        metadata = _json_loads(row["metadata_json"], {})
        chunks.append(
            DocumentChunk(
                chunk_id=row["chunk_id"],
                document_name=row["document_name"],
                text=row["text"],
                chunk_type=row["chunk_type"],
                start_line=int(row["start_line"]),
                end_line=int(row["end_line"]),
                section_title=row["section_title"],
                section_id=row["section_id"],
                metadata=metadata,
            )
        )
    return chunks


def get_sections_for_document(
    db_path: str | Path, document_id: int
) -> list[StoredSection]:
    """Load stored sections for a document in document order."""
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT section_id, title, level, start_line, end_line, parent_section_id
            FROM sections
            WHERE document_id = ?
            ORDER BY start_line ASC, section_id ASC
            """,
            (document_id,),
        ).fetchall()

    return [
        StoredSection(
            section_id=row["section_id"],
            title=row["title"],
            level=int(row["level"]),
            start_line=int(row["start_line"]),
            end_line=int(row["end_line"]),
            parent_section_id=row["parent_section_id"],
        )
        for row in rows
    ]


def get_document_processing_counts(
    db_path: str | Path, document_id: int
) -> tuple[int, int, int]:
    """Return section_count, chunk_count, and indexed_term_count for a document."""
    with connect(db_path) as connection:
        section_count = connection.execute(
            "SELECT COUNT(*) FROM sections WHERE document_id = ?",
            (document_id,),
        ).fetchone()[0]
        chunk_count = connection.execute(
            "SELECT COUNT(*) FROM chunks WHERE document_id = ?",
            (document_id,),
        ).fetchone()[0]
        indexed_term_count = connection.execute(
            "SELECT COUNT(*) FROM index_terms WHERE document_id = ?",
            (document_id,),
        ).fetchone()[0]
    return int(section_count), int(chunk_count), int(indexed_term_count)


def document_has_index(db_path: str | Path, document_id: int) -> bool:
    """Return True if BM25 statistics exist for the document."""
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT 1 FROM bm25_statistics WHERE document_id = ?",
            (document_id,),
        ).fetchone()
    return row is not None


def save_document_bundle(
    db_path: str | Path,
    extraction: DocumentExtractionResult,
    sections: list[DocumentSection],
    chunks: list[DocumentChunk],
) -> tuple[int, bool]:
    """
    Persist extraction output, sections, and chunks.

    If the checksum already exists, returns the existing document id and False
    without creating duplicate rows.
    """
    initialize_database(db_path)

    existing = get_document_by_checksum(db_path, extraction.checksum_sha256)
    if existing is not None:
        return existing.id, False

    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO documents (
                file_path, file_name, file_type, file_size_bytes,
                checksum_sha256, page_count, text, metadata_json,
                extraction_warnings_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                extraction.file_path,
                extraction.file_name,
                extraction.file_type,
                extraction.file_size_bytes,
                extraction.checksum_sha256,
                extraction.page_count,
                extraction.text,
                _json_dumps(extraction.metadata),
                _json_dumps(extraction.extraction_warnings),
            ),
        )
        document_id = int(cursor.lastrowid)

        for section in sections:
            connection.execute(
                """
                INSERT INTO sections (
                    document_id, section_id, title, level,
                    start_line, end_line, parent_section_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    section.section_id,
                    section.title,
                    section.level,
                    section.start_line,
                    section.end_line,
                    section.parent_section_id,
                ),
            )

        for chunk in chunks:
            connection.execute(
                """
                INSERT INTO chunks (
                    document_id, chunk_id, document_name, text, chunk_type,
                    start_line, end_line, section_title, section_id, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    chunk.chunk_id,
                    chunk.document_name,
                    chunk.text,
                    chunk.chunk_type,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.section_title,
                    chunk.section_id,
                    _json_dumps(chunk.metadata),
                ),
            )

        connection.commit()

    return document_id, True


def save_index_bundle(
    db_path: str | Path,
    document_id: int,
    index: InvertedIndex,
    bm25_stats: dict,
) -> bool:
    """
    Persist inverted index postings and BM25 statistics for a document.

    Returns True when a new index is saved, False if one already exists.
    """
    initialize_database(db_path)

    if document_has_index(db_path, document_id):
        return False

    with connect(db_path) as connection:
        for term, document_frequency in bm25_stats.get("df", {}).items():
            connection.execute(
                """
                INSERT INTO index_terms (document_id, term, document_frequency)
                VALUES (?, ?, ?)
                """,
                (document_id, term, int(document_frequency)),
            )

        for chunk_id, chunk_entry in index.chunk_statistics.items():
            metadata = dict(chunk_entry.metadata)
            metadata["normalized_text"] = chunk_entry.normalized_text
            connection.execute(
                "UPDATE chunks SET metadata_json = ? WHERE document_id = ? AND chunk_id = ?",
                (_json_dumps(metadata), document_id, chunk_id),
            )

            for term, frequency in chunk_entry.token_frequencies.items():
                posting = index.term_to_chunks.get(term, {}).get(chunk_id, {})
                positions = posting.get("positions", [])
                connection.execute(
                    """
                    INSERT INTO chunk_term_frequencies (
                        document_id, chunk_id, term, frequency, positions_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        chunk_id,
                        term,
                        int(frequency),
                        _json_dumps(positions),
                    ),
                )

        connection.execute(
            """
            INSERT INTO bm25_statistics (
                document_id, avgdl, document_count, corpus_document_count,
                vocabulary_size, df_json, idf_json, chunk_lengths_json,
                field_weights_json, searchable_term_map_json, bm25_k1, bm25_b,
                vocabulary_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                float(bm25_stats.get("avgdl", 0.0)),
                int(bm25_stats.get("document_count", index.total_chunk_count)),
                int(bm25_stats.get("corpus_document_count", index.document_count)),
                int(bm25_stats.get("vocabulary_size", index.vocabulary_size)),
                _json_dumps(bm25_stats.get("df", {})),
                _json_dumps(bm25_stats.get("idf", {})),
                _json_dumps(bm25_stats.get("chunk_lengths", {})),
                _json_dumps(bm25_stats.get("field_weights", index.field_weights)),
                _json_dumps(bm25_stats.get("searchable_term_map", index.searchable_term_map)),
                float(bm25_stats.get("bm25_k1", 1.5)),
                float(bm25_stats.get("bm25_b", 0.75)),
                _json_dumps(bm25_stats.get("vocabulary", [])),
            ),
        )
        connection.commit()

    return True


def load_bm25_statistics(db_path: str | Path, document_id: int) -> dict:
    """Load BM25 statistics for a document."""
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM bm25_statistics WHERE document_id = ?",
            (document_id,),
        ).fetchone()

    if row is None:
        return {}

    df = _json_loads(row["df_json"], {})
    idf = {term: float(value) for term, value in _json_loads(row["idf_json"], {}).items()}
    chunk_lengths = {
        chunk_id: int(length)
        for chunk_id, length in _json_loads(row["chunk_lengths_json"], {}).items()
    }

    return {
        "df": {term: int(value) for term, value in df.items()},
        "idf": idf,
        "avgdl": float(row["avgdl"]),
        "chunk_lengths": chunk_lengths,
        "document_count": int(row["document_count"]),
        "corpus_document_count": int(row["corpus_document_count"]),
        "vocabulary_size": int(row["vocabulary_size"]),
        "vocabulary": _json_loads(row["vocabulary_json"], []),
        "field_weights": _json_loads(row["field_weights_json"], {}),
        "searchable_term_map": _json_loads(row["searchable_term_map_json"], {}),
        "bm25_k1": float(row["bm25_k1"]),
        "bm25_b": float(row["bm25_b"]),
    }


def load_index_for_document(db_path: str | Path, document_id: int) -> InvertedIndex:
    """Reconstruct an inverted index for a single document."""
    chunks = get_chunks_for_document(db_path, document_id)
    bm25_stats = load_bm25_statistics(db_path, document_id)

    term_to_chunks: dict[str, dict[str, dict[str, Any]]] = {}
    chunk_statistics: dict[str, ChunkIndexEntry] = {}

    with connect(db_path) as connection:
        frequency_rows = connection.execute(
            """
            SELECT chunk_id, term, frequency, positions_json
            FROM chunk_term_frequencies
            WHERE document_id = ?
            """,
            (document_id,),
        ).fetchall()

    frequencies_by_chunk: dict[str, dict[str, int]] = {}
    positions_by_chunk_term: dict[tuple[str, str], list[int]] = {}
    for row in frequency_rows:
        chunk_id = row["chunk_id"]
        term = row["term"]
        frequencies_by_chunk.setdefault(chunk_id, {})[term] = int(row["frequency"])
        positions_by_chunk_term[(chunk_id, term)] = _json_loads(row["positions_json"], [])

        term_to_chunks.setdefault(term, {})[chunk_id] = {
            "frequency": int(row["frequency"]),
            "positions": positions_by_chunk_term[(chunk_id, term)],
        }

    for chunk in chunks:
        token_frequencies = frequencies_by_chunk.get(chunk.chunk_id, {})
        metadata = dict(chunk.metadata)
        normalized_text = metadata.get("normalized_text", "")
        chunk_statistics[chunk.chunk_id] = ChunkIndexEntry(
            chunk_id=chunk.chunk_id,
            document_name=chunk.document_name,
            chunk_type=chunk.chunk_type,
            section_title=chunk.section_title,
            text=chunk.text,
            token_count=sum(token_frequencies.values()),
            unique_token_count=len(token_frequencies),
            normalized_text=normalized_text,
            token_frequencies=token_frequencies,
            metadata=metadata,
        )

    return InvertedIndex(
        term_to_chunks=term_to_chunks,
        chunk_statistics=chunk_statistics,
        document_count=int(bm25_stats.get("corpus_document_count", 1)),
        total_chunk_count=int(bm25_stats.get("document_count", len(chunks))),
        average_chunk_length=float(bm25_stats.get("avgdl", 0.0)),
        vocabulary_size=int(bm25_stats.get("vocabulary_size", len(term_to_chunks))),
        searchable_term_map=dict(bm25_stats.get("searchable_term_map", {})),
        field_weights=dict(bm25_stats.get("field_weights", {})),
    )


def add_audit_event(
    db_path: str | Path,
    event_type: str,
    details: dict,
    document_id: int | None = None,
    message: str | None = None,
) -> None:
    """Insert one audit event into the audit_events table."""
    initialize_database(db_path)
    event_message = message or event_type.replace("_", " ")

    stored_details = dict(details)
    foreign_key_document_id = document_id
    if document_id is not None and get_document_by_id(db_path, document_id) is None:
        foreign_key_document_id = None
        stored_details.setdefault("document_id", document_id)

    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO audit_events (document_id, event_type, message, details_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                foreign_key_document_id,
                event_type,
                event_message,
                _json_dumps(stored_details),
            ),
        )
        connection.commit()


def list_audit_events(
    db_path: str | Path,
    document_id: int | None = None,
    limit: int = 100,
) -> list[AuditEventRecord]:
    """List audit events, optionally filtered by document."""
    query = "SELECT * FROM audit_events"
    params: list[Any] = []
    if document_id is not None:
        query += " WHERE document_id = ?"
        params.append(document_id)
    query += " ORDER BY id ASC LIMIT ?"
    params.append(limit)

    with connect(db_path) as connection:
        rows = connection.execute(query, params).fetchall()

    return [
        AuditEventRecord(
            id=int(row["id"]),
            document_id=row["document_id"],
            event_type=row["event_type"],
            message=row["message"],
            details=_json_loads(row["details_json"], {}),
            created_at=row["created_at"],
        )
        for row in rows
    ]
