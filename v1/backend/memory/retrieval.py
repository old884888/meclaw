import math
import os
import re
import sqlite3
from datetime import datetime

from .constants import RECENCY_HALF_LIFE_DAYS, RECENCY_WEIGHT, estimate_tokens
from .indexer import _connect, _init_schema, reindex_if_stale
from .intent import wants_doc_retrieval
from .store import ensure_layout, list_item_files, read_entry, read_item_file


def _escape_fts_query(query):
    """Build a simple OR-joined FTS query from user text."""
    text = re.sub(r'["\'\\:*]', " ", query or "")
    tokens = re.findall(r"[\w\u4e00-\u9fff]{2,}", text)
    if not tokens:
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", text)
    if not tokens:
        return None
    return " OR ".join(tokens[:12])


def _recency_score(created_at, item_type):
    half_life = RECENCY_HALF_LIFE_DAYS.get(item_type, 60)
    if half_life >= 9999:
        return 1.0
    try:
        dt = datetime.fromisoformat((created_at or "").replace("Z", ""))
        age_days = max(0, (datetime.now() - dt).total_seconds() / 86400)
    except (ValueError, TypeError):
        age_days = 30
    return math.pow(0.5, age_days / max(half_life, 1))


def _composite_score(bm25_rank, item_type, importance, created_at):
    bm25_part = max(0, -float(bm25_rank)) if bm25_rank is not None else 0
    bm25_norm = min(1.0, bm25_part / 10.0)
    recency = _recency_score(created_at, item_type)
    w_rec = RECENCY_WEIGHT.get(item_type, 0.2)
    imp = min(5, max(1, int(importance or 3))) / 5.0
    return bm25_norm * 0.65 + recency * w_rec + imp * 0.15


def search_memory(soul_folder, query, session_summary="", budget_tokens=1200, include_docs=None):
    """
    Search index.sqlite and return ranked memory hits.
    Returns list of dicts: type, summary, content, score, source.
    """
    if not soul_folder or not os.path.isdir(soul_folder):
        return []

    ensure_layout(soul_folder)
    reindex_if_stale(soul_folder)

    if include_docs is None:
        include_docs = wants_doc_retrieval(query)

    combined_query = query or ""
    if session_summary:
        combined_query += " " + session_summary[:200]

    fts_q = _escape_fts_query(combined_query)
    results = []
    conn = _connect(soul_folder)
    try:
        _init_schema(conn)

        # 1. Search entries (new format) — prioritize
        if fts_q:
            try:
                entry_rows = conn.execute(
                    """SELECT entry_id, entry_type, importance, created_at, summary, keywords,
                              bm25(memory_entries_fts) AS rank
                       FROM memory_entries_fts
                       WHERE memory_entries_fts MATCH ?
                       ORDER BY rank
                       LIMIT 8""",
                    (fts_q,),
                ).fetchall()
            except sqlite3.OperationalError:
                entry_rows = []
            for row in entry_rows:
                score = _composite_score(
                    row["rank"], row["entry_type"], row["importance"], row["created_at"]
                )
                score += 0.2  # entries get a boost over legacy items
                results.append({
                    "kind": "entry",
                    "type": row["entry_type"],
                    "id": row["entry_id"],
                    "summary": row["summary"] or "",
                    "content": row["summary"] or "",
                    "importance": row["importance"],
                    "score": score,
                    "file_path": None,  # will be resolved when picking
                })

        # 2. Search legacy items
        if fts_q:
            try:
                rows = conn.execute(
                    """SELECT item_id, item_type, importance, created_at, search_text, content,
                              bm25(memory_items_fts) AS rank
                       FROM memory_items_fts
                       WHERE memory_items_fts MATCH ?
                       ORDER BY rank
                       LIMIT 20""",
                    (fts_q,),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
            for row in rows:
                score = _composite_score(
                    row["rank"], row["item_type"], row["importance"], row["created_at"]
                )
                results.append({
                    "kind": "item",
                    "type": row["item_type"],
                    "id": row["item_id"],
                    "summary": (row["content"] or "")[:80],
                    "content": row["content"] or "",
                    "importance": row["importance"],
                    "score": score,
                })

        # 高 importance 兜底
        min_imp = 5 if len(results) >= 4 else 4
        high_cap = 2 if len(results) >= 4 else 5
        high_importance = conn.execute(
            """SELECT item_id, item_type, importance, created_at, content
               FROM memory_items_index WHERE importance >= ?
               ORDER BY importance DESC, created_at DESC LIMIT ?""",
            (min_imp, high_cap),
        ).fetchall()
        seen_ids = {r["id"] for r in results}
        for row in high_importance:
            if row["item_id"] in seen_ids:
                continue
            score = _composite_score(None, row["item_type"], row["importance"], row["created_at"])
            score += 0.1
            results.append({
                "kind": "item",
                "type": row["item_type"],
                "id": row["item_id"],
                "summary": (row["content"] or "")[:80],
                "content": row["content"] or "",
                "importance": row["importance"],
                "score": score,
            })

        if include_docs and fts_q:
            try:
                chunk_rows = conn.execute(
                    """SELECT chunk_id, doc_slug, title, content, bm25(memory_chunks_fts) AS rank
                       FROM memory_chunks_fts
                       WHERE memory_chunks_fts MATCH ?
                       ORDER BY rank
                       LIMIT 8""",
                    (fts_q,),
                ).fetchall()
            except sqlite3.OperationalError:
                chunk_rows = []
            for row in chunk_rows:
                score = _composite_score(row["rank"], "chunk", 3, "")
                results.append({
                    "kind": "chunk",
                    "type": "document",
                    "id": row["chunk_id"],
                    "summary": f"[{row['title']}] 片段",
                    "content": row["content"] or "",
                    "importance": 3,
                    "score": score,
                })
    finally:
        conn.close()

    results.sort(key=lambda x: x["score"], reverse=True)

    picked = []
    used_tokens = 0
    seen_keys = set()
    related_loaded = set()

    for hit in results:
        key = (hit["kind"], hit["id"])
        if key in seen_keys:
            continue
        snippet = hit["content"]
        if hit["kind"] == "chunk":
            snippet = f"[{hit['summary']}]\n{snippet}"
        elif hit["kind"] == "entry":
            # Load full entry content
            entry_data = _load_entry_full(soul_folder, hit["id"])
            if entry_data:
                snippet = _format_entry_content(entry_data)
                hit["summary"] = entry_data.get("title", hit["summary"])
            else:
                continue  # entry file deleted, skip
        tokens = estimate_tokens(snippet)
        if used_tokens + tokens > budget_tokens:
            if not picked:
                picked.append({**hit, "content": snippet[: budget_tokens * 2]})
            break
        picked.append({**hit, "content": snippet})
        used_tokens += tokens
        seen_keys.add(key)

        # Load related entries for entry hits
        if hit["kind"] == "entry" and entry_data:
            related = entry_data.get("related", [])
            for rel_slug in related:
                if rel_slug in related_loaded:
                    continue
                related_loaded.add(rel_slug)
                rel_data = _load_entry_by_slug(soul_folder, rel_slug)
                if not rel_data:
                    continue
                rel_snippet = _format_entry_content(rel_data)
                rel_tokens = estimate_tokens(rel_snippet)
                if used_tokens + rel_tokens > budget_tokens:
                    break
                picked.append({
                    "kind": "entry",
                    "type": rel_data.get("type", "fact"),
                    "id": rel_slug,
                    "summary": rel_data.get("title", rel_slug),
                    "content": rel_snippet,
                    "importance": rel_data.get("importance", 3),
                    "score": 0.1,  # low score — supplementary
                })
                used_tokens += rel_tokens

        if len(picked) >= 5:
            break

    return picked


def _load_entry_full(soul_folder, entry_id):
    """Load full entry data by entry_id (filename without .md)."""
    from .store import entries_dir
    base = entries_dir(soul_folder)
    path = os.path.join(base, f"{entry_id}.md")
    if not os.path.isfile(path):
        # Try partial match
        if os.path.isdir(base):
            for name in os.listdir(base):
                if name.endswith(".md") and entry_id in name:
                    path = os.path.join(base, name)
                    break
    return read_entry(path) if os.path.isfile(path) else None


def _load_entry_by_slug(soul_folder, slug):
    """Load entry by slug (filename without .md)."""
    from .store import entries_dir
    base = entries_dir(soul_folder)
    path = os.path.join(base, f"{slug}.md")
    if not os.path.isfile(path):
        return None
    return read_entry(path)


def _format_entry_content(entry_data):
    """Format entry data into readable content for injection."""
    parts = []
    title = entry_data.get("title", "")
    summary = entry_data.get("summary", "")
    points = entry_data.get("points", [])
    keywords = entry_data.get("keywords", "")
    if title:
        parts.append(f"[{title}]")
    if summary:
        parts.append(summary)
    if points:
        parts.append("要点：" + "、".join(points[:5]))
    return "\n".join(parts)


def format_memory_block(hits):
    if not hits:
        return ""
    lines = [
        "## 相关记忆",
        "与当前问题相关的记忆片段（非完整记忆库）：",
        "",
    ]
    for i, hit in enumerate(hits, 1):
        label = hit.get("type", "memory")
        kind = hit.get("kind", "item")
        if kind == "chunk":
            lines.append(f"{i}. [{label}] {hit.get('summary', '')}")
        elif kind == "entry":
            lines.append(f"{i}. [{hit.get('summary', '')}] {hit.get('content', '')}")
        else:
            lines.append(f"{i}. [{label}] {hit.get('content', '')}")
        lines.append("")
    return "\n".join(lines).strip()
