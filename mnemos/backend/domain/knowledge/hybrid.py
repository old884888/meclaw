"""Hybrid retrieval: FTS + lightweight semantic ranking (RRF)."""

from __future__ import annotations

import math
import re
from typing import Any

from .indexer import search_notes
from .paths import KnowledgePaths
from .store import list_notes

TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
RRF_K = 60.0
EMBED_DIM = 256


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text or "")]


def _text_to_vector(text: str, dim: int = EMBED_DIM) -> list[float]:
    vec = [0.0] * dim
    for tok in _tokenize(text):
        h = hash(tok)
        idx = h % dim
        sign = -1.0 if (h & 1) else 1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def _semantic_hits(paths: KnowledgePaths, query: str, limit: int = 8) -> list[dict[str, Any]]:
    qv = _text_to_vector(query)
    scored: list[dict[str, Any]] = []
    for note in list_notes(paths):
        text = " ".join(
            [
                note.get("title") or "",
                note.get("category") or "",
                " ".join(note.get("tags") or []),
                note.get("body") or "",
            ]
        )
        sv = _text_to_vector(text)
        score = _cosine(qv, sv)
        scored.append(
            {
                "id": note.get("id"),
                "title": note.get("title"),
                "category": note.get("category"),
                "tags": note.get("tags") or [],
                "source_id": note.get("source_id") or "",
                "source_url": note.get("source_url") or "",
                "created_at": note.get("created_at") or "",
                "snippet": (note.get("body") or "")[:180],
                "semantic_score": score,
            }
        )
    scored.sort(key=lambda x: x.get("semantic_score", 0.0), reverse=True)
    return scored[: max(limit, 1)]


def search_notes_hybrid(paths: KnowledgePaths, query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Fuse lexical and semantic results using Reciprocal Rank Fusion."""
    q = (query or "").strip()
    if not q:
        return []

    lexical = search_notes(paths, q, limit=max(limit * 3, 20))
    semantic = _semantic_hits(paths, q, limit=max(limit * 3, 20))

    by_id: dict[str, dict[str, Any]] = {}
    score: dict[str, float] = {}

    for i, item in enumerate(lexical, start=1):
        nid = item.get("id")
        if not nid:
            continue
        by_id.setdefault(nid, dict(item))
        score[nid] = score.get(nid, 0.0) + 1.0 / (RRF_K + i)

    for i, item in enumerate(semantic, start=1):
        nid = item.get("id")
        if not nid:
            continue
        if nid not in by_id:
            by_id[nid] = dict(item)
        else:
            if not by_id[nid].get("snippet"):
                by_id[nid]["snippet"] = item.get("snippet") or ""
        score[nid] = score.get(nid, 0.0) + 1.0 / (RRF_K + i)

    merged = [
        {
            **by_id[nid],
            "hybrid_score": score.get(nid, 0.0),
        }
        for nid in by_id
    ]
    merged.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
    return merged[:limit]
