"""Rule-based learner nudge trigger classification."""

from __future__ import annotations

import re
from typing import Any

CORRECTION_RE = re.compile(
    r"不对|错了|应该是|不是这样|别这样|改一下|纠正|"
    r"wrong|incorrect|not right|should be|fix this",
    re.I,
)
TASK_DONE_RE = re.compile(
    r"完成了|搞定了|done|finished|任务完成|搞定了|可以了",
    re.I,
)
TASK_INTENT_RE = re.compile(
    r"怎么做|步骤|教程|帮我写|如何实现|how to|step by step|guide me",
    re.I,
)
REVISION_RE = re.compile(
    r"改成|改为|换成|再改|重新|revise|change to|try again",
    re.I,
)

NUDGE_TYPES = frozenset({"user_correction", "multi_turn_revision", "task_completion", "topic_burst"})


def classify_turn_signal(
    *,
    user_input: str,
    assistant_output: str,
    messages: list[dict] | None = None,
) -> str | None:
    """Return a nudge trigger type or None."""
    user = (user_input or "").strip()
    if not user:
        return None
    if CORRECTION_RE.search(user):
        return "user_correction"
    if TASK_DONE_RE.search(user):
        return "task_completion"

    msgs = list(messages or [])
    user_turns = [m for m in msgs if m.get("role") == "user"]
    if len(user_turns) >= 4 and REVISION_RE.search(user):
        return "multi_turn_revision"
    if len(user_turns) >= 8:
        return "topic_burst"
    if len(user_turns) >= 3 and TASK_INTENT_RE.search(user):
        return "multi_turn_revision"
    return None


def candidate_type_for_trigger(trigger: str) -> str:
    if trigger == "user_correction":
        return "prompt_hint"
    if trigger == "task_completion":
        return "skill_draft"
    if trigger == "multi_turn_revision":
        return "skill_draft"
    if trigger == "topic_burst":
        return "l3_profile_update"
    return "prompt_hint"
