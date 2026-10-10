"""Tests for super brain status aggregation."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.brains.brain_status import brain_status_for_bot, memory_stats_for_bot
from backend.domain.brains.runtime_status import save_session_trace
from backend.domain.memory.paths import ensure_bot_memory_layout
from backend.domain.memory.store_l1 import write_atom
from backend.storage.config_store import normalize_bot, normalize_config
from backend.storage.history_store import save_sessions_index


def test_memory_stats_empty_bot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        souls = root / "souls"
        history = root / "history"
        history.mkdir(parents=True)
        souls.mkdir(parents=True)
        bot_id = "b_empty"
        stats = memory_stats_for_bot(souls, history, history / "sessions.json", bot_id)
        assert stats["l0_count"] == 0
        assert stats["l1_count"] == 0
        assert stats["index_status"] == "missing"
        assert stats["l3_available"] is False


def test_memory_stats_with_l1_and_index() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        souls = root / "souls"
        history = root / "history"
        history.mkdir(parents=True)
        bot_id = "b_mem"
        paths = ensure_bot_memory_layout(souls, bot_id)
        write_atom(paths, atom_type="fact", content="用户喜欢简洁", session_id="s1")
        paths.index_db.parent.mkdir(parents=True, exist_ok=True)
        paths.index_db.write_text("{}", encoding="utf-8")
        stats = memory_stats_for_bot(souls, history, history / "sessions.json", bot_id)
        assert stats["l1_count"] >= 1
        assert stats["index_status"] == "ready"


def test_brain_status_for_bot_smoke() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        souls = root / "souls"
        history = root / "history"
        history.mkdir(parents=True)
        bot_id = "b_status"
        ensure_bot_memory_layout(souls, bot_id)
        save_sessions_index(history / "sessions.json", [], backup=False)
        cfg = normalize_config({"multi_brain_enabled": True})
        bot = normalize_bot(
            {
                "id": bot_id,
                "name": "Status Bot",
                "profile_id": "p1",
                "model": "gpt-4o",
                "background_model": "gpt-4o-mini",
            }
        )
        public = {
            "chat_ready": True,
            "provider_name": "Test",
            "brain_message": "",
        }
        save_session_trace(
            "s1",
            {
                "activated": ["executor", "memory"],
                "tokens": {"system": 10, "memory": 50},
                "compact_tier": 1,
                "context_ratio": 0.33,
                "memory": {"recall_count": 5},
            },
        )

        def profile_fn(b: dict, role: str = "executor") -> dict:  # noqa: ARG001
            return {"model": "gpt-4o-mini" if role == "background" else "gpt-4o"}

        status = brain_status_for_bot(
            cfg=cfg,
            bot=bot,
            public_bot=public,
            session_id="s1",
            souls_dir=souls,
            history_dir=history,
            sessions_index_path=history / "sessions.json",
            profile_for_bot_fn=profile_fn,
            max_context_for_bot_fn=lambda _b: 65536,
        )
        assert status["health"]["status"] == "ok"
        assert status["bot"]["executor_model"] == "gpt-4o"
        assert status["memory"]["last_recall_count"] == 5
        assert status["context"]["compact_tier"] == 1
        assert status["turn_trace"]["memory"]["recall_count"] == 5


def main() -> None:
    test_memory_stats_empty_bot()
    test_memory_stats_with_l1_and_index()
    test_brain_status_for_bot_smoke()
    print("brain status tests OK")


if __name__ == "__main__":
    main()
