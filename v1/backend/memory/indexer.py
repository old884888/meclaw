import json
import os
import re
import sqlite3

from .constants import ITEM_TYPES
from .store import (
    docs_dir,
    ensure_layout,
    entries_dir,
    index_path,
    list_item_files,
    memory_root,
    read_entry,
    read_item_file,
)


def _connect(soul_folder):
    ensure_layout(soul_folder)
    path = index_path(soul_folder)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sync_state (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS memory_items_index (
            item_id TEXT PRIMARY KEY,
            item_type TEXT NOT NULL,
            file_path TEXT NOT NULL UNIQUE,
            importance INTEGER DEFAULT 3,
            created_at TEXT,
            file_mtime REAL DEFAULT 0,
            search_text TEXT,
            content TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_items_fts USING fts5(
            item_id UNINDEXED,
            item_type UNINDEXED,
            importance UNINDEXED,
            created_at UNINDEXED,
            search_text,
            content UNINDEXED,
            tokenize='unicode61'
        );

        CREATE TABLE IF NOT EXISTS memory_chunks_index (
            chunk_id TEXT PRIMARY KEY,
            doc_slug TEXT NOT NULL,
            chunk_index INTEGER,
            file_path TEXT NOT NULL UNIQUE,
            title TEXT,
            file_mtime REAL DEFAULT 0,
            search_text TEXT,
            content TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_chunks_fts USING fts5(
            chunk_id UNINDEXED,
            doc_slug UNINDEXED,
            title UNINDEXED,
            search_text,
            content UNINDEXED,
            tokenize='unicode61'
        );

        CREATE TABLE IF NOT EXISTS memory_entries_index (
            entry_id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL UNIQUE,
            entry_type TEXT,
            importance INTEGER DEFAULT 3,
            created_at TEXT,
            file_mtime REAL DEFAULT 0,
            search_text TEXT,
            summary TEXT,
            keywords TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_entries_fts USING fts5(
            entry_id UNINDEXED,
            entry_type UNINDEXED,
            importance UNINDEXED,
            created_at UNINDEXED,
            search_text,
            tokenize='unicode61'
        );
    """)
    conn.commit()


def build_search_text(content, summary="", keywords=None):
    parts = []
    if summary:
        parts.append(summary)
    if keywords:
        if isinstance(keywords, list):
            parts.extend(str(k) for k in keywords)
        else:
            parts.append(str(keywords))
    if content:
        parts.append(content[:500])
    text = " ".join(parts)
    ngrams = _chinese_ngrams(text)
    if ngrams:
        parts.append(ngrams)
    return " ".join(parts)


def _chinese_ngrams(text, sizes=(2, 3)):
    chars = re.sub(r"\s+", "", text or "")
    tokens = []
    for n in sizes:
        if len(chars) < n:
            continue
        for i in range(len(chars) - n + 1):
            tokens.append(chars[i:i + n])
    return " ".join(tokens[:400])


def _file_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def index_item_file(conn, file_path, data=None):
    data = data or read_item_file(file_path)
    if not data:
        return
    item_id = data.get("id", os.path.basename(file_path).replace(".json", ""))
    item_type = data.get("type", "fact")
    content = data.get("content", "")
    search_text = build_search_text(
        content,
        data.get("summary", ""),
        data.get("keywords"),
    )
    mtime = _file_mtime(file_path)
    conn.execute("DELETE FROM memory_items_fts WHERE item_id = ?", (item_id,))
    conn.execute(
        """INSERT OR REPLACE INTO memory_items_index
           (item_id, item_type, file_path, importance, created_at, file_mtime, search_text, content)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            item_id,
            item_type,
            file_path,
            int(data.get("importance", 3)),
            data.get("created_at", ""),
            mtime,
            search_text,
            content,
        ),
    )
    conn.execute(
        """INSERT INTO memory_items_fts (item_id, item_type, importance, created_at, search_text, content)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            item_id,
            item_type,
            int(data.get("importance", 3)),
            data.get("created_at", ""),
            search_text,
            content,
        ),
    )


def index_doc_folder(conn, soul_folder, doc_slug):
    base = os.path.join(docs_dir(soul_folder), doc_slug)
    if not os.path.isdir(base):
        return
    meta_path = os.path.join(base, "meta.json")
    title = doc_slug
    tags = []
    summary = ""
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            title = meta.get("title", doc_slug)
            tags = meta.get("tags", [])
            summary = meta.get("summary", "")
        except (OSError, json.JSONDecodeError):
            pass

    for name in sorted(os.listdir(base)):
        if not name.startswith("chunk-") or not name.endswith(".md"):
            continue
        path = os.path.join(base, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue
        chunk_index = int(re.search(r"chunk-(\d+)", name).group(1)) if re.search(r"chunk-(\d+)", name) else 0
        chunk_id = f"{doc_slug}:{name}"
        search_text = build_search_text(content, summary, tags + [title])
        mtime = _file_mtime(path)
        conn.execute("DELETE FROM memory_chunks_fts WHERE chunk_id = ?", (chunk_id,))
        conn.execute(
            """INSERT OR REPLACE INTO memory_chunks_index
               (chunk_id, doc_slug, chunk_index, file_path, title, file_mtime, search_text, content)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (chunk_id, doc_slug, chunk_index, path, title, mtime, search_text, content),
        )
        conn.execute(
            """INSERT INTO memory_chunks_fts (chunk_id, doc_slug, title, search_text, content)
               VALUES (?, ?, ?, ?, ?)""",
            (chunk_id, doc_slug, title, search_text, content),
        )


def index_entry_file(conn, file_path, data=None):
    """Index a single entry file into memory_entries_index and memory_entries_fts."""
    data = data or read_entry(file_path)
    if not data:
        return
    entry_id = data.get("id", os.path.basename(file_path).replace(".md", ""))
    entry_type = data.get("type", "fact")
    summary = data.get("summary", "")
    keywords = data.get("keywords", "")
    points = data.get("points", [])
    # build search_text: keywords + summary + points + n-grams
    parts = []
    if keywords:
        parts.append(keywords)
    if summary:
        parts.append(summary)
    if points:
        parts.extend(points)
    content_text = " ".join(parts)
    search_text = build_search_text(content_text, summary, keywords.split(",") if isinstance(keywords, str) else keywords)
    mtime = _file_mtime(file_path)
    conn.execute("DELETE FROM memory_entries_fts WHERE entry_id = ?", (entry_id,))
    conn.execute(
        """INSERT OR REPLACE INTO memory_entries_index
           (entry_id, file_path, entry_type, importance, created_at, file_mtime, search_text, summary, keywords)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            entry_id,
            file_path,
            entry_type,
            int(data.get("importance", 3)),
            data.get("created_at", ""),
            mtime,
            search_text,
            summary,
            keywords if isinstance(keywords, str) else ", ".join(keywords),
        ),
    )
    conn.execute(
        """INSERT INTO memory_entries_fts (entry_id, entry_type, importance, created_at, search_text)
           VALUES (?, ?, ?, ?, ?)""",
        (
            entry_id,
            entry_type,
            int(data.get("importance", 3)),
            data.get("created_at", ""),
            search_text,
        ),
    )


def reindex_all(soul_folder):
    """Full reindex from filesystem."""
    if not soul_folder or not os.path.isdir(soul_folder):
        return
    ensure_layout(soul_folder)
    conn = _connect(soul_folder)
    try:
        _init_schema(conn)
        conn.execute("DELETE FROM memory_items_index")
        conn.execute("DELETE FROM memory_items_fts")
        conn.execute("DELETE FROM memory_chunks_index")
        conn.execute("DELETE FROM memory_chunks_fts")
        conn.execute("DELETE FROM memory_entries_index")
        conn.execute("DELETE FROM memory_entries_fts")

        for path in list_item_files(soul_folder):
            index_item_file(conn, path)

        droot = docs_dir(soul_folder)
        if os.path.isdir(droot):
            for slug in os.listdir(droot):
                if os.path.isdir(os.path.join(droot, slug)):
                    index_doc_folder(conn, soul_folder, slug)

        eroot = entries_dir(soul_folder)
        if os.path.isdir(eroot):
            for name in os.listdir(eroot):
                if name.endswith(".md"):
                    index_entry_file(conn, os.path.join(eroot, name))

        conn.execute(
            "INSERT OR REPLACE INTO sync_state (key, value) VALUES (?, ?)",
            ("last_full_reindex", str(_file_mtime(memory_root(soul_folder)))),
        )
        conn.commit()
    finally:
        conn.close()


def reindex_if_stale(soul_folder):
    """Incremental reindex when item files changed."""
    if not soul_folder or not os.path.isdir(soul_folder):
        return
    if not os.path.isdir(memory_root(soul_folder)):
        ensure_layout(soul_folder)
        reindex_all(soul_folder)
        return

    conn = _connect(soul_folder)
    try:
        _init_schema(conn)
        indexed_paths = {
            row["file_path"]: row["file_mtime"]
            for row in conn.execute("SELECT file_path, file_mtime FROM memory_items_index")
        }
        seen = set()
        for path in list_item_files(soul_folder):
            seen.add(path)
            mtime = _file_mtime(path)
            if path not in indexed_paths or abs(indexed_paths[path] - mtime) > 0.5:
                index_item_file(conn, path)

        for path, _ in list(indexed_paths.items()):
            if path not in seen and not os.path.isfile(path):
                row = conn.execute(
                    "SELECT item_id FROM memory_items_index WHERE file_path = ?", (path,)
                ).fetchone()
                if row:
                    conn.execute("DELETE FROM memory_items_fts WHERE item_id = ?", (row["item_id"],))
                    conn.execute("DELETE FROM memory_items_index WHERE file_path = ?", (path,))

        droot = docs_dir(soul_folder)
        if os.path.isdir(droot):
            for slug in os.listdir(droot):
                doc_path = os.path.join(droot, slug)
                if os.path.isdir(doc_path):
                    index_doc_folder(conn, soul_folder, slug)

        # entries incremental reindex
        entry_indexed_paths = {
            row["file_path"]: row["file_mtime"]
            for row in conn.execute("SELECT file_path, file_mtime FROM memory_entries_index")
        }
        entry_seen = set()
        eroot = entries_dir(soul_folder)
        if os.path.isdir(eroot):
            for name in os.listdir(eroot):
                if not name.endswith(".md"):
                    continue
                path = os.path.join(eroot, name)
                entry_seen.add(path)
                mtime = _file_mtime(path)
                if path not in entry_indexed_paths or abs(entry_indexed_paths[path] - mtime) > 0.5:
                    index_entry_file(conn, path)

        for path, _ in list(entry_indexed_paths.items()):
            if path not in entry_seen and not os.path.isfile(path):
                row = conn.execute(
                    "SELECT entry_id FROM memory_entries_index WHERE file_path = ?", (path,)
                ).fetchone()
                if row:
                    conn.execute("DELETE FROM memory_entries_fts WHERE entry_id = ?", (row["entry_id"],))
                    conn.execute("DELETE FROM memory_entries_index WHERE file_path = ?", (path,))

        conn.commit()
    finally:
        conn.close()


def index_after_write(soul_folder, item_path):
    conn = _connect(soul_folder)
    try:
        _init_schema(conn)
        index_item_file(conn, item_path)
        conn.commit()
    finally:
        conn.close()


def index_after_entry_write(soul_folder, entry_path):
    """Index a single entry file after write."""
    conn = _connect(soul_folder)
    try:
        _init_schema(conn)
        index_entry_file(conn, entry_path)
        conn.commit()
    finally:
        conn.close()


def index_after_document(soul_folder, doc_slug):
    conn = _connect(soul_folder)
    try:
        _init_schema(conn)
        index_doc_folder(conn, soul_folder, doc_slug)
        conn.commit()
    finally:
        conn.close()


def remove_item_from_index(soul_folder, item_id):
    conn = _connect(soul_folder)
    try:
        _init_schema(conn)
        conn.execute("DELETE FROM memory_items_fts WHERE item_id = ?", (item_id,))
        conn.execute("DELETE FROM memory_items_index WHERE item_id = ?", (item_id,))
        conn.commit()
    finally:
        conn.close()


def remove_entry_from_index(soul_folder, entry_id):
    conn = _connect(soul_folder)
    try:
        _init_schema(conn)
        conn.execute("DELETE FROM memory_entries_fts WHERE entry_id = ?", (entry_id,))
        conn.execute("DELETE FROM memory_entries_index WHERE entry_id = ?", (entry_id,))
        conn.commit()
    finally:
        conn.close()
