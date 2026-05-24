"""DOCX text extraction using python-docx."""

from __future__ import annotations

from typing import Any

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


def _table_to_text(table: Table) -> str:
    rows: list[str] = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        rows.append(" | ".join(cells))
    return "\n".join(rows)


def _iter_block_items(document: DocxDocument):
    """Yield paragraphs and tables in document order."""
    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _core_properties_metadata(document: DocxDocument) -> dict[str, Any]:
    props = document.core_properties
    field_names = (
        "author",
        "category",
        "comments",
        "content_status",
        "created",
        "identifier",
        "keywords",
        "language",
        "last_modified_by",
        "last_printed",
        "modified",
        "revision",
        "subject",
        "title",
        "version",
    )
    metadata: dict[str, Any] = {}
    for name in field_names:
        value = getattr(props, name, None)
        if value is not None:
            metadata[name] = str(value)
    return metadata


def extract_docx(file_path: str) -> tuple[str, None, dict[str, Any], list[str]]:
    """
    Extract text and metadata from a DOCX file.

    Returns:
        (combined_text, page_count, metadata_dict, warnings)
    """
    warnings: list[str] = []
    document = Document(file_path)
    metadata = _core_properties_metadata(document)

    blocks: list[str] = []
    for block in _iter_block_items(document):
        if isinstance(block, Paragraph):
            paragraph_text = block.text.strip()
            if paragraph_text:
                blocks.append(paragraph_text)
        elif isinstance(block, Table):
            table_text = _table_to_text(block).strip()
            if table_text:
                blocks.append(table_text)

    text = "\n\n".join(blocks).strip()
    return text, None, metadata, warnings
