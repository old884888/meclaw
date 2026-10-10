"""Heuristic L3 persona profile aggregation from L1 atoms.

Reads all L1 atoms for a bot, groups by type and topic_key,
renders preference evolution timelines, and writes a human-readable
Markdown profile to the bot's L3 store.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ...storage.common import now_iso
from .paths import BotMemoryPaths, ensure_bot_memory_layout
from .store_l1 import list_atoms
from .store_l3 import has_real_profile, write_user_profile
from .topic_metadata import enrich_atom, format_evolution_timeline, group_atoms_by_topic_key, topic_label


_TOPIC_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"食|饮食|吃|菜|餐|过敏|忌口|food|meal|diet|allerg", re.I), "饮食偏好"),
    (re.compile(r"写|文案|风格|语气|tone|writing|邮件", re.I), "写作风格"),
    (re.compile(r"旅|旅行|出行|酒店|航班|travel|trip|hotel", re.I), "旅行"),
    (re.compile(r"运动|锻炼|健身|sport|exercise|gym|workout", re.I), "运动健康"),
    (re.compile(r"工作|项目|代码|编程|work|project|code|dev", re.I), "工作/项目"),
    (re.compile(r"音乐|歌|听|music|song|playlist", re.I), "音乐"),
    (re.compile(r"阅读|书|读|book|read", re.I), "阅读"),
    (re.compile(r"简洁|详细|长|短|回答|答复|reply|response|answer", re.I), "回复偏好"),
]

_TYPE_ORDER = ("preference", "constraint", "todo", "fact")
_MAX_TIMELINE_EVENTS = 5


def _infer_topic_label(content: str) -> str:
    for pattern, label in _TOPIC_HINTS:
        if pattern.search(content):
            return label
    return "其他"


def _atom_created_key(atom: dict[str, Any]) -> str:
    return str(atom.get("created_at") or atom.get("meta", {}).get("created_at") or "")


def _group_non_preference_atoms(atoms: list[dict[str, Any]], atom_type: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for atom in sorted(atoms, key=_atom_created_key, reverse=True):
        if str(atom.get("type") or "fact") != atom_type:
            continue
        topic = _infer_topic_label(str(atom.get("content") or ""))
        groups.setdefault(topic, []).append(enrich_atom(dict(atom)))
    return groups


def _render_simple_group_section(
    title: str,
    topic_map: dict[str, list[dict[str, Any]]],
    max_per_topic: int = 3,
) -> str:
    if not topic_map:
        return ""
    lines = [f"### {title}"]
    for topic, items in sorted(topic_map.items()):
        lines.append(f"\n**{topic}**")
        for atom in items[:max_per_topic]:
            content = str(atom.get("content") or "").strip()[:200]
            session = atom.get("session_id") or ""
            ts = (_atom_created_key(atom) or "")[:10]
            source = f" _(s:{session[:8]}, {ts})_" if session or ts else ""
            lines.append(f"- {content}{source}")
        if len(items) > max_per_topic:
            lines.append(f"  _(+{len(items) - max_per_topic} 条历史记录)_")
    return "\n".join(lines)


def _render_preference_section(pref_groups: dict[str, list[dict[str, Any]]]) -> str:
    if not pref_groups:
        return ""
    lines = ["### 偏好"]
    for topic_key in sorted(pref_groups, key=lambda k: topic_label(k, pref_groups[k][-1].get("content", ""))):
        atoms = pref_groups[topic_key]
        lines.append("")
        lines.append(format_evolution_timeline(atoms, max_events=_MAX_TIMELINE_EVENTS))
    return "\n".join(lines)


def aggregate_persona_profile(paths: BotMemoryPaths) -> str:
    """Build L3 persona profile from L1 atoms.  Returns generated profile text."""
    atoms = [enrich_atom(dict(a)) for a in list_atoms(paths)]
    if not atoms:
        return ""

    pref_atoms = [a for a in atoms if str(a.get("type") or "") == "preference"]
    pref_groups = group_atoms_by_topic_key(pref_atoms)

    sections: list[str] = [
        f"## 用户画像（自动聚合，共 {len(atoms)} 条记忆原子）\n\n_updated: {now_iso()[:19]}_\n",
    ]

    pref_section = _render_preference_section(pref_groups)
    if pref_section:
        sections.append(pref_section)

    con_section = _render_simple_group_section(
        "约束/忌口",
        _group_non_preference_atoms(atoms, "constraint"),
    )
    if con_section:
        sections.append(con_section)

    todo_section = _render_simple_group_section(
        "待办事项",
        _group_non_preference_atoms(atoms, "todo"),
    )
    if todo_section:
        sections.append(todo_section)

    fact_section = _render_simple_group_section(
        "其他事实",
        _group_non_preference_atoms(atoms, "fact"),
        max_per_topic=2,
    )
    if fact_section:
        sections.append(fact_section)

    return "\n\n".join(s for s in sections if s)


def refresh_persona_profile(
    souls_root: Path,
    bot_id: str,
    *,
    force: bool = False,
    l3_update_every_n_atoms: int = 5,
) -> bool:
    """Regenerate L3 profile if atom count has grown enough, or if forced."""
    try:
        paths = ensure_bot_memory_layout(souls_root, bot_id)
        atoms = list_atoms(paths)
        if not atoms:
            return False

        if not force and has_real_profile(souls_root, bot_id):
            interval = max(1, l3_update_every_n_atoms)
            if len(atoms) % interval != 0:
                return False

        profile_text = aggregate_persona_profile(paths)
        if profile_text:
            write_user_profile(souls_root, bot_id, profile_text)
            return True
    except Exception:  # noqa: BLE001
        pass
    return False
