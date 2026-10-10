"""Near-duplicate detection when writing L1 atoms."""

from __future__ import annotations

import math
from typing import Any

from .store_l1 import list_atoms
from .topic_metadata import enrich_atom


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def find_near_duplicate_atom(
    paths,
    *,
    content: str,
    topic_key: str,
    embedding_port=None,
    threshold: float = 0.92,
    scan_limit: int = 30,
) -> dict[str, Any] | None:
    """Return an existing atom if body embedding is near-identical under same topic."""
    threshold = float(threshold or 0.0)
    if threshold <= 0:
        return None
    text = (content or "").strip()
    topic = (topic_key or "").strip()
    if not text or not topic or embedding_port is None or not getattr(embedding_port, "available", False):
        return None
    try:
        new_vec = embedding_port.embed([text])[0]
    except Exception:  # noqa: BLE001
        return None
    if not new_vec:
        return None
    for atom in list_atoms(paths)[:scan_limit]:
        enriched = enrich_atom(dict(atom))
        if str(enriched.get("topic_key") or "") != topic:
            continue
        body = str(enriched.get("content") or "").strip()
        if not body:
            continue
        try:
            vec = embedding_port.embed([body])[0]
        except Exception:  # noqa: BLE001
            continue
        if _cosine(new_vec, vec) >= threshold:
            return enriched
    return None
