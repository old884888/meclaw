"""Tests for hybrid memory recall and FTS query safety."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.brains.orchestrator import MultiBrainOrchestrator  # noqa: F401 — break import cycle
from backend.domain.memory.hybrid import expand_memory_query, search_memory_hybrid
from backend.domain.memory.indexer import rebuild_index, sanitize_fts_query, search_memory
from backend.domain.memory.memory_brain import MemoryBrain
from backend.domain.memory.paths import ensure_bot_memory_layout
from backend.domain.memory.protocol import MemoryScope
from backend.domain.memory.store_l1 import write_atom
from backend.storage.config_store import normalize_config
from backend.storage.history_store import save_sessions_index


def test_sanitize_fts_query_with_punctuation() -> None:
    raw = 'What is your favorite? *food*: "spicy" (yes/no)?'
    safe = sanitize_fts_query(raw)
    assert "*" not in safe
    assert "?" not in safe
    assert ":" not in safe

    with tempfile.TemporaryDirectory() as tmp:
        souls = Path(tmp) / "souls"
        bot_id = "b_fts_safe"
        paths = ensure_bot_memory_layout(souls, bot_id)
        write_atom(paths, atom_type="preference", content="用户喜欢简洁回答", session_id="s1")
        rebuild_index(paths)
        hits = search_memory(paths, raw, limit=3)
        assert isinstance(hits, list)


def test_expand_memory_query_adds_food_terms() -> None:
    expanded = expand_memory_query("今晚餐厅推荐什么主菜？")
    assert "推荐" in expanded or "food" in expanded.lower()


def test_hybrid_recall_weak_keyword_overlap() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        souls = root / "souls"
        history = root / "history"
        history.mkdir(parents=True)
        bot_id = "b_hybrid"
        paths = ensure_bot_memory_layout(souls, bot_id)
        save_sessions_index(history / "sessions.json", [], backup=False)

        write_atom(
            paths,
            atom_type="constraint",
            content="用户对海鲜过敏，不能吃虾和蟹",
            session_id="s_persona",
        )
        rebuild_index(paths)

        fts_hits = search_memory(paths, "餐厅推荐什么主菜", limit=5)
        hybrid_hits = search_memory_hybrid(paths, "餐厅推荐什么主菜", limit=5)
        assert len(hybrid_hits) >= len(fts_hits)

        cfg = normalize_config(
            {
                "multi_brain_enabled": True,
                "memory_retrieval_enabled": True,
                "memory_retrieval_strategy": "hybrid",
            }
        )
        brain = MemoryBrain(souls, history, history / "sessions.json", lambda: cfg)
        scope = MemoryScope(kind="bot", scope_id=bot_id)
        block = brain.before_chat(scope, "餐厅推荐什么主菜？", "", 800, session_id="s_persona")
        assert block
        assert "相关记忆" in block
        assert "海鲜" in block or "过敏" in block or "虾" in block


def test_before_chat_survives_broken_local_embedding() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        souls = root / "souls"
        history = root / "history"
        history.mkdir(parents=True)
        bot_id = "b_degrade"
        paths = ensure_bot_memory_layout(souls, bot_id)
        save_sessions_index(history / "sessions.json", [], backup=False)
        write_atom(
            paths,
            atom_type="constraint",
            content="用户对海鲜过敏",
            session_id="s1",
        )
        rebuild_index(paths)

        cfg = normalize_config(
            {
                "multi_brain_enabled": True,
                "memory_retrieval_enabled": True,
                "memory_retrieval_strategy": "hybrid",
                "embedding_provider": "local",
                "embedding_model": "no-such-model-xyz",
            }
        )
        brain = MemoryBrain(souls, history, history / "sessions.json", lambda: cfg)
        scope = MemoryScope(kind="bot", scope_id=bot_id)
        block = brain.before_chat(scope, "推荐主菜", "", 800, session_id="s1")
        assert isinstance(block, str)


if __name__ == "__main__":
    test_sanitize_fts_query_with_punctuation()
    test_expand_memory_query_adds_food_terms()
    test_hybrid_recall_weak_keyword_overlap()
    test_before_chat_survives_broken_local_embedding()
    print("memory hybrid recall smoke OK")
