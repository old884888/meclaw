"""Review job: turn classified signals into pending learner candidates."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ....storage.common import now_iso
from ...brains.learner_brain import LearnerBrain
from .triggers import candidate_type_for_trigger, classify_turn_signal


def _parse_iso(ts: str) -> datetime | None:
    text = (ts or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _dedupe_hit(
    learner: LearnerBrain,
    *,
    bot_id: str,
    candidate_type: str,
    dedupe_hours: float,
) -> bool:
    window = timedelta(hours=max(1.0, float(dedupe_hours or 24)))
    now = datetime.now(timezone.utc)
    for item in learner.list_candidates(bot_id=bot_id, status="pending"):
        if str(item.get("type") or "") != candidate_type:
            continue
        created = _parse_iso(str(item.get("created_at") or ""))
        if created and now - created <= window:
            return True
    return False


def _build_candidate_content(
    trigger: str,
    *,
    user_input: str,
    assistant_output: str,
) -> tuple[str, str]:
    user = (user_input or "").strip()[:800]
    asst = (assistant_output or "").strip()[:800]
    if trigger == "user_correction":
        return (
            f"User correction signal: {user[:400]}",
            "User indicated the prior response was wrong; capture corrected preference or constraint.",
        )
    if trigger in ("task_completion", "multi_turn_revision"):
        return (
            f"Procedural pattern from session:\nUser: {user[:300]}\nAssistant: {asst[:300]}",
            f"Trigger={trigger}; consider skill draft for repeatable workflow.",
        )
    if trigger == "topic_burst":
        return (
            f"Sustained topic discussion; summarize evolving preferences:\n{user[:400]}",
            "Topic burst detected; candidate for L3 profile refinement.",
        )
    return (user[:400] or "Learner signal", f"Trigger={trigger}")


def maybe_enqueue_nudge_candidate(
    learner: LearnerBrain,
    *,
    bot_id: str,
    session_id: str,
    user_input: str,
    assistant_output: str,
    messages: list[dict] | None,
    cfg: dict[str, Any],
) -> dict[str, Any] | None:
    if not bool(cfg.get("learner_nudge_enabled", False)):
        return None
    trigger = classify_turn_signal(
        user_input=user_input,
        assistant_output=assistant_output,
        messages=messages,
    )
    if not trigger:
        return None
    candidate_type = candidate_type_for_trigger(trigger)
    if _dedupe_hit(
        learner,
        bot_id=bot_id,
        candidate_type=candidate_type,
        dedupe_hours=float(cfg.get("learner_nudge_dedupe_hours") or 24),
    ):
        return None
    content, reason = _build_candidate_content(
        trigger,
        user_input=user_input,
        assistant_output=assistant_output,
    )
    record = learner.save_candidate(
        bot_id=bot_id,
        candidate_type=candidate_type,
        content=content,
        reason=reason,
        status="pending",
        source_session=session_id,
        trigger=trigger,
    )
    return record
