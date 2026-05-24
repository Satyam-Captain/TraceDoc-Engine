"""PDF text extraction using pypdf."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from app.ingestion.pdf_layout import reconstruct_pdf_layout


def extract_pdf(file_path: str) -> tuple[str, int, dict[str, Any], list[str]]:
    """
    Extract text and metadata from a PDF file.

    Returns:
        (combined_text, page_count, metadata_dict, warnings)
    """
    warnings: list[str] = []
    metadata: dict[str, Any] = {}
    path = Path(file_path)

    reader = PdfReader(str(path))
    page_count = len(reader.pages)

    if reader.metadata:
        for key, value in reader.metadata.items():
            if value is not None:
                clean_key = str(key).lstrip("/")
                metadata[clean_key] = str(value)

    page_texts: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        extracted = page.extract_text() or ""
        if not extracted.strip():
            warnings.append(f"Page {page_number} contains no extractable text.")
        page_texts.append(extracted)

    text = "\n\n".join(page_texts).strip()
    text = reconstruct_pdf_layout(text)
    return text, page_count, metadata, warnings
