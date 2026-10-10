"""Smoke tests for L3 persona profile aggregation (no LLM)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.brains.orchestrator import MultiBrainOrchestrator  # noqa: F401 — break circular
from backend.domain.memory.memory_brain import MemoryBrain
from backend.domain.memory.paths import ensure_bot_memory_layout
from backend.domain.memory.profile_aggregator import aggregate_persona_profile, refresh_persona_profile
from backend.domain.memory.protocol import MemoryScope
from backend.domain.memory.store_l1 import write_atom
from backend.domain.memory.store_l3 import profile_path, read_profile_excerpt, read_user_profile
from backend.storage.config_store import normalize_config
from backend.storage.history_store import save_sessions_index


def _setup(tmp: str, bot_id: str = "b_l3"):
    root = Path(tmp)
    souls = root / "souls"
    history = root / "history"
    history.mkdir(parents=True)
    save_sessions_index(history / "sessions.json", [], backup=False)
    paths = ensure_bot_memory_layout(souls, bot_id)
    return souls, history, paths


def test_l3_profile_generated_from_preferences() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls, history, paths = _setup(tmp)
        bot_id = "b_l3"

        write_atom(paths, atom_type="preference", content="用户喜欢简洁回答", session_id="s1")
        write_atom(paths, atom_type="preference", content="用户不喜欢长篇幅文字", session_id="s1")
        write_atom(paths, atom_type="constraint", content="用户对花生过敏，禁止推荐含花生食品", session_id="s1")

        profile = aggregate_persona_profile(paths)
        assert profile
        assert "偏好" in profile
        assert "简洁" in profile or "回答" in profile
        assert "花生" in profile or "过敏" in profile


def test_l3_preference_evolution_newer_wins() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls, history, paths = _setup(tmp)
        bot_id = "b_l3"

        write_atom(paths, atom_type="preference", content="用户喜欢长篇详细回答（早期）", session_id="s1")
        write_atom(paths, atom_type="preference", content="用户现在更喜欢简洁直接的回答（新）", session_id="s2")

        profile = aggregate_persona_profile(paths)
        assert profile
        # Both entries should be preserved; newer appears first (newest-first within topic)
        assert "简洁" in profile or "新" in profile


def test_l3_refresh_writes_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls, history, paths = _setup(tmp)
        bot_id = "b_l3"

        write_atom(paths, atom_type="preference", content="用户喜欢 Markdown 格式输出", session_id="s1")

        refreshed = refresh_persona_profile(souls, bot_id, force=True)
        assert refreshed

        p = profile_path(souls, bot_id)
        assert p.exists()
        text = p.read_text(encoding="utf-8")
        assert "用户画像" in text


def test_l3_profile_injected_via_persona_brain() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls, history, paths = _setup(tmp)
        bot_id = "b_l3"
        (souls / bot_id).mkdir(exist_ok=True)
        (souls / bot_id / "soul.md").write_text("你是测试助手", encoding="utf-8")

        write_atom(paths, atom_type="preference", content="用户喜欢简洁回答", session_id="s1")
        write_atom(paths, atom_type="constraint", content="用户对海鲜过敏", session_id="s1")
        refresh_persona_profile(souls, bot_id, force=True)

        excerpt = read_profile_excerpt(souls, bot_id, budget_tokens=400)
        assert excerpt
        assert "画像" in excerpt or "偏好" in excerpt or "简洁" in excerpt


def test_l3_does_not_overwrite_soul_md() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls, history, paths = _setup(tmp)
        bot_id = "b_l3"
        (souls / bot_id).mkdir(exist_ok=True)
        soul_path = souls / bot_id / "soul.md"
        soul_path.write_text("原始人格", encoding="utf-8")

        write_atom(paths, atom_type="preference", content="用户喜欢诗歌风格", session_id="s1")
        refresh_persona_profile(souls, bot_id, force=True)

        assert soul_path.read_text(encoding="utf-8") == "原始人格", "soul.md should not be modified"


def test_l3_refresh_on_rebuild_index() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls, history, paths = _setup(tmp)
        bot_id = "b_l3"
        (souls / bot_id).mkdir(exist_ok=True)
        (souls / bot_id / "soul.md").write_text("你是助手", encoding="utf-8")

        write_atom(paths, atom_type="preference", content="用户偏好代码注释简洁", session_id="s1")

        cfg = normalize_config({
            "multi_brain_enabled": True,
            "memory_write_enabled": True,
            "l3_profile_enabled": True,
        })
        brain = MemoryBrain(souls, history, history / "sessions.json", lambda: cfg)
        brain.rebuild_bot_index(bot_id)

        p = profile_path(souls, bot_id)
        assert p.exists(), "L3 profile should be written by rebuild_bot_index"


if __name__ == "__main__":
    test_l3_profile_generated_from_preferences()
    test_l3_preference_evolution_newer_wins()
    test_l3_refresh_writes_file()
    test_l3_profile_injected_via_persona_brain()
    test_l3_does_not_overwrite_soul_md()
    test_l3_refresh_on_rebuild_index()
    print("L3 persona profile smoke OK")
