"""Skill recall and prompt block formatting."""

from __future__ import annotations

from typing import Any

from ..brains.budgets import truncate_to_budget
from ..memory.topic_registry import cosine_similarity
from .intent import query_wants_skill_recall
from .paths import ensure_skill_layout
from .store import list_skills


def recall_skills_block(
    souls_root,
    bot_id: str,
    query: str,
    *,
    cfg: dict[str, Any],
    embedding_port=None,
) -> str:
    if not bool(cfg.get("skill_recall_enabled", False)):
        return ""
    if not query_wants_skill_recall(query):
        return ""
    paths = ensure_skill_layout(souls_root, bot_id)
    skills = list_skills(paths, status="approved")
    if not skills:
        return ""

    threshold = float(cfg.get("skill_recall_threshold") or 0.65)
    top_k = max(1, min(3, int(cfg.get("skill_recall_top_k") or 1)))
    budget = max(100, int(cfg.get("skill_token_budget") or 400))

    ranked: list[tuple[float, dict[str, Any]]] = []
    if embedding_port is not None and getattr(embedding_port, "available", False):
        try:
            q_vec = embedding_port.embed([query.strip()])[0]
        except Exception:  # noqa: BLE001
            q_vec = []
        if q_vec:
            for skill in skills:
                text = f"{skill.get('title', '')} {skill.get('content', '')}".strip()
                try:
                    s_vec = embedding_port.embed([text])[0]
                except Exception:  # noqa: BLE001
                    continue
                if not s_vec:
                    continue
                score = cosine_similarity(q_vec, s_vec)
                if score >= threshold:
                    ranked.append((score, skill))
    if not ranked:
        # keyword fallback: title/content substring
        q = (query or "").lower()
        for skill in skills:
            blob = f"{skill.get('title', '')} {skill.get('content', '')}".lower()
            if any(tok in blob for tok in q.split() if len(tok) >= 2):
                ranked.append((0.7, skill))
    if not ranked:
        return ""

    ranked.sort(key=lambda x: x[0], reverse=True)
    lines = ["[相关技能]"]
    for score, skill in ranked[:top_k]:
        title = str(skill.get("title") or skill.get("id") or "skill")
        body = str(skill.get("content") or "").strip()
        lines.append(f"### {title}")
        lines.append(body[:600])
    block = truncate_to_budget("\n".join(lines), budget)
    return block.strip()
