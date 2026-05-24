"""Tests for local data cleanup."""

from __future__ import annotations

from pathlib import Path

from app.storage.cleanup import clear_local_data
from app.storage.database import initialize_database
from app.storage.repository import list_documents


def test_clear_local_data_removes_db_and_uploads(tmp_path: Path) -> None:
    db_path = tmp_path / "tracedoc.db"
    upload_dir = tmp_path / "uploads"
    index_dir = tmp_path / "index"

    initialize_database(db_path)
    upload_dir.mkdir(parents=True)
    index_dir.mkdir(parents=True)
    (upload_dir / "sample.txt").write_text("uploaded", encoding="utf-8")
    (index_dir / "cache.bin").write_bytes(b"data")

    report = clear_local_data(
        db_path,
        upload_dir=upload_dir,
        index_dir=index_dir,
    )

    assert report["database_removed"] is True
    assert not report.get("error")
    assert report["upload_items_removed"] >= 1
    assert report["index_items_removed"] >= 1
    assert list_documents(db_path) == []
    assert not any(upload_dir.iterdir()) or all(
        item.name == ".gitkeep" for item in upload_dir.iterdir()
    )
    assert upload_dir.exists()
    assert index_dir.exists()
