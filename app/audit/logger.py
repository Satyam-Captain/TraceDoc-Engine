"""Audit event logging."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.storage.repository import add_audit_event


def _default_message(event_type: str, details: dict[str, Any]) -> str:
    file_name = details.get("file_name")
    question = details.get("question")

    if event_type == "document_processed" and file_name:
        return f"Document processed: {file_name}"
    if event_type == "duplicate_document_detected" and file_name:
        return f"Duplicate document detected: {file_name}"
    if event_type == "document_processing_failed" and file_name:
        return f"Document processing failed: {file_name}"
    if event_type == "question_asked" and question:
        return f"Question asked: {question}"
    if event_type == "question_failed":
        return "Question processing failed"

    return event_type.replace("_", " ")


def log_audit_event(
    db_path: str,
    event_type: str,
    details: dict,
) -> None:
    """Append a deterministic audit event to the local SQLite audit log."""
    document_id = details.get("document_id")
    if document_id is not None:
        document_id = int(document_id)

    add_audit_event(
        db_path=Path(db_path),
        event_type=event_type,
        details=details,
        document_id=document_id,
        message=_default_message(event_type, details),
    )
