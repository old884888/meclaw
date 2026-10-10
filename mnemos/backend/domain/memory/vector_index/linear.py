"""Linear vector scan over all cached embeddings (no scan cap)."""

from __future__ import annotations

from typing import Any

from ..embedding.port import EmbeddingPort
from ..indexer import list_indexed_records
from ..paths import BotMemoryPaths


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


class LinearVectorIndex:
    """Full-table cosine scan using P1 cached vectors (ANN fallback)."""

    @property
    def available(self) -> bool:
        return True

    def query(
        self,
        paths: BotMemoryPaths,
        query: str,
        *,
        limit: int,
        embedding_port: EmbeddingPort,
    ) -> list[dict[str, Any]]:
        if not embedding_port.available:
            return []
        identity = embedding_port.model_identity
        try:
            q_vecs = embedding_port.embed([query])
            qv = q_vecs[0] if q_vecs and q_vecs[0] else None
        except Exception:  # noqa: BLE001
            return []
        if not qv:
            return []

        scored: list[dict[str, Any]] = []
        for record in list_indexed_records(paths, limit=0):
            body = (record.get("body") or "").strip()
            cached = record.get("embedding_vector")
            cached_id = str(record.get("embedding_model") or "")
            sv: list[float] | None = None
            if cached and cached_id == identity:
                sv = cached
            elif body:
                try:
                    vecs = embedding_port.embed([body])
                    sv = vecs[0] if vecs and vecs[0] else None
                except Exception:  # noqa: BLE001
                    sv = None
            if not sv:
                continue
            score = _cosine(qv, sv)
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
