"""Capacity-driven memory consolidation engine."""

from __future__ import annotations

import json
from typing import Any

from ....storage.common import now_iso
from ..paths import BotMemoryPaths
from ..store_l1 import list_atoms
from .actions import archive_low_value_atoms, compress_l3_profile, compress_topic_chains, merge_similar_atoms
from .audit import log_consolidation_event


def _state_path(paths: BotMemoryPaths):
    return paths.root / "consolidation_state.json"


def load_consolidation_state(paths: BotMemoryPaths) -> dict[str, Any]:
    path = _state_path(paths)
    if not path.exists():
        return {"last_run_at": ""}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"last_run_at": ""}


def save_consolidation_state(paths: BotMemoryPaths, state: dict[str, Any]) -> None:
    path = _state_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def capacity_exceeded(
    paths: BotMemoryPaths,
    souls_root,
    bot_id: str,
    cfg: dict[str, Any],
) -> bool:
    if not bool(cfg.get("memory_consolidation_enabled", False)):
        return False
    max_atoms = int(cfg.get("memory_l1_max_atoms") or 300)
    if len(list_atoms(paths, include_archived=False)) > max_atoms:
        return True
    max_chars = int(cfg.get("memory_l3_max_chars") or 1600)
    from ..store_l3 import read_user_profile

    if len(read_user_profile(souls_root, bot_id)) > max_chars:
        return True
    max_chain = int(cfg.get("memory_topic_chain_max") or 8)
    from ..topic_metadata import group_atoms_by_topic_key

    for _key, items in group_atoms_by_topic_key(list_atoms(paths)).items():
        if len(items) > max_chain:
            return True
    return False


def run_consolidation(
    paths: BotMemoryPaths,
    *,
    souls_root,
    bot_id: str,
    cfg: dict[str, Any],
    embedding_port=None,
    summary_profile: dict | None = None,
) -> dict[str, Any]:
    if not bool(cfg.get("memory_consolidation_enabled", False)):
        return {"skipped": True, "reason": "disabled"}

    half_life = float(cfg.get("memory_recency_half_life_days") or 90)
    stats = {
        "archived": archive_low_value_atoms(paths, cfg=cfg, half_life_days=half_life),
        "merged": merge_similar_atoms(paths, embedding_port=embedding_port, cfg=cfg),
        "chain_compressed": compress_topic_chains(paths, cfg=cfg, embedding_port=embedding_port),
        "l3_compressed": int(
            compress_l3_profile(souls_root, bot_id, cfg=cfg, profile=summary_profile)
        ),
    }
    stats["total"] = stats["archived"] + stats["merged"] + stats["chain_compressed"] + stats["l3_compressed"]
    save_consolidation_state(
        paths,
        {"last_run_at": now_iso(), "last_stats": stats},
    )
    if stats["total"]:
        log_consolidation_event(paths, {"action": "run_complete", **stats})
    return stats


def maybe_run_consolidation(
    paths: BotMemoryPaths,
    *,
    souls_root,
    bot_id: str,
    cfg: dict[str, Any],
    embedding_port=None,
    summary_profile: dict | None = None,
    force: bool = False,
) -> dict[str, Any] | None:
    if not bool(cfg.get("memory_consolidation_enabled", False)):
        return None
    if not force and not capacity_exceeded(paths, souls_root, bot_id, cfg):
        return None
    return run_consolidation(
        paths,
        souls_root=souls_root,
        bot_id=bot_id,
        cfg=cfg,
        embedding_port=embedding_port,
        summary_profile=summary_profile,
    )
