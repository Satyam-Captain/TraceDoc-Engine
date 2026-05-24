"""Document extraction dispatcher."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.ingestion.docx_extractor import extract_docx
from app.ingestion.models import DocumentExtractionResult
from app.ingestion.pdf_extractor import extract_pdf
from app.ingestion.txt_extractor import extract_txt

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def compute_checksum_sha256(file_path: str) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    digest = hashlib.sha256()
    path = Path(file_path)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_document(file_path: str) -> DocumentExtractionResult:
    """
    Extract raw text and metadata from a local PDF, DOCX, or TXT file.

    Raises:
        FileNotFoundError: If the path does not exist or is not a file.
        ValueError: If the file extension is not supported.
    """
    path = Path(file_path).resolve()

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    extension = path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(
            f"Unsupported file type '{extension}'. Supported types: {supported}"
        )

    checksum = compute_checksum_sha256(str(path))
    file_size = path.stat().st_size

    if extension == ".pdf":
        text, page_count, metadata, warnings = extract_pdf(str(path))
        file_type = "pdf"
    elif extension == ".docx":
        text, page_count, metadata, warnings = extract_docx(str(path))
        file_type = "docx"
    else:
        text, page_count, metadata, warnings = extract_txt(str(path))
        file_type = "txt"

    return DocumentExtractionResult(
        file_path=str(path),
        file_name=path.name,
        file_type=file_type,
        file_size_bytes=file_size,
        checksum_sha256=checksum,
        page_count=page_count,
        text=text,
        metadata=metadata,
        extraction_warnings=warnings,
    )
