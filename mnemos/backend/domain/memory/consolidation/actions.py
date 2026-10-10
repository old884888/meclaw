"""Consolidation actions: merge, compress, archive."""

from __future__ import annotations

from typing import Any

from ..memory_scoring import atom_hit_count, atom_importance, recency_factor
from ..store_l1 import list_atoms, mark_atom_archived, update_atom_meta, write_atom
from ..topic_metadata import enrich_atom, format_evolution_timeline, group_atoms_by_topic_key
from ..topic_registry import cosine_similarity
from .audit import log_consolidation_event
from .pins import is_pinned


def _active_atoms(paths, *, include_archived: bool = False) -> list[dict[str, Any]]:
    return list_atoms(paths, include_archived=include_archived)


def archive_low_value_atoms(
    paths,
    *,
    cfg: dict[str, Any],
    half_life_days: float,
) -> int:
    archived = 0
    for atom in _active_atoms(paths):
        enriched = enrich_atom(dict(atom))
        if is_pinned(enriched):
            continue
        if atom_hit_count(enriched) > 0:
            continue
        if atom_importance(enriched) >= 0.55:
            continue
        if recency_factor(enriched, half_life_days=half_life_days) >= 0.5:
            continue
        atom_id = str(enriched.get("id") or "")
        if not atom_id:
            continue
        mark_atom_archived(paths, atom_id, reason="low_value")
        log_consolidation_event(
            paths,
            {"action": "archive", "atom_id": atom_id, "reason": "low_value"},
        )
        archived += 1
    return archived


def merge_similar_atoms(
    paths,
    *,
    embedding_port,
    cfg: dict[str, Any],
) -> int:
    if embedding_port is None or not getattr(embedding_port, "available", False):
        return 0
    threshold = float(cfg.get("memory_consolidation_merge_threshold") or 0.93)
    threshold = max(0.85, min(0.99, threshold))
    merged = 0
    atoms = _active_atoms(paths)
    groups = group_atoms_by_topic_key(atoms)
    for _topic, items in groups.items():
        if len(items) < 2:
            continue
        ordered = sorted(items, key=lambda a: int(a.get("seq") or 0))
        for i in range(len(ordered) - 1):
            left = ordered[i]
            right = ordered[i + 1]
            if is_pinned(left) or is_pinned(right):
                continue
            left_body = str(left.get("content") or "").strip()
            right_body = str(right.get("content") or "").strip()
            if not left_body or not right_body:
                continue
            try:
                vecs = embedding_port.embed([left_body, right_body])
            except Exception:  # noqa: BLE001
                continue
            if len(vecs) != 2 or not vecs[0] or not vecs[1]:
                continue
            if cosine_similarity(vecs[0], vecs[1]) < threshold:
                continue
            keep = right
            drop = left
            keep_id = str(keep.get("id") or "")
            drop_id = str(drop.get("id") or "")
            if not keep_id or not drop_id:
                continue
            note = str(keep.get("reason") or "").strip()
            drop_body = str(drop.get("content") or "").strip()
            merged_note = f"{note}; merged: {drop_body[:120]}".strip("; ")
            from pathlib import Path

            keep_path = Path(str(keep.get("path") or ""))
            update_atom_meta(keep_path, {"reason": merged_note[:200]})
            mark_atom_archived(paths, drop_id, reason="merged", merged_into=keep_id)
            log_consolidation_event(
                paths,
                {
                    "action": "merge",
                    "kept_id": keep_id,
                    "archived_id": drop_id,
                    "topic_key": str(keep.get("topic_key") or ""),
                },
            )
            merged += 1
            break
    return merged


def compress_topic_chains(
    paths,
    *,
    cfg: dict[str, Any],
    embedding_port=None,
) -> int:
    max_chain = int(cfg.get("memory_topic_chain_max") or 8)
    max_chain = max(3, min(20, max_chain))
    compressed = 0
    groups = group_atoms_by_topic_key(_active_atoms(paths))
    for topic_key, items in groups.items():
        if len(items) <= max_chain:
            continue
        ordered = sorted(items, key=lambda a: int(a.get("seq") or 0))
        keep_tail = ordered[-max_chain:]
        keep_ids = {str(a.get("id") or "") for a in keep_tail}
        archive_candidates = [a for a in ordered[:-max_chain] if str(a.get("id") or "") not in keep_ids]
        if not archive_candidates:
            continue
        summary_body = format_evolution_timeline(ordered, max_events=max_chain)
        if summary_body:
            summary_path = write_atom(
                paths,
                atom_type="fact",
                content=summary_body[:800],
                session_id=str(ordered[-1].get("session_id") or ""),
                topic_key=topic_key,
                importance=0.75,
                resolved_topic=topic_key,
                embedding_port=embedding_port,
                topic_cluster_cfg={
                    "topic_cluster_enabled": False,
                    "embedding_provider": "off",
                },
            )
            update_atom_meta(summary_path, {"chain_summary": True})
        for atom in archive_candidates:
            if is_pinned(enrich_atom(dict(atom))):
                continue
            atom_id = str(atom.get("id") or "")
            if not atom_id:
                continue
            mark_atom_archived(paths, atom_id, reason="chain_compress")
            log_consolidation_event(
                paths,
                {"action": "chain_compress", "atom_id": atom_id, "topic_key": topic_key},
            )
            compressed += 1
    return compressed


def compress_l3_profile(
    souls_root,
    bot_id: str,
    *,
    cfg: dict[str, Any],
    profile: dict | None = None,
) -> bool:
    del profile  # reserved for future summary-role compression
    from ..store_l3 import read_user_profile, write_user_profile
    from ...brains.budgets import truncate_to_budget

    max_chars = int(cfg.get("memory_l3_max_chars") or 1600)
    text = read_user_profile(souls_root, bot_id)
    if len(text) <= max_chars:
        return False
    compressed = truncate_to_budget(text, max(200, max_chars // 3))
    write_user_profile(souls_root, bot_id, compressed[:max_chars])
    return True
