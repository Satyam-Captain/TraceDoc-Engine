"""Tests for Docling PDF extraction (v2 stack)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("docling")

from app.ingestion.docling_extractor import extract_pdf_docling
from app.ingestion.extractor import extract_document

_TINY_PDF_BYTES = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>endobj
4 0 obj<</Length 92>>stream
BT /F1 12 Tf 72 720 Td (TraceDoc test line one.) Tj 0 -16 Td (TraceDoc test line two.) Tj ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000274 00000 n 
0000000417 00000 n 
trailer<</Size 6/Root 1 0 R>>
startxref
496
%%EOF"""


@pytest.fixture
def tiny_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "tiny.pdf"
    pdf_path.write_bytes(_TINY_PDF_BYTES)
    return pdf_path


def test_extract_pdf_docling_returns_text_with_newlines(tiny_pdf: Path) -> None:
    text, page_count, metadata, warnings = extract_pdf_docling(str(tiny_pdf))

    assert text.strip()
    assert "TraceDoc" in text
    assert "\n" in text
    assert page_count == 1
    assert metadata.get("extractor") == "docling"
    assert "docling_v2" in warnings
    assert any(w.startswith("pages:") for w in warnings)


def test_extract_document_v2_dispatch(tiny_pdf: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRACEDOC_EXTRACTOR", "v2")

    result = extract_document(str(tiny_pdf))

    assert result.file_type == "pdf"
    assert result.metadata.get("extractor_version") == "v2"
    assert "TraceDoc" in result.text
    assert "docling_v2" in result.extraction_warnings


def test_extract_document_v1_unchanged(tiny_pdf: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRACEDOC_EXTRACTOR", "v1")

    from unittest.mock import MagicMock, patch

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "flat pdf text"

    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]
    mock_reader.metadata = {}

    with patch("app.ingestion.pdf_extractor.PdfReader", return_value=mock_reader):
        result = extract_document(str(tiny_pdf))

    assert result.metadata.get("extractor_version") == "v1"
    assert "flat pdf text" in result.text
