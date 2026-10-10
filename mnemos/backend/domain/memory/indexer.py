"""SQLite FTS index for personal memory (L1/L2)."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from .embedding.vectors import blob_to_vector, vector_to_blob
from .paths import BotMemoryPaths
from .store_l1 import list_atoms, read_atom_file
from .store_l2 import read_session_summary

if TYPE_CHECKING:
    from .embedding.port import EmbeddingPort

FTS_SPECIAL_RE = re.compile(r'["\'\\?\*:^()\[\]{}~/-]')
INDEX_SCHEMA_VERSION = 3


def sanitize_fts_query(query: str) -> str:
    """Strip characters that break SQLite FTS5 MATCH syntax."""
    text = FTS_SPECIAL_RE.sub(" ", query or "")
    text = text.replace('"', " ")
    return " ".join(text.split())


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS memory_index (
            record_id TEXT PRIMARY KEY,
            layer TEXT,
            file_path TEXT NOT NULL,
            record_type TEXT,
            session_id TEXT,
            search_text TEXT,
            body TEXT,
            file_mtime REAL DEFAULT 0
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            record_id UNINDEXED,
            layer UNINDEXED,
            record_type UNINDEXED,
            session_id UNINDEXED,
            search_text,
            body UNINDEXED,
            tokenize='unicode61'
        );
        """
    )
    _migrate_schema(conn)
    conn.commit()


def _migrate_schema(conn: sqlite3.Connection) -> None:
    version = int(conn.execute("PRAGMA user_version").fetchone()[0] or 0)
    if version >= INDEX_SCHEMA_VERSION:
        return
    cols = {row[1] for row in conn.execute("PRAGMA table_info(memory_index)")}
    if "embedding" not in cols:
        conn.execute("ALTER TABLE memory_index ADD COLUMN embedding BLOB")
    if "embedding_model" not in cols:
        conn.execute("ALTER TABLE memory_index ADD COLUMN embedding_model TEXT")
    if "subject" not in cols:
        conn.execute("ALTER TABLE memory_index ADD COLUMN subject TEXT DEFAULT ''")
    if "predicate" not in cols:
        conn.execute("ALTER TABLE memory_index ADD COLUMN predicate TEXT DEFAULT ''")
    if "object" not in cols:
        conn.execute("ALTER TABLE memory_index ADD COLUMN object TEXT DEFAULT ''")
    conn.execute(f"PRAGMA user_version = {INDEX_SCHEMA_VERSION}")


def _embed_body(port: EmbeddingPort | None, body: str) -> tuple[bytes | None, str | None]:
    if port is None or not port.available:
        return None, None
    text = (body or "").strip()
    if not text:
        return None, None
    try:
        vectors = port.embed([text])
    except Exception:  # noqa: BLE001
        return None, None
    if not vectors or not vectors[0]:
        return None, None
    return vector_to_blob(vectors[0]), port.model_identity


def rebuild_index(
    paths: BotMemoryPaths,
    history_dir: Path | None = None,
    extra_l2: list[dict] | None = None,
    *,
    embedding_port: EmbeddingPort | None = None,
) -> None:
    paths.index_db.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(paths.index_db)
    _init_schema(conn)
    conn.execute("DELETE FROM memory_index")
    conn.execute("DELETE FROM memory_fts")
    for atom in list_atoms(paths):
        _upsert_record(
            conn,
            atom["id"],
            "L1",
            atom["path"],
            atom.get("type", ""),
            atom.get("session_id", ""),
            atom["content"],
            embedding_port=embedding_port,
            subject=str(atom.get("subject") or ""),
            predicate=str(atom.get("predicate") or ""),
            object_=str(atom.get("object") or ""),
        )
    for item in extra_l2 or []:
        rid = f"l2_{item.get('session_id', '')}"
        body = item.get("summary") or ""
        _upsert_record(
            conn,
            rid,
            "L2",
            "",
            "session_summary",
            item.get("session_id", ""),
            body,
            embedding_port=embedding_port,
        )
    conn.commit()
    conn.close()


def index_atom(
    paths: BotMemoryPaths,
    atom: dict,
    *,
    embedding_port: EmbeddingPort | None = None,
) -> None:
    paths.index_db.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(paths.index_db)
    _init_schema(conn)
    _upsert_record(
        conn,
        atom["id"],
        "L1",
        atom["path"],
        atom.get("type", ""),
        atom.get("session_id", ""),
        atom["content"],
        embedding_port=embedding_port,
        subject=str(atom.get("subject") or ""),
        predicate=str(atom.get("predicate") or ""),
        object_=str(atom.get("object") or ""),
    )
    conn.commit()
    conn.close()


def _upsert_record(
    conn: sqlite3.Connection,
    record_id: str,
    layer: str,
    file_path: str,
    record_type: str,
    session_id: str,
    body: str,
    *,
    embedding_port: EmbeddingPort | None = None,
    subject: str = "",
    predicate: str = "",
    object_: str = "",
) -> None:
    search_text = " ".join(
        part
        for part in (record_type, session_id, subject, predicate, object_, body)
        if part
    ).strip()
    mtime = 0.0
    if file_path:
        p = Path(file_path)
        if p.exists():
            mtime = p.stat().st_mtime
    embedding_blob, embedding_model = _embed_body(embedding_port, body)
    conn.execute("DELETE FROM memory_index WHERE record_id = ?", (record_id,))
    conn.execute("DELETE FROM memory_fts WHERE record_id = ?", (record_id,))
    conn.execute(
        """
        INSERT INTO memory_index (
            record_id, layer, file_path, record_type, session_id,
            search_text, body, file_mtime, embedding, embedding_model,
            subject, predicate, object
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            layer,
            file_path,
            record_type,
            session_id,
            search_text,
            body,
            mtime,
            embedding_blob,
            embedding_model,
            subject,
            predicate,
            object_,
        ),
    )
    conn.execute(
        "INSERT INTO memory_fts (record_id, layer, record_type, session_id, search_text, body) VALUES (?, ?, ?, ?, ?, ?)",
        (record_id, layer, record_type, session_id, search_text, body),
    )


def list_indexed_records(paths: BotMemoryPaths, limit: int = 500) -> list[dict]:
    """Load indexed L1/L2 records for hybrid semantic scoring.

    When ``limit <= 0``, return all rows (no SQL LIMIT) for full vector scan.
    """
    if not paths.index_db.exists():
        rebuild_index(paths)
    conn = _connect(paths.index_db)
    _init_schema(conn)
    if limit and limit > 0:
        rows = conn.execute(
            """
            SELECT record_id, layer, record_type, session_id, search_text, body,
                   embedding, embedding_model
            FROM memory_index
            ORDER BY file_mtime DESC, record_id ASC
            LIMIT ?
            """,
            (max(limit, 1),),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT record_id, layer, record_type, session_id, search_text, body,
                   embedding, embedding_model
            FROM memory_index
            ORDER BY file_mtime DESC, record_id ASC
            """
        ).fetchall()
    conn.close()
    out: list[dict] = []
    for row in rows:
        out.append(
            {
                "id": row["record_id"],
                "layer": row["layer"],
                "type": row["record_type"],
                "session_id": row["session_id"],
                "search_text": row["search_text"] or "",
                "body": row["body"] or "",
                "embedding_vector": blob_to_vector(row["embedding"]),
                "embedding_model": row["embedding_model"] or "",
            }
        )
    return out


def search_memory(paths: BotMemoryPaths, query: str, limit: int = 5) -> list[dict]:
    q = sanitize_fts_query(query)
    if not q:
        return []
    if not paths.index_db.exists():
        rebuild_index(paths)
    conn = _connect(paths.index_db)
    _init_schema(conn)
    try:
        rows = conn.execute(
            """
            SELECT record_id, layer, record_type, session_id,
                   snippet(memory_fts, 4, '[', ']', '…', 20) AS snippet, body
            FROM memory_fts
            WHERE memory_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (q, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()
    return [
        {
            "id": row["record_id"],
            "layer": row["layer"],
            "type": row["record_type"],
            "session_id": row["session_id"],
            "snippet": row["snippet"] or "",
            "body": row["body"] or "",
        }
        for row in rows
    ]
