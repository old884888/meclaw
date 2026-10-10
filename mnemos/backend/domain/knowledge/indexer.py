"""SQLite FTS index for knowledge notes."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .paths import KnowledgePaths
from .store import list_notes, read_note_file


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS notes_index (
            note_id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL UNIQUE,
            title TEXT,
            category TEXT,
            tags TEXT,
            source_id TEXT,
            source_url TEXT,
            created_at TEXT,
            search_text TEXT,
            body TEXT,
            file_mtime REAL DEFAULT 0
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            note_id UNINDEXED,
            title UNINDEXED,
            category UNINDEXED,
            tags UNINDEXED,
            search_text,
            body UNINDEXED,
            tokenize='unicode61'
        );
        """
    )
    conn.commit()


def rebuild_index(paths: KnowledgePaths) -> None:
    paths.index_db.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(paths.index_db)
    _init_schema(conn)
    conn.execute("DELETE FROM notes_index")
    conn.execute("DELETE FROM notes_fts")
    for note in list_notes(paths):
        _upsert_note(conn, note)
    conn.commit()
    conn.close()


def index_note(paths: KnowledgePaths, note: dict) -> None:
    paths.index_db.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(paths.index_db)
    _init_schema(conn)
    _upsert_note(conn, note)
    conn.commit()
    conn.close()


def _upsert_note(conn: sqlite3.Connection, note: dict) -> None:
    path = Path(note["path"])
    meta = note.get("meta") or {}
    tags = note.get("tags") or []
    body = note.get("body") or ""
    title = note.get("title") or ""
    category = note.get("category") or ""
    search_text = " ".join(
        [
            title,
            category,
            " ".join(tags),
            body,
        ]
    ).strip()
    note_id = note.get("id") or path.stem
    conn.execute("DELETE FROM notes_index WHERE note_id = ?", (note_id,))
    conn.execute("DELETE FROM notes_fts WHERE note_id = ?", (note_id,))
    conn.execute(
        """
        INSERT INTO notes_index
        (note_id, file_path, title, category, tags, source_id, source_url, created_at, search_text, body, file_mtime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            note_id,
            str(path),
            title,
            category,
            ",".join(tags),
            note.get("source_id") or meta.get("source_id") or "",
            note.get("source_url") or meta.get("source_url") or "",
            note.get("created_at") or meta.get("created_at") or "",
            search_text,
            body,
            path.stat().st_mtime if path.exists() else 0,
        ),
    )
    conn.execute(
        "INSERT INTO notes_fts (note_id, title, category, tags, search_text, body) VALUES (?, ?, ?, ?, ?, ?)",
        (note_id, title, category, ",".join(tags), search_text, body),
    )


def search_notes(paths: KnowledgePaths, query: str, limit: int = 8) -> list[dict]:
    if not query.strip():
        return []
    if not paths.index_db.exists():
        rebuild_index(paths)
    conn = _connect(paths.index_db)
    _init_schema(conn)
    q = query.strip().replace('"', '""')
    rows = conn.execute(
        """
        SELECT n.note_id, n.title, n.category, n.tags, n.source_id, n.source_url, n.created_at,
               snippet(notes_fts, 4, '[', ']', '…', 20) AS snippet
        FROM notes_fts f
        JOIN notes_index n ON n.note_id = f.note_id
        WHERE notes_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (q, limit),
    ).fetchall()
    conn.close()
    results = []
    for row in rows:
        results.append(
            {
                "id": row["note_id"],
                "title": row["title"],
                "category": row["category"],
                "tags": [x for x in (row["tags"] or "").split(",") if x],
                "source_id": row["source_id"],
                "source_url": row["source_url"],
                "created_at": row["created_at"],
                "snippet": row["snippet"] or "",
            }
        )
    return results
