"""Context compaction engine — tier 1/2 without LLM, tier 3 stub."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..brains.budgets import estimate_tokens


@dataclass
class CompactionResult:
    messages: list[dict[str, Any]]
    tier: int
    ratio: float


def estimate_messages_tokens(messages: list[dict]) -> int:
    return sum(estimate_tokens(str(m.get("content") or "")) for m in messages)


def context_ratio(messages: list[dict], max_context: int) -> float:
    limit = max(1024, int(max_context or 65536))
    return estimate_messages_tokens(messages) / limit


def _replacement_cache_path(cache_dir: Path, session_id: str) -> Path:
    return cache_dir / f"{session_id}.json"


def _load_cache(cache_dir: Path, session_id: str) -> dict[str, dict]:
    path = _replacement_cache_path(cache_dir, session_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_cache(cache_dir: Path, session_id: str, cache: dict[str, dict]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _replacement_cache_path(cache_dir, session_id).write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _split_protection_zone(messages: list[dict], protection_tokens: int) -> tuple[list[dict], list[dict]]:
    if protection_tokens <= 0 or not messages:
        return [], list(messages)
    protected: list[dict] = []
    compressible: list[dict] = []
    used = 0
    for m in reversed(messages):
        est = estimate_tokens(str(m.get("content") or ""))
        if used + est <= protection_tokens:
            protected.insert(0, m)
            used += est
        else:
            compressible.insert(0, m)
    if not protected and messages:
        protected = [messages[-1]]
        compressible = messages[:-1]
    return protected, compressible


def tier1_snip(messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        content = str(m.get("content") or "")
        role = m.get("role")
        if role == "tool" and len(content) > 1000:
            content = content[:500] + f"\n…[已截短，共 {len(content)} 字符]"
        elif role == "user" and content.count("\n") > 20:
            lines = content.split("\n")
            content = "\n".join(lines[:20]) + f"\n…[共 {len(lines)} 行]"
        elif role == "assistant" and len(content) > 2000:
            content = content[:800] + f"\n…[已截短，共 {len(content)} 字符]"
        out.append({**m, "content": content})
    return out


def tier2_prune(messages: list[dict], session_id: str, cache_dir: Path) -> list[dict]:
    cache = _load_cache(cache_dir, session_id)
    out: list[dict] = []
    for i, m in enumerate(messages):
        part_id = str(m.get("id") or f"idx_{i}")
        if part_id in cache:
            decision = cache[part_id]
            out.append({**m, "content": decision.get("content", m.get("content", ""))})
            continue
        content = str(m.get("content") or "")
        role = m.get("role")
        decision: dict[str, str]
        if role == "assistant" and len(content) > 500:
            decision = {"action": "truncate", "content": content[:200] + " …[已压缩]"}
        elif role == "user" and len(content) > 800:
            decision = {"action": "truncate", "content": content[:300] + " …[已压缩]"}
        else:
            decision = {"action": "keep", "content": content}
        if decision["action"] != "keep":
            cache[part_id] = decision
        out.append({**m, "content": decision["content"]})
    _save_cache(cache_dir, session_id, cache)
    return out


def compact_messages(
    messages: list[dict],
    *,
    session_id: str,
    max_context: int,
    cache_dir: Path,
    tier1_pct: int = 60,
    tier2_pct: int = 80,
    tier3_pct: int = 95,
    protection_zone_tokens: int = 8000,
    running_summary: str = "",
) -> CompactionResult:
    ratio = context_ratio(messages, max_context)
    if ratio < tier1_pct / 100:
        return CompactionResult(messages=messages, tier=0, ratio=ratio)

    protected, compressible = _split_protection_zone(messages, protection_zone_tokens)
    tier = 1
    compressible = tier1_snip(compressible)

    if ratio >= tier2_pct / 100:
        tier = 2
        compressible = tier2_prune(compressible, session_id, cache_dir)

    if ratio >= tier3_pct / 100:
        tier = 3
        if running_summary.strip():
            summary_msg = {"role": "system", "content": f"[对话摘要]\n{running_summary.strip()}"}
            return CompactionResult(messages=[summary_msg, *protected], tier=tier, ratio=ratio)
        # tier3 reached but no summary yet — still collapse old compressible history
        return CompactionResult(messages=[*protected], tier=tier, ratio=ratio)

    return CompactionResult(messages=[*compressible, *protected], tier=tier, ratio=ratio)
