"""PDF text extraction using Docling (v2 stack)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

_CONVERTER: DocumentConverter | None = None

_MULTI_NEWLINE = re.compile(r"\n{3,}")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _normalize_extracted_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return _MULTI_NEWLINE.sub("\n\n", normalized).strip()


def _document_to_text(document: Any) -> str:
    """Build plain text with line breaks from a Docling document."""
    text_items = getattr(document, "texts", None) or []
    if len(text_items) > 1:
        parts = [
            str(getattr(item, "text", item)).strip()
            for item in text_items
            if str(getattr(item, "text", item)).strip()
        ]
        if parts:
            return "\n\n".join(parts)

    markdown = document.export_to_markdown().strip()
    if "\n" in markdown:
        return markdown

    pages = getattr(document, "pages", None) or {}
    if len(pages) > 1:
        page_chunks: list[str] = []
        for page_key in sorted(pages, key=lambda key: int(key) if str(key).isdigit() else str(key)):
            page = pages[page_key]
            export = getattr(page, "export_to_markdown", None)
            if export is None:
                continue
            chunk = export().strip()
            if chunk:
                page_chunks.append(chunk)
        if page_chunks:
            return "\n\n".join(page_chunks)

    if _SENTENCE_BREAK.search(markdown):
        return _SENTENCE_BREAK.sub("\n", markdown)
    return markdown


def _get_converter() -> DocumentConverter:
    global _CONVERTER
    if _CONVERTER is None:
        pipeline_options = PdfPipelineOptions(
            do_ocr=False,
            do_table_structure=False,
            force_backend_text=True,
            do_picture_classification=False,
            do_picture_description=False,
            do_code_enrichment=False,
            do_formula_enrichment=False,
        )
        _CONVERTER = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            },
        )
    return _CONVERTER


def _docling_metadata(document: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {"extractor": "docling"}
    name = getattr(document, "name", None)
    if name:
        metadata["name"] = str(name)
    return metadata


def extract_pdf_docling(file_path: str) -> tuple[str, int | None, dict[str, Any], list[str]]:
    """
    Extract text and metadata from a PDF using Docling.

    Returns:
        (combined_text, page_count, metadata_dict, warnings)

    Raises:
        FileNotFoundError: If the path does not exist.
        RuntimeError: If Docling conversion fails (v2 does not fall back to pypdf).
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    warnings: list[str] = ["docling_v2"]

    try:
        result = _get_converter().convert(str(path))
    except Exception as exc:  # noqa: BLE001 — surface Docling failures to caller
        raise RuntimeError(
            f"Docling PDF extraction failed for '{path.name}': {exc}"
        ) from exc

    if result.status == ConversionStatus.FAILURE or result.document is None:
        errors = getattr(result, "errors", None) or []
        detail = "; ".join(str(item) for item in errors) if errors else result.status
        raise RuntimeError(
            f"Docling PDF extraction failed for '{path.name}': {detail}"
        )

    document = result.document
    text = _normalize_extracted_text(_document_to_text(document))

    page_count: int | None = None
    pages = getattr(document, "pages", None)
    if pages is not None:
        page_count = len(pages)
        warnings.append(f"pages:{page_count}")

    metadata = _docling_metadata(document)
    if result.status == ConversionStatus.PARTIAL_SUCCESS:
        warnings.append("docling_partial_success")

    return text, page_count, metadata, warnings
