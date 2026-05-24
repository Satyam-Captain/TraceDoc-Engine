"""Tests for audit logging and traceability."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.audit import log_audit_event
from app.pipeline import process_document
from app.qa import ask_document
from app.storage import add_audit_event, list_audit_events


def _write_policy_txt(path: Path) -> None:
    path.write_text(
        "# Security Policy\n\n"
        "HPC6 cluster memory requirements are documented.\n\n"
        "REQ-001 defines baseline controls.\n",
        encoding="utf-8",
    )


def _process_sample(tmp_path: Path) -> tuple[Path, int]:
    source = tmp_path / "policy.txt"
    db_path = tmp_path / "tracedoc.db"
    _write_policy_txt(source)
    result = process_document(str(source), db_path=str(db_path))
    return db_path, result.document_id


def test_audit_event_can_be_logged(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"

    log_audit_event(
        str(db_path),
        "test_event",
        {"file_name": "sample.txt"},
    )

    events = list_audit_events(db_path)
    assert len(events) == 1
    assert events[0].event_type == "test_event"
    assert events[0].details["file_name"] == "sample.txt"
    assert events[0].document_id is None


def test_add_audit_event_helper(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"

    add_audit_event(
        db_path,
        "helper_event",
        {"status": "ok"},
        message="Helper event logged",
    )

    events = list_audit_events(db_path)
    assert events[0].event_type == "helper_event"
    assert events[0].document_id is None


def test_process_document_creates_audit_event(tmp_path: Path) -> None:
    db_path, document_id = _process_sample(tmp_path)

    events = list_audit_events(db_path, document_id=document_id)
    event_types = [event.event_type for event in events]

    assert "document_processed" in event_types
    processed = next(
        event for event in events if event.event_type == "document_processed"
    )
    assert processed.details["file_name"] == "policy.txt"
    assert processed.details["chunk_count"] >= 1


def test_duplicate_processing_creates_duplicate_audit_event(tmp_path: Path) -> None:
    source = tmp_path / "policy.txt"
    db_path = tmp_path / "tracedoc.db"
    _write_policy_txt(source)

    process_document(str(source), db_path=str(db_path))
    process_document(str(source), db_path=str(db_path))

    events = list_audit_events(db_path)
    event_types = [event.event_type for event in events]

    assert event_types.count("document_processed") == 2
    assert "duplicate_document_detected" in event_types


def test_ask_document_creates_question_asked_event(tmp_path: Path) -> None:
    db_path, document_id = _process_sample(tmp_path)

    ask_document("HPC6 memory", document_id, db_path=str(db_path))

    events = list_audit_events(db_path, document_id=document_id)
    asked = next(event for event in events if event.event_type == "question_asked")

    assert asked.details["question"] == "HPC6 memory"
    assert asked.details["answer_mode"] == "EVIDENCE_ONLY"
    assert asked.details["evidence_card_count"] >= 1
    assert asked.details["top_score"] is not None


def test_failed_question_creates_question_failed_event(tmp_path: Path) -> None:
    db_path, document_id = _process_sample(tmp_path)

    with pytest.raises(ValueError, match="Document not found"):
        ask_document("HPC6", 99999, db_path=str(db_path))

    events = list_audit_events(db_path)
    failed = [event for event in events if event.event_type == "question_failed"]
    assert failed
    assert "Document not found" in failed[-1].details["error"]


def test_document_processing_failed_audit_event(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"

    with pytest.raises(FileNotFoundError):
        process_document(str(tmp_path / "missing.txt"), db_path=str(db_path))

    events = list_audit_events(db_path)
    assert any(event.event_type == "document_processing_failed" for event in events)


def test_audit_events_can_be_listed(tmp_path: Path) -> None:
    db_path, document_id = _process_sample(tmp_path)
    ask_document("memory", document_id, db_path=str(db_path))

    all_events = list_audit_events(db_path, limit=50)
    doc_events = list_audit_events(db_path, document_id=document_id, limit=50)

    assert len(all_events) >= len(doc_events)
    assert all(event.document_id == document_id for event in doc_events)
