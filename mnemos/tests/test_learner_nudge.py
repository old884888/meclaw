"""Tests for P6a learner nudge triggers."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.brains.learner_brain import LearnerBrain
from backend.domain.learner.nudge import classify_turn_signal, maybe_enqueue_nudge_candidate
from backend.domain.learner.nudge.triggers import candidate_type_for_trigger


def test_classify_user_correction() -> None:
    assert classify_turn_signal(user_input="不对，应该是美式", assistant_output="好的") == "user_correction"
    assert candidate_type_for_trigger("user_correction") == "prompt_hint"


def test_classify_task_completion() -> None:
    assert classify_turn_signal(user_input="搞定了，任务完成了", assistant_output="收到") == "task_completion"
    assert candidate_type_for_trigger("task_completion") == "skill_draft"


def test_nudge_dedupe_within_window() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        learner = LearnerBrain(Path(tmp))
        cfg = {"learner_nudge_enabled": True, "learner_nudge_dedupe_hours": 24}
        first = maybe_enqueue_nudge_candidate(
            learner,
            bot_id="b1",
            session_id="s1",
            user_input="不对，你理解错了",
            assistant_output="抱歉",
            messages=[{"role": "user", "content": "不对，你理解错了"}],
            cfg=cfg,
        )
        second = maybe_enqueue_nudge_candidate(
            learner,
            bot_id="b1",
            session_id="s2",
            user_input="又错了，应该是 B",
            assistant_output="明白",
            messages=[{"role": "user", "content": "又错了，应该是 B"}],
            cfg=cfg,
        )
        assert first is not None
        assert second is None


def test_nudge_disabled_returns_none() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        learner = LearnerBrain(Path(tmp))
        out = maybe_enqueue_nudge_candidate(
            learner,
            bot_id="b1",
            session_id="s1",
            user_input="不对",
            assistant_output="ok",
            messages=[],
            cfg={"learner_nudge_enabled": False},
        )
        assert out is None
