"""Left brain (Cognitive): structured planning block when intent matches."""

from __future__ import annotations

from .budgets import truncate_to_budget


def build_cognitive_block(
    user_message: str,
    session_summary: str,
    *,
    budget_tokens: int,
) -> str:
    if budget_tokens <= 0:
        return ""
    lines = [
        "[思考框架]",
        "在回答前，先理清：",
        "1. 用户当前目标是什么",
        "2. 已知约束与偏好",
        "3. 建议的下一步（可执行、简短）",
    ]
    if session_summary.strip():
        lines.append("")
        lines.append("[会话进展摘要]")
        lines.append(session_summary.strip()[:400])
    lines.append("")
    lines.append(f"[当前问题]\n{user_message.strip()[:300]}")
    return truncate_to_budget("\n".join(lines), budget_tokens)
