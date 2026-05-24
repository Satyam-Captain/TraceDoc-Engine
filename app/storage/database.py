"""SQLite schema initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_type TEXT NOT NULL,
        file_size_bytes INTEGER NOT NULL,
        checksum_sha256 TEXT NOT NULL UNIQUE,
        page_count INTEGER,
        text TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        extraction_warnings_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        section_id TEXT NOT NULL,
        title TEXT NOT NULL,
        level INTEGER NOT NULL,
        start_line INTEGER NOT NULL,
        end_line INTEGER NOT NULL,
        parent_section_id TEXT,
        UNIQUE(document_id, section_id),
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        chunk_id TEXT NOT NULL,
        document_name TEXT NOT NULL,
        text TEXT NOT NULL,
        chunk_type TEXT NOT NULL,
        start_line INTEGER NOT NULL,
        end_line INTEGER NOT NULL,
        section_title TEXT,
        section_id TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(document_id, chunk_id),
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS index_terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        term TEXT NOT NULL,
        document_frequency INTEGER NOT NULL,
        UNIQUE(document_id, term),
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunk_term_frequencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        chunk_id TEXT NOT NULL,
        term TEXT NOT NULL,
        frequency INTEGER NOT NULL,
        positions_json TEXT NOT NULL DEFAULT '[]',
        UNIQUE(document_id, chunk_id, term),
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bm25_statistics (
        document_id INTEGER PRIMARY KEY,
        avgdl REAL NOT NULL,
        document_count INTEGER NOT NULL,
        corpus_document_count INTEGER NOT NULL,
        vocabulary_size INTEGER NOT NULL,
        df_json TEXT NOT NULL,
        idf_json TEXT NOT NULL,
        chunk_lengths_json TEXT NOT NULL,
        field_weights_json TEXT NOT NULL DEFAULT '{}',
        searchable_term_map_json TEXT NOT NULL DEFAULT '{}',
        bm25_k1 REAL NOT NULL DEFAULT 1.5,
        bm25_b REAL NOT NULL DEFAULT 0.75,
        vocabulary_json TEXT NOT NULL DEFAULT '[]',
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        event_type TEXT NOT NULL,
        message TEXT NOT NULL,
        details_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sections_document ON sections(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_index_terms_document ON index_terms(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_chunk_term_freq_document ON chunk_term_frequencies(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_events_document ON audit_events(document_id)",
)


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys enabled."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: str | Path) -> None:
    """Create the TraceDoc SQLite schema if it does not exist."""
    with connect(db_path) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.commit()
