"""Local SQLite persistence."""

from app.storage.cleanup import clear_local_data
from app.storage.database import connect, initialize_database
from app.storage.models import AuditEventRecord, DocumentRecord, StoredChunk, StoredSection
from app.storage.repository import (
    add_audit_event,
    document_has_index,
    get_chunks_for_document,
    get_sections_for_document,
    get_document_by_checksum,
    get_document_by_id,
    get_document_processing_counts,
    list_audit_events,
    list_documents,
    load_bm25_statistics,
    load_document_schema,
    load_document_tree,
    load_index_for_document,
    save_document_bundle,
    save_document_schema,
    save_document_tree,
    save_index_bundle,
)

__all__ = [
    "AuditEventRecord",
    "DocumentRecord",
    "StoredChunk",
    "StoredSection",
    "add_audit_event",
    "clear_local_data",
    "connect",
    "document_has_index",
    "get_chunks_for_document",
    "get_sections_for_document",
    "get_document_by_checksum",
    "get_document_by_id",
    "get_document_processing_counts",
    "initialize_database",
    "list_audit_events",
    "list_documents",
    "load_bm25_statistics",
    "load_document_schema",
    "load_document_tree",
    "load_index_for_document",
    "save_document_bundle",
    "save_document_schema",
    "save_document_tree",
    "save_index_bundle",
]
