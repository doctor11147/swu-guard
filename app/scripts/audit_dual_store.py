"""Read-only audit for legacy SQLite, MySQL face_embeddings, and FAISS ids.

This script is intentionally diagnostic only. It never writes to SQLite,
MySQL, or the FAISS index.
"""
from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
from pathlib import Path
from typing import Iterable

import faiss
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.settings import Settings
from app.store.session import db_session


def _id_range(ids: list[int]) -> tuple[int | None, int | None]:
    if not ids:
        return None, None
    return min(ids), max(ids)


def _brief(ids: Iterable[int], limit: int) -> str:
    values = sorted({int(i) for i in ids})
    shown = values[:limit]
    suffix = ", ..." if len(values) > limit else ""
    return "[" + ", ".join(str(i) for i in shown) + suffix + "]"


def _read_sqlite_ids(db_path: Path) -> tuple[list[int], str | None]:
    if not db_path.exists():
        return [], f"SQLite file not found: {db_path}"

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            table_exists = conn.execute(
                "select 1 from sqlite_master where type='table' and name='embeddings'",
            ).fetchone()
            if table_exists is None:
                return [], "SQLite table 'embeddings' not found"

            rows = conn.execute("select id from embeddings order by id").fetchall()
            return [int(row[0]) for row in rows], None
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - diagnostic script
        return [], f"SQLite read failed: {type(exc).__name__}: {exc}"


def _read_faiss_ids(faiss_path: Path) -> tuple[list[int], int, str | None]:
    if not faiss_path.exists():
        return [], 0, f"FAISS file not found: {faiss_path}"

    try:
        index = faiss.read_index(str(faiss_path))
        ntotal = int(index.ntotal)
        if not hasattr(index, "id_map"):
            return [], ntotal, "FAISS index has no id_map; cannot list explicit ids"
        ids = [int(i) for i in faiss.vector_to_array(index.id_map)]
        return ids, ntotal, None
    except Exception as exc:  # pragma: no cover - diagnostic script
        return [], 0, f"FAISS read failed: {type(exc).__name__}: {exc}"


async def _read_mysql_ids() -> tuple[list[int], str | None]:
    try:
        async with db_session() as session:
            result = await session.execute(text("select id from face_embeddings order by id"))
            return [int(row[0]) for row in result.fetchall()], None
    except Exception as exc:  # pragma: no cover - diagnostic script
        return [], f"MySQL read failed: {type(exc).__name__}: {exc}"


def _print_source(name: str, ids: list[int], error: str | None, ntotal: int | None = None) -> None:
    unique = len(set(ids))
    duplicates = len(ids) - unique
    count_text = f"ntotal={ntotal}, ids={len(ids)}" if ntotal is not None else f"count={len(ids)}"
    print(f"{name:<16} {count_text}, unique={unique}, duplicates={duplicates}, range={_id_range(ids)}")
    if error:
        print(f"{name:<16} warning: {error}")


def _print_set(label: str, ids: set[int], limit: int) -> None:
    print(f"{label:<34} {len(ids):>5} {_brief(ids, limit)}")


def _legacy_code_active() -> tuple[bool, list[str]]:
    """Return whether removed SQLite legacy code still appears active."""
    checks: list[tuple[Path, str, str]] = [
        (PROJECT_ROOT / "app/api/routes_persons.py", "", "legacy persons route file exists"),
        (PROJECT_ROOT / "app/api/routes_recognize.py", "", "legacy recognize route file exists"),
        (PROJECT_ROOT / "app/store/db.py", "", "legacy SQLite store module exists"),
        (PROJECT_ROOT / "app/api/main.py", "legacy_persons_router", "legacy persons router imported/mounted"),
        (PROJECT_ROOT / "app/api/main.py", "legacy_recognize_router", "legacy recognize router imported/mounted"),
        (PROJECT_ROOT / "app/api/state.py", "SessionLocal", "AppState still exposes SessionLocal"),
        (PROJECT_ROOT / "app/api/state.py", "app.store.db", "AppState still imports legacy SQLite store"),
    ]
    reasons: list[str] = []
    for path, needle, reason in checks:
        if not path.exists():
            continue
        if not needle:
            reasons.append(reason)
            continue
        try:
            if needle in path.read_text(encoding="utf-8"):
                reasons.append(reason)
        except UnicodeDecodeError:
            continue
    return bool(reasons), reasons


async def _amain() -> int:
    parser = argparse.ArgumentParser(description="Read-only dual-store id audit")
    parser.add_argument("--sqlite", type=Path, default=None, help="legacy SQLite app.db path")
    parser.add_argument("--faiss", type=Path, default=None, help="FAISS index path")
    parser.add_argument("--limit", type=int, default=30, help="max ids to print per set")
    args = parser.parse_args()

    settings = Settings.load()
    sqlite_path = args.sqlite or (settings.data_dir / "app.db")
    faiss_path = args.faiss or (settings.data_dir / "faces.faiss")

    sqlite_ids, sqlite_error = _read_sqlite_ids(sqlite_path)
    faiss_ids, faiss_ntotal, faiss_error = _read_faiss_ids(faiss_path)
    mysql_ids, mysql_error = await _read_mysql_ids()

    sqlite_set = set(sqlite_ids)
    faiss_set = set(faiss_ids)
    mysql_set = set(mysql_ids)
    legacy_active, legacy_reasons = _legacy_code_active()

    print("Dual-store audit report (read-only)")
    print(f"SQLite app.db : {sqlite_path}")
    print(f"FAISS index   : {faiss_path}")
    print()
    _print_source("SQLite embeddings", sqlite_ids, sqlite_error)
    _print_source("MySQL face_emb", mysql_ids, mysql_error)
    _print_source("FAISS", faiss_ids, faiss_error, ntotal=faiss_ntotal)
    print(f"Legacy SQLite code active: {'YES' if legacy_active else 'NO'}")
    if legacy_reasons:
        for reason in legacy_reasons:
            print(f"  - {reason}")
    print()

    sqlite_mysql_overlap = sqlite_set & mysql_set
    sqlite_faiss_overlap = sqlite_set & faiss_set
    faiss_orphans = faiss_set - mysql_set
    mysql_missing = mysql_set - faiss_set
    faiss_sqlite_only = (faiss_set & sqlite_set) - mysql_set

    _print_set("SQLite ∩ MySQL id overlap", sqlite_mysql_overlap, args.limit)
    _print_set("SQLite ∩ FAISS id overlap", sqlite_faiss_overlap, args.limit)
    _print_set("FAISS ids missing in MySQL", faiss_orphans, args.limit)
    _print_set("MySQL ids missing in FAISS", mysql_missing, args.limit)
    _print_set("FAISS ids only explained by SQLite", faiss_sqlite_only, args.limit)
    print()

    if mysql_error:
        risk = "UNKNOWN"
        advice = "Fix MySQL connectivity, then rerun this audit."
    elif legacy_active and (sqlite_mysql_overlap or faiss_sqlite_only):
        risk = "HIGH"
        advice = "Unmount legacy routes before serving traffic; inspect overlapping ids before cleanup."
    elif faiss_orphans or mysql_missing:
        risk = "MEDIUM"
        advice = "Run a FAISS/MySQL consistency repair plan before production use."
    elif sqlite_mysql_overlap or sqlite_faiss_overlap:
        risk = "INFO"
        advice = "Historical SQLite ids overlap, but legacy SQLite code is inactive; active MySQL and FAISS ids are consistent."
    elif sqlite_ids:
        risk = "LOW"
        advice = "Legacy SQLite data exists but does not explain active FAISS ids."
    else:
        risk = "OK"
        advice = "No dual-store id collision evidence found."

    print(f"Risk: {risk}")
    print(f"Advice: {advice}")
    return 0


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
