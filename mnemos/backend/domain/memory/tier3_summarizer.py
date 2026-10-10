"""Tier 3 incremental LLM running summary for context compaction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...adapters import providers
from .compaction import _split_protection_zone
from .store_l2 import read_session_summary, write_session_summary


def _meta_path(history_dir: Path, session_id: str) -> Path:
    return history_dir / "summaries" / f"{session_id}_summary_meta.json"


def load_summary_meta(history_dir: Path, session_id: str) -> dict[str, Any]:
    path = _meta_path(history_dir, session_id)
    if not path.exists():
        return {"summarized_message_count": 0, "last_summary": ""}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"summarized_message_count": 0, "last_summary": ""}


def save_summary_meta(history_dir: Path, session_id: str, meta: dict[str, Any]) -> None:
    path = _meta_path(history_dir, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _format_delta(messages: list[dict]) -> str:
    lines: list[str] = []
    for m in messages:
        role = m.get("role", "")
        if role not in ("user", "assistant"):
            continue
        content = str(m.get("content") or "")[:1500]
        lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


def _build_summary_prompt(last_summary: str, delta_text: str, max_length: int) -> str:
    return f"""你是一个对话摘要助手。请基于以下信息生成结构化摘要。

上次摘要：
{last_summary or "（无）"}

新增对话：
{delta_text or "（无）"}

请输出四段式摘要：
1. 【进展】已完成的工作和关键决策
2. 【文件】涉及的关键文件和代码
3. 【待办】未完成的任务和下一步计划
4. 【上下文】用户偏好、错误、约束条件

规则：
- 保留具体文件名、函数名、变量名
- 保留用户明确提出的约束和偏好
- 合并重复信息，新状态覆盖旧状态
- 总长度控制在 {max_length} 字以内
"""


def _heuristic_summary_merge(last_summary: str, delta_messages: list[dict], max_length: int = 2000) -> str:
    lines = ["## 会话进展（自动摘要）", ""]
    if last_summary.strip():
        lines.extend([last_summary.strip(), ""])
    for m in delta_messages[-8:]:
        role = m.get("role", "")
        content = str(m.get("content") or "")[:200]
        lines.append(f"- **{role}**: {content}")
    return "\n".join(lines)[: max_length * 2]


def generate_incremental_summary(
    profile: dict,
    *,
    last_summary: str,
    delta_messages: list[dict],
    max_length: int = 2000,
) -> str:
    delta_text = _format_delta(delta_messages)
    if not delta_text.strip():
        return last_summary
    prompt = _build_summary_prompt(last_summary, delta_text, max_length)
    try:
        return providers.chat_once(
            profile,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=min(1200, max(256, max_length)),
            timeout=60,
        ).strip()
    except Exception:  # noqa: BLE001
        return _heuristic_summary_merge(last_summary, delta_messages, max_length)


def refresh_running_summary_if_needed(
    profile: dict | None,
    history_dir: Path,
    session_id: str,
    api_messages: list[dict],
    *,
    max_context: int,
    tier3_pct: int,
    protection_zone_tokens: int,
    summary_max_length: int = 2000,
    bot_id: str = "",
) -> str:
    """When context pressure hits tier3, merge delta history into running summary via LLM."""
    from .compaction import context_ratio

    ratio = context_ratio(api_messages, max_context)
    if ratio < tier3_pct / 100:
        return read_session_summary(history_dir, session_id)

    history = [m for m in api_messages if m.get("role") in ("user", "assistant")]
    if not history:
        return read_session_summary(history_dir, session_id)

    meta = load_summary_meta(history_dir, session_id)
    last_count = int(meta.get("summarized_message_count") or 0)
    if last_count >= len(history):
        return read_session_summary(history_dir, session_id) or str(meta.get("last_summary") or "")

    protected, compressible = _split_protection_zone(history, protection_zone_tokens)
    delta = [m for m in history[last_count:] if m in compressible or last_count == 0]
    if not delta and last_count < len(history):
        delta = history[last_count:]

    last_summary = read_session_summary(history_dir, session_id) or str(meta.get("last_summary") or "")
    model = str((profile or {}).get("model") or "")
    if bot_id and delta:
        from ..brains.runtime_status import mark_job_failed, mark_job_running, mark_job_success

        mark_job_running(bot_id, "tier3_summary", model=model)
    try:
        if profile and profile.get("api_key") and delta:
            new_summary = generate_incremental_summary(
                profile,
                last_summary=last_summary,
                delta_messages=delta,
                max_length=summary_max_length,
            )
        else:
            new_summary = _heuristic_summary_merge(last_summary, delta, summary_max_length)
        if bot_id and delta:
            mark_job_success(bot_id, "tier3_summary", model=model)
    except Exception as exc:  # noqa: BLE001
        if bot_id and delta:
            mark_job_failed(bot_id, "tier3_summary", str(exc), model=model)
        raise

    write_session_summary(history_dir, session_id, new_summary)
    save_summary_meta(
        history_dir,
        session_id,
        {
            "summarized_message_count": len(history),
            "last_summary": new_summary[:4000],
        },
    )
    return new_summary
