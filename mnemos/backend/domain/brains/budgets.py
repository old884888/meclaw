"""Token budget helpers for multi-brain prompt assembly."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~2 chars per token for mixed CN/EN."""
    if not text:
        return 0
    return max(1, len(text) // 2)


def truncate_to_budget(text: str, budget_tokens: int) -> str:
    if budget_tokens <= 0 or not text:
        return ""
    max_chars = budget_tokens * 2
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20].rstrip() + "\n…[已截断]"


def fit_lines_to_budget(lines: list[str], budget_tokens: int) -> list[str]:
    out: list[str] = []
    used = 0
    for line in lines:
        est = estimate_tokens(line) + 1
        if used + est > budget_tokens:
            break
        out.append(line)
        used += est
    return out
