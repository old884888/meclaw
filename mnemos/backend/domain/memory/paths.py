"""Per-bot personal memory directory layout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...storage.soul_store import bot_soul_dir


@dataclass
class BotMemoryPaths:
    root: Path
    l0_dir: Path
    l1_dir: Path
    l2_dir: Path
    l3_dir: Path
    index_db: Path
    replacement_cache_dir: Path
    deleted_audit: Path


def bot_memory_paths(souls_root: Path, bot_id: str) -> BotMemoryPaths:
    root = bot_soul_dir(souls_root, bot_id) / "memory"
    return BotMemoryPaths(
        root=root,
        l0_dir=root / "l0",
        l1_dir=root / "l1",
        l2_dir=root / "l2",
        l3_dir=root / "l3",
        index_db=root / "index.sqlite",
        replacement_cache_dir=root / "replacement_cache",
        deleted_audit=root / "deleted" / "audit.jsonl",
    )


def ensure_bot_memory_layout(souls_root: Path, bot_id: str) -> BotMemoryPaths:
    paths = bot_memory_paths(souls_root, bot_id)
    for d in (
        paths.l0_dir,
        paths.l1_dir,
        paths.l2_dir,
        paths.l3_dir,
        paths.replacement_cache_dir,
        paths.deleted_audit.parent,
    ):
        d.mkdir(parents=True, exist_ok=True)
    return paths


def session_summary_path(history_dir: Path, session_id: str) -> Path:
    return history_dir / "summaries" / f"{session_id}_summary.md"
