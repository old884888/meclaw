"""Tests for memory list/search helpers and API route logic."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.memory.paths import ensure_bot_memory_layout
from backend.domain.memory.store_l0 import list_l0_evidence, save_turn_evidence
from backend.domain.memory.store_l1 import write_atom
from backend.domain.memory.store_l2 import list_session_summaries, write_session_summary
from backend.storage.common import now_iso
from backend.storage.history_store import save_sessions_index


def test_list_l0_evidence_empty() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = ensure_bot_memory_layout(root / "souls", "b_l0")
        items, total = list_l0_evidence(paths)
        assert items == []
        assert total == 0


def test_list_l0_evidence_with_data() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = ensure_bot_memory_layout(root / "souls", "b_l0")
        save_turn_evidence(
            paths,
            session_id="sess_a",
            messages=[
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好，有什么可以帮你？"},
            ],
        )
        items, total = list_l0_evidence(paths, limit=10)
        assert total >= 1
        assert items[0]["session_id"] == "sess_a"
        assert "preview" in items[0]
        assert "user:" in items[0]["preview"]


def test_list_l0_evidence_session_filter() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = ensure_bot_memory_layout(root / "souls", "b_l0")
        save_turn_evidence(
            paths,
            session_id="sess_a",
            messages=[{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}],
        )
        save_turn_evidence(
            paths,
            session_id="sess_b",
            messages=[{"role": "user", "content": "c"}, {"role": "assistant", "content": "d"}],
        )
        items, total = list_l0_evidence(paths, session_id="sess_a")
        assert total >= 1
        assert all(i["session_id"] == "sess_a" for i in items)


def test_list_session_summaries() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        history = root / "history"
        history.mkdir(parents=True)
        bot_id = "b_l2"
        sid = "session_1"
        write_session_summary(history, sid, "这是会话摘要内容。")
        sessions = [
            {
                "id": sid,
                "bot_id": bot_id,
                "title": "测试会话",
                "updated_at": now_iso(),
            }
        ]
        save_sessions_index(history / "sessions.json", sessions, backup=False)
        items = list_session_summaries(history, bot_id, sessions, limit=5)
        assert len(items) == 1
        assert items[0]["session_id"] == sid
        assert "summary" in items[0]
        assert "updated_at" in items[0]


def test_list_atoms_pagination_shape() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = ensure_bot_memory_layout(root / "souls", "b_l1")
        for i in range(5):
            write_atom(paths, atom_type="fact", content=f"fact {i}", session_id="s1")
        from backend.domain.memory.store_l1 import list_atoms

        atoms = list_atoms(paths)
        sliced = atoms[2:4]
        assert len(sliced) == 2
        assert all("content" in a for a in sliced)
