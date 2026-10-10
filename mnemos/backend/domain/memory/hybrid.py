"""Hybrid memory retrieval: FTS + vector recall + optional rerank."""

from __future__ import annotations

import hashlib
import math
import re
from typing import TYPE_CHECKING, Any

from .indexer import list_indexed_records, sanitize_fts_query, search_memory
from .paths import BotMemoryPaths

if TYPE_CHECKING:
    from .embedding.port import EmbeddingPort
    from .rerank.port import Reranker
    from .vector_index.port import VectorIndex

TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
RRF_K = 60.0
EMBED_DIM = 256
# Hash fallback only — real embeddings use VectorIndex (no cap).
SEMANTIC_SCAN_LIMIT = 2000

INTENT_EXPANSIONS: list[tuple[re.Pattern[str], tuple[str, ...]]] = [
    (re.compile(r"喜欢|偏好|最爱|倾向|prefer|favorite|favourite|choice|style", re.I), ("preference", "偏好", "喜欢", "风格")),
    (re.compile(r"过敏|allerg|忌口|不能吃|avoid|intoler", re.I), ("allergy", "constraint", "过敏", "忌口", "约束")),
    (re.compile(r"约束|限制|必须|不能|should not|must not|never", re.I), ("constraint", "约束", "限制", "规则")),
    (re.compile(r"待办|todo|task|remind|记得|别忘了", re.I), ("todo", "待办", "任务", "提醒")),
    (re.compile(r"推荐|建议|哪个好|选什么|recommend|suggest|pick", re.I), ("recommendation", "推荐", "建议", "偏好")),
    (re.compile(r"旅行|旅游|trip|travel|vacation|hotel|航班", re.I), ("travel", "旅行", "旅游", "行程")),
    (re.compile(r"吃|餐|菜|饭|food|meal|restaurant|diet|饮食", re.I), ("food", "饮食", "餐", "菜", "偏好")),
    (re.compile(r"写|文案|邮件|tone|writing|draft|compose", re.I), ("writing", "写作", "风格", "语气")),
]


def expand_memory_query(query: str) -> str:
    base = (query or "").strip()
    if not base:
        return base
    extras: list[str] = []
    seen: set[str] = {base.lower()}
    for pattern, terms in INTENT_EXPANSIONS:
        if not pattern.search(base):
            continue
        for term in terms:
            key = term.lower()
            if key not in seen:
                seen.add(key)
                extras.append(term)
    if not extras:
        return base
    return f"{base} {' '.join(extras)}"


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text or "")]


def _stable_hash(token: str) -> int:
    digest = hashlib.sha1(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _text_to_vector(text: str, dim: int = EMBED_DIM) -> list[float]:
    vec = [0.0] * dim
    for tok in _tokenize(text):
        h = _stable_hash(tok)
        idx = h % dim
        sign = -1.0 if (h & 1) else 1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def _semantic_hits_hash(paths: BotMemoryPaths, query: str, limit: int) -> list[dict[str, Any]]:
    qv = _text_to_vector(query)
    scored: list[dict[str, Any]] = []
    for record in list_indexed_records(paths, limit=SEMANTIC_SCAN_LIMIT):
        body = (record.get("body") or "").strip()
        text = body or record.get("search_text") or ""
        score = _cosine(qv, _text_to_vector(text))
        snippet_src = body or record.get("search_text") or ""
        scored.append(
            {
                "id": record.get("id"),
                "layer": record.get("layer"),
                "type": record.get("type"),
                "session_id": record.get("session_id"),
                "snippet": snippet_src[:180],
                "body": body,
                "semantic_score": score,
            }
        )
    scored.sort(key=lambda x: (-x.get("semantic_score", 0.0), str(x.get("id") or "")))
    return scored[: max(limit, 1)]


def _semantic_hits(
    paths: BotMemoryPaths,
    query: str,
    limit: int = 8,
    *,
    embedding_port: EmbeddingPort | None = None,
    vector_index: VectorIndex | None = None,
) -> list[dict[str, Any]]:
    if (
        embedding_port is not None
        and embedding_port.available
        and vector_index is not None
        and vector_index.available
    ):
        try:
            hits = vector_index.query(
                paths,
                query,
                limit=limit,
                embedding_port=embedding_port,
            )
            if hits:
                return hits
        except Exception:  # noqa: BLE001
            pass

    if embedding_port is not None and embedding_port.available:
        return _semantic_hits_cached_linear(paths, query, limit, embedding_port=embedding_port)

    return _semantic_hits_hash(paths, query, limit)


def _semantic_hits_cached_linear(
    paths: BotMemoryPaths,
    query: str,
    limit: int,
    *,
    embedding_port: EmbeddingPort,
) -> list[dict[str, Any]]:
    """P1-style cached-vector scan without SEMANTIC_SCAN_LIMIT."""
    from .vector_index.linear import LinearVectorIndex

    try:
        return LinearVectorIndex().query(
            paths,
            query,
            limit=limit,
            embedding_port=embedding_port,
        )
    except Exception:  # noqa: BLE001
        return _semantic_hits_hash(paths, query, limit)


def _merge_rrf(*ranked_lists: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    score: dict[str, float] = {}

    for items in ranked_lists:
        for i, item in enumerate(items, start=1):
            rid = item.get("id")
            if not rid:
                continue
            by_id.setdefault(rid, dict(item))
            existing = by_id[rid]
            if not existing.get("snippet") and item.get("snippet"):
                existing["snippet"] = item["snippet"]
            if not existing.get("body") and item.get("body"):
                existing["body"] = item["body"]
            if item.get("semantic_score") is not None:
                existing["semantic_score"] = item.get("semantic_score")
            score[rid] = score.get(rid, 0.0) + 1.0 / (RRF_K + i)

    merged = [{**by_id[rid], "hybrid_score": score.get(rid, 0.0)} for rid in by_id]
    merged.sort(key=lambda x: (-x.get("hybrid_score", 0.0), str(x.get("id") or "")))
    return merged[:limit]


def search_memory_hybrid(
    paths: BotMemoryPaths,
    query: str,
    limit: int = 5,
    *,
    min_score: float = 0.0,
    embedding_port: EmbeddingPort | None = None,
    vector_index: VectorIndex | None = None,
    reranker: Reranker | None = None,
    rerank_enabled: bool = False,
    rerank_candidate_pool: int = 20,
    rerank_top_k: int = 5,
    cfg: dict | None = None,
) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []

    expanded = expand_memory_query(q)
    fetch = max(limit * 3, 20)
    pool_limit = max(rerank_candidate_pool, limit) if rerank_enabled else fetch

    lexical_lists: list[list[dict]] = []
    safe_original = sanitize_fts_query(q)
    if safe_original:
        lexical_lists.append(search_memory(paths, safe_original, limit=pool_limit))
    safe_expanded = sanitize_fts_query(expanded)
    if safe_expanded and safe_expanded != safe_original:
        lexical_lists.append(search_memory(paths, safe_expanded, limit=pool_limit))
    if not lexical_lists:
        lexical_lists.append([])

    semantic_query = expanded if expanded != q else q
    semantic = _semantic_hits(
        paths,
        semantic_query,
        limit=pool_limit,
        embedding_port=embedding_port,
        vector_index=vector_index,
    )

    merged = _merge_rrf(*lexical_lists, semantic, limit=pool_limit)
    if min_score > 0.0:
        merged = [m for m in merged if m.get("hybrid_score", 0.0) >= min_score]

    use_rerank = rerank_enabled and reranker is not None and reranker.available
    if use_rerank:
        final_k = max(1, min(rerank_top_k, limit))
        try:
            results = reranker.rerank(q, merged, top_k=final_k)
        except Exception:  # noqa: BLE001
            results = merged[:limit]
    else:
        results = merged[:limit]

    return _apply_quality_ranking(paths, results, limit=limit, cfg=cfg)


def _apply_quality_ranking(
    paths: BotMemoryPaths,
    hits: list[dict[str, Any]],
    *,
    limit: int,
    cfg: dict | None,
) -> list[dict]:
    if not hits:
        return hits
    from .memory_scoring import is_superseded, rerank_hits_by_quality
    from .store_l1 import get_atom_by_id

    cfg = cfg or {}
    atoms_by_id: dict[str, dict[str, Any]] = {}
    filtered: list[dict[str, Any]] = []
    for hit in hits:
        atom_id = str(hit.get("id") or "")
        atom = get_atom_by_id(paths, atom_id) if atom_id else None
        if atom:
            atoms_by_id[atom_id] = atom
            if is_superseded(atom):
                continue
        filtered.append(hit)

    use_quality = any(
        float(cfg.get(key) or 0) > 0
        for key in (
            "memory_score_importance_weight",
            "memory_score_recency_weight",
            "memory_score_hit_weight",
        )
    )
    if use_quality and atoms_by_id:
        filtered = rerank_hits_by_quality(filtered, atoms_by_id, cfg)
    return filtered[: max(limit, 1)]
