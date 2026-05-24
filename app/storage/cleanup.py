"""Clear local TraceDoc persistence (database, uploads, index cache)."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.storage.database import connect


def _remove_path(path: Path) -> bool:
    """Remove a file or directory; return True if something was removed."""
    if not path.exists():
        return False
    if path.is_file():
        path.unlink()
        return True
    shutil.rmtree(path)
    return True


def _clear_directory_contents(directory: Path) -> int:
    """Delete all files and subfolders inside directory; recreate empty dir."""
    removed = 0
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
        return removed

    for item in directory.iterdir():
        if _remove_path(item):
            removed += 1
    return removed


def _wipe_database_tables(db_path: Path) -> None:
    """Delete all rows when the database file cannot be removed (e.g. file lock)."""
    table_names = (
        "chunk_term_frequencies",
        "index_terms",
        "bm25_statistics",
        "chunks",
        "sections",
        "audit_events",
        "documents",
    )
    with connect(db_path) as connection:
        for table in table_names:
            connection.execute(f"DELETE FROM {table}")
        connection.commit()
        connection.execute("VACUUM")


def clear_local_data(
    db_path: str | Path,
    *,
    upload_dir: str | Path | None = None,
    index_dir: str | Path | None = None,
) -> dict[str, int | bool | str]:
    """
    Remove the UI database, uploaded files, and optional index directory.

    Returns a small report dict for display in the UI.
    """
    db_file = Path(db_path)
    data_root = db_file.parent
    uploads = Path(upload_dir) if upload_dir else data_root / "uploads"
    index = Path(index_dir) if index_dir else data_root / "index"

    report: dict[str, int | bool | str] = {
        "database_removed": False,
        "upload_items_removed": 0,
        "index_items_removed": 0,
        "error": "",
    }

    try:
        if db_file.exists():
            try:
                db_file.unlink()
            except OSError:
                _wipe_database_tables(db_file)
            report["database_removed"] = True

        report["upload_items_removed"] = _clear_directory_contents(uploads)
        report["index_items_removed"] = _clear_directory_contents(index)

        for keep_dir in (uploads, index):
            keep_dir.mkdir(parents=True, exist_ok=True)
            gitkeep = keep_dir / ".gitkeep"
            if not gitkeep.exists():
                gitkeep.touch()
    except OSError as error:
        report["error"] = str(error)
        report["database_removed"] = False

    return report
