"""Rule-based intent router — zero LLM cost."""

from __future__ import annotations

import re
from dataclasses import dataclass

_CROSS_SESSION_PATTERNS = re.compile(
    r"继续|上次|之前|我们说过|早前|那时候|上回|接着聊|pick up|last time|continue",
    re.IGNORECASE,
)
_COGNITIVE_PATTERNS = re.compile(
    r"步骤|实现|对比|为什么|计划|方案|怎么做|如何|拆解|todo|plan|implement|compare|why|how to",
    re.IGNORECASE,
)
_TRACE_PATTERNS = re.compile(
    r"原文|当时怎么说的|引用|追溯|exactly said|quote|verbatim",
    re.IGNORECASE,
)


@dataclass
class RouteDecision:
    persona: bool = True
    memory: bool = True
    cognitive: bool = False
    cross_session: bool = False
    l0_deep_recall: bool = False


def route_intent(user_message: str, *, cognitive_enabled: bool = True) -> RouteDecision:
    text = (user_message or "").strip()
    decision = RouteDecision()
    if not text:
        return decision
    if _CROSS_SESSION_PATTERNS.search(text):
        decision.cross_session = True
    if cognitive_enabled and _COGNITIVE_PATTERNS.search(text):
        decision.cognitive = True
    if _TRACE_PATTERNS.search(text):
        decision.l0_deep_recall = True
    return decision
