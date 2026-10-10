"""Per-bot skill directory layout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...storage.soul_store import bot_soul_dir


@dataclass
class BotSkillPaths:
    root: Path
    skills_dir: Path
    index_db: Path


def bot_skill_paths(souls_root: Path, bot_id: str) -> BotSkillPaths:
    root = bot_soul_dir(souls_root, bot_id) / "skills"
    return BotSkillPaths(
        root=root,
        skills_dir=root / "approved",
        index_db=root / "skills_index.sqlite",
    )


def ensure_skill_layout(souls_root: Path, bot_id: str) -> BotSkillPaths:
    paths = bot_skill_paths(souls_root, bot_id)
    paths.skills_dir.mkdir(parents=True, exist_ok=True)
    paths.root.mkdir(parents=True, exist_ok=True)
    return paths
