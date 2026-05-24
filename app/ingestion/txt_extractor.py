"""Plain-text file extraction with encoding fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_txt(file_path: str) -> tuple[str, None, dict[str, Any], list[str]]:
    """
    Read a text file as UTF-8, falling back to latin-1 if needed.

    Returns:
        (text, page_count, metadata_dict, warnings)
    """
    warnings: list[str] = []
    metadata: dict[str, Any] = {"encoding": "utf-8"}
    path = Path(file_path)
    raw = path.read_bytes()

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
        metadata["encoding"] = "latin-1"
        warnings.append("UTF-8 decode failed; used latin-1 fallback encoding.")

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text, None, metadata, warnings
