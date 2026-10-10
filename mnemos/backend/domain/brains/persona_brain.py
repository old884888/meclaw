"""Right brain (Persona): L3 user profile snippet.

Soul and constraints are owned by the stable system prompt
(`main._system_prompt` -> `system_base`) and must NOT be duplicated here,
otherwise they are injected twice per turn (wasting tokens and breaking the
cache-friendly stable prefix). This brain only contributes the aggregated
L3 user profile excerpt.
"""

from __future__ import annotations

from pathlib import Path

from ..memory.store_l3 import read_profile_excerpt
from .budgets import truncate_to_budget


def build_persona_block(
    souls_root: Path,
    bot_id: str,
    *,
    budget_tokens: int,
) -> str:
    profile_excerpt = read_profile_excerpt(souls_root, bot_id, budget_tokens=budget_tokens)
    if not profile_excerpt:
        return ""
    block = f"[用户画像]\n{profile_excerpt}"
    return truncate_to_budget(block, budget_tokens)
