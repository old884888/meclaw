"""Importance, recency, and composite recall scoring for L1 atoms."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

_TYPE_IMPORTANCE = {
    "constraint": 1.0,
    "preference": 0.85,
    "fact": 0.7,
    "todo": 0.6,
}


def _cfg_float(cfg: dict[str, Any], key: str, default: float) -> float:
    raw = cfg.get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def default_importance(atom_type: str) -> float:
    return float(_TYPE_IMPORTANCE.get(str(atom_type or "").strip().lower(), 0.65))


def atom_importance(atom: dict[str, Any]) -> float:
    meta = atom.get("meta") or {}
    raw = atom.get("importance", meta.get("importance"))
    try:
        val = float(raw)
        if val > 0:
            return max(0.0, min(1.0, val))
    except (TypeError, ValueError):
        pass
    atom_type = str(atom.get("type") or meta.get("type") or "fact")
    return default_importance(atom_type)


def atom_hit_count(atom: dict[str, Any]) -> int:
    meta = atom.get("meta") or {}
    raw = atom.get("hit_count", meta.get("hit_count", 0))
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def is_superseded(atom: dict[str, Any]) -> bool:
    meta = atom.get("meta") or {}
    by = str(atom.get("superseded_by") or meta.get("superseded_by") or "").strip()
    return bool(by)


def _parse_iso(ts: str) -> datetime | None:
    text = (ts or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def recency_factor(
    atom: dict[str, Any],
    *,
    half_life_days: float = 90.0,
    now: datetime | None = None,
) -> float:
    meta = atom.get("meta") or {}
    atom_type = str(atom.get("type") or meta.get("type") or "fact").lower()
    if atom_type == "constraint":
        return 1.0
    created = str(atom.get("created_at") or meta.get("created_at") or "")
    dt = _parse_iso(created)
    if dt is None:
        return 0.75
    now = now or datetime.now(timezone.utc)
    age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
    half = max(1.0, float(half_life_days or 90.0))
    return 0.5 ** (age_days / half)


def normalize_relevance(score: float, *, floor: float = 0.0, ceiling: float = 1.0) -> float:
    if ceiling <= floor:
        return 0.0
    return max(0.0, min(1.0, (float(score) - floor) / (ceiling - floor)))


def composite_recall_score(
    atom: dict[str, Any],
    relevance: float,
    cfg: dict[str, Any] | None = None,
) -> float:
    """Combine hybrid/rerank relevance with importance, recency, and hit boost."""
    cfg = cfg or {}
    w_rel = _cfg_float(cfg, "memory_score_relevance_weight", 1.0)
    w_imp = _cfg_float(cfg, "memory_score_importance_weight", 0.15)
    w_rec = _cfg_float(cfg, "memory_score_recency_weight", 0.1)
    w_hit = _cfg_float(cfg, "memory_score_hit_weight", 0.08)
    half_life = _cfg_float(cfg, "memory_recency_half_life_days", 90.0)

    rel = float(relevance)
    if rel < 0.0 or rel > 1.0:
        floor = _cfg_float(cfg, "memory_score_rel_floor", 0.0)
        ceiling = max(floor + 0.001, _cfg_float(cfg, "memory_score_rel_ceiling", 0.05))
        rel = normalize_relevance(rel, floor=floor, ceiling=ceiling)
    imp = atom_importance(atom)
    rec = recency_factor(atom, half_life_days=half_life)
    hit = math.log1p(atom_hit_count(atom)) / math.log1p(10)
    return w_rel * rel + w_imp * imp + w_rec * rec + w_hit * hit


def rerank_hits_by_quality(
    hits: list[dict[str, Any]],
    atoms_by_id: dict[str, dict[str, Any]],
    cfg: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not hits:
        return hits
    scored: list[tuple[float, dict[str, Any]]] = []
    rel_key = "rerank_score"
    rels = [float(h.get(rel_key) or h.get("hybrid_score") or 0.0) for h in hits]
    rel_max = max(rels) if rels else 1.0
    rel_min = min(rels) if rels else 0.0
    cfg = dict(cfg or {})
    cfg["memory_score_rel_floor"] = rel_min
    cfg["memory_score_rel_ceiling"] = rel_max if rel_max > rel_min else rel_max + 0.001
    for hit in hits:
        atom = atoms_by_id.get(str(hit.get("id") or ""))
        if not atom:
            scored.append((float(hit.get(rel_key) or hit.get("hybrid_score") or 0.0), hit))
            continue
        rel = float(hit.get(rel_key) or hit.get("hybrid_score") or 0.0)
        total = composite_recall_score(atom, rel, cfg)
        item = dict(hit)
        item["quality_score"] = round(total, 6)
        scored.append((total, item))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("id") or "")))
    return [item for _score, item in scored]
