"""Tests for Streamlit app module imports."""

from __future__ import annotations

import importlib
from io import BytesIO
from pathlib import Path

import pytest


class _FakeUploadedFile:
    def __init__(self, name: str, content: bytes) -> None:
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


def test_app_main_imports_successfully() -> None:
    module = importlib.import_module("app.main")

    assert hasattr(module, "main")
    assert hasattr(module, "save_uploaded_file")
    assert hasattr(module, "ANSWER_MODE_LABELS")
    assert hasattr(module, "suggested_demo_questions")
    assert module.DB_PATH.endswith("tracedoc.db")
    assert "GRAPH_STRUCTURED" in module.ANSWER_MODE_LABELS


def test_save_uploaded_file_exists_and_writes_safely(tmp_path: Path) -> None:
    from app.main import save_uploaded_file

    upload_dir = tmp_path / "uploads"
    fake = _FakeUploadedFile("policy.txt", b"HPC6 memory requirements")

    saved_path = save_uploaded_file(fake, upload_dir=str(upload_dir))

    assert Path(saved_path).exists()
    assert Path(saved_path).read_bytes() == b"HPC6 memory requirements"
    assert Path(saved_path).parent.resolve() == upload_dir.resolve()


def test_suggested_demo_questions_prefers_architecture_set() -> None:
    from app.main import DocumentIndexMetadata, suggested_demo_questions

    metadata = DocumentIndexMetadata(
        schema_categories=("Existing architectures",),
        graph_node_count=12,
        graph_edge_count=8,
    )
    suggestions = suggested_demo_questions("system_architectures.txt", metadata)
    assert "what are different architectures mentioned?" in suggestions


def test_save_uploaded_file_rejects_unsafe_paths(tmp_path: Path) -> None:
    from app.main import save_uploaded_file

    fake = _FakeUploadedFile("../escape.txt", b"bad")

    with pytest.raises(ValueError, match="Unsafe upload filename"):
        save_uploaded_file(fake, upload_dir=str(tmp_path / "uploads"))
