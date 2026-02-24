import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

SPACE_RE = re.compile(r"\s+")
ALNUM_RE = re.compile(r"[^a-z0-9]+")


def base_key(name: str) -> str:
    base = Path(name.strip()).name
    if "." in base:
        base = Path(base).stem
    return base.strip()


def normalize_key(name: str) -> str:
    key = base_key(name).lower()
    return SPACE_RE.sub(" ", key).strip()


def compact_key(name: str) -> str:
    return ALNUM_RE.sub("", normalize_key(name))


def ensure_pdf_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS pdf_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            path TEXT NOT NULL,
            mtime REAL,
            size INTEGER
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pdf_files_source_path ON pdf_files(source, path);

        CREATE TABLE IF NOT EXISTS pdf_keys (
            key TEXT NOT NULL,
            pdf_id INTEGER NOT NULL,
            FOREIGN KEY(pdf_id) REFERENCES pdf_files(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_pdf_keys_key ON pdf_keys(key);
        """
    )
    conn.commit()


def reindex_source(conn: sqlite3.Connection, source: str, root_path: str) -> int:
    ensure_pdf_schema(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    to_delete = [row[0] for row in conn.execute("SELECT id FROM pdf_files WHERE source = ?", (source,))]
    if to_delete:
        conn.executemany("DELETE FROM pdf_keys WHERE pdf_id = ?", [(pdf_id,) for pdf_id in to_delete])
        conn.execute("DELETE FROM pdf_files WHERE source = ?", (source,))

    root = Path(root_path)
    count = 0
    if not root.exists():
        conn.commit()
        return 0

    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if not filename.lower().endswith(".pdf"):
                continue
            full_path = str(Path(dirpath) / filename)
            st = os.stat(full_path)
            cur = conn.execute(
                "INSERT INTO pdf_files(source, path, mtime, size) VALUES(?, ?, ?, ?)",
                (source, full_path, st.st_mtime, st.st_size),
            )
            pdf_id = cur.lastrowid
            raw = base_key(filename)
            norm = normalize_key(filename)
            compact = compact_key(filename)
            keys = {raw, raw.lower(), norm, compact}
            conn.executemany("INSERT INTO pdf_keys(key, pdf_id) VALUES(?, ?)", [(k, pdf_id) for k in keys if k])
            count += 1

    conn.commit()
    return count


def find_pdf(conn: sqlite3.Connection, key: str, source: str) -> Optional[str]:
    normalized = normalize_key(key)
    compact = compact_key(key)
    raw = base_key(key)
    for candidate in (raw, raw.lower(), normalized, compact):
        row = conn.execute(
            """
            SELECT f.path
            FROM pdf_keys k
            JOIN pdf_files f ON f.id = k.pdf_id
            WHERE f.source = ? AND k.key = ?
            ORDER BY f.path ASC
            LIMIT 1
            """,
            (source, candidate),
        ).fetchone()
        if row:
            return row[0]
    return None
