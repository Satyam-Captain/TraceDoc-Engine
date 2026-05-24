"""Local SQLite persistence."""

from app.storage.database import connect, initialize_database
from app.storage.models import AuditEventRecord, DocumentRecord
from app.storage.repository import (
    document_has_index,
    get_chunks_for_document,
    get_document_by_checksum,
    get_document_processing_counts,
    list_audit_events,
    list_documents,
    load_bm25_statistics,
    load_index_for_document,
    save_document_bundle,
    save_index_bundle,
)

__all__ = [
    "AuditEventRecord",
    "DocumentRecord",
    "connect",
    "document_has_index",
    "get_chunks_for_document",
    "get_document_by_checksum",
    "get_document_processing_counts",
    "initialize_database",
    "list_audit_events",
    "list_documents",
    "load_bm25_statistics",
    "load_index_for_document",
    "save_document_bundle",
    "save_index_bundle",
]
