"""Document ingestion: extract raw text and metadata from local files."""

from app.ingestion.extractor import compute_checksum_sha256, extract_document
from app.ingestion.models import DocumentExtractionResult

__all__ = [
    "DocumentExtractionResult",
    "compute_checksum_sha256",
    "extract_document",
]
