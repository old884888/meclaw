"""Task intent detection for skill recall."""

from __future__ import annotations

import re

TASK_SKILL_RE = re.compile(
    r"怎么做|如何做|步骤|教程|流程|帮我写|如何实现|操作指南|"
    r"how to|step by step|walk me through|guide me|procedure",
    re.I,
)


def query_wants_skill_recall(query: str) -> bool:
    return bool(TASK_SKILL_RE.search(query or ""))
