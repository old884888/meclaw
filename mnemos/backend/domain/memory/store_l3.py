"""L3 user profile store."""

from __future__ import annotations

from pathlib import Path

from ...storage.soul_store import bot_soul_dir
from .paths import ensure_bot_memory_layout
from ..brains.budgets import truncate_to_budget

DEFAULT_PROFILE = """## 用户画像（自动维护）

- 偏好：待积累
- 长期项目：待积累
- 回复风格：待积累
"""


def profile_path(souls_root: Path, bot_id: str) -> Path:
    paths = ensure_bot_memory_layout(souls_root, bot_id)
    return paths.l3_dir / "user_profile.md"


def has_real_profile(souls_root: Path, bot_id: str) -> bool:
    """True only when an aggregated (non-default, non-empty) profile exists on disk."""
    path = profile_path(souls_root, bot_id)
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8").strip()
    return bool(text) and text != DEFAULT_PROFILE.strip()


def read_user_profile(souls_root: Path, bot_id: str) -> str:
    """Return profile text. Does NOT persist the default template on read
    (persisting it previously blocked initial aggregation in profile_aggregator)."""
    path = profile_path(souls_root, bot_id)
    if not path.exists():
        return DEFAULT_PROFILE.strip()
    return path.read_text(encoding="utf-8").strip()


def write_user_profile(souls_root: Path, bot_id: str, content: str) -> None:
    path = profile_path(souls_root, bot_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def read_profile_excerpt(souls_root: Path, bot_id: str, *, budget_tokens: int) -> str:
    text = read_user_profile(souls_root, bot_id)
    if text == DEFAULT_PROFILE.strip():
        return ""
    return truncate_to_budget(text, budget_tokens)
