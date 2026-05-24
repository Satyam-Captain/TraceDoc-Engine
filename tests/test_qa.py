"""Tests for document question-answer orchestration."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from app.pipeline import process_document
from app.qa import DocumentQAResult, ask_document
from app.storage import get_document_by_id, save_document_bundle
from app.ingestion.models import DocumentExtractionResult
from app.structure import structure_document


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


def test_ask_document_returns_evidence_only(tmp_path: Path) -> None:
    db_path, document_id = _process_sample(tmp_path)

    answer = ask_document(
        "What are the HPC6 memory requirements?",
        document_id,
        db_path=str(db_path),
    )

    assert answer.answer_mode == "EVIDENCE_ONLY"
    assert answer.document_name == "policy.txt"
    assert answer.cards
    assert answer.cards[0].document_name == "policy.txt"
    assert "policy.txt" in answer.cards[0].citation


def test_no_matching_question_returns_no_evidence(tmp_path: Path) -> None:
    db_path, document_id = _process_sample(tmp_path)

    answer = ask_document(
        "zzzz-unknown-term-zzzz",
        document_id,
        db_path=str(db_path),
    )

    assert answer.answer_mode == "NO_EVIDENCE"
    assert answer.cards == []
    assert answer.no_evidence_message is not None


def test_empty_question_returns_no_evidence(tmp_path: Path) -> None:
    db_path, document_id = _process_sample(tmp_path)

    answer = ask_document("   ", document_id, db_path=str(db_path))

    assert answer.answer_mode == "NO_EVIDENCE"
    assert answer.cards == []


def test_invalid_document_id_raises_value_error(tmp_path: Path) -> None:
    db_path, _ = _process_sample(tmp_path)

    with pytest.raises(ValueError, match="Document not found"):
        ask_document("HPC6", 99999, db_path=str(db_path))


def test_missing_index_raises_value_error(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"
    source = tmp_path / "bare.txt"
    source.write_text("Alpha beta gamma.", encoding="utf-8")

    extraction = DocumentExtractionResult(
        file_path=str(source),
        file_name=source.name,
        file_type="txt",
        file_size_bytes=source.stat().st_size,
        checksum_sha256="bare-checksum-001",
        page_count=None,
        text=source.read_text(encoding="utf-8"),
    )
    sections, chunks = structure_document(source.name, extraction.text)
    document_id, _ = save_document_bundle(
        str(db_path), extraction, sections, chunks
    )

    with pytest.raises(ValueError, match="No lexical index found"):
        ask_document("alpha", document_id, db_path=str(db_path))


def test_top_k_and_max_cards_respected(tmp_path: Path) -> None:
    db_path, document_id = _process_sample(tmp_path)

    answer = ask_document(
        "HPC6 memory REQ-001",
        document_id,
        db_path=str(db_path),
        top_k=1,
        max_cards=1,
    )

    assert len(answer.cards) <= 1


def test_no_generated_answer_field(tmp_path: Path) -> None:
    db_path, document_id = _process_sample(tmp_path)

    answer = ask_document("HPC6 memory", document_id, db_path=str(db_path))
    field_names = {field.name for field in fields(DocumentQAResult)}

    assert "answer" not in field_names
    assert "generated_answer" not in field_names
    assert answer.explanation


def test_get_document_by_id(tmp_path: Path) -> None:
    db_path, document_id = _process_sample(tmp_path)

    document = get_document_by_id(db_path, document_id)

    assert document is not None
    assert document.id == document_id
    assert document.file_name == "policy.txt"
