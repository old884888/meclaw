"""Tests for L1 evolution metadata, L3 timelines, and topic-chain recall."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.brains.orchestrator import MultiBrainOrchestrator  # noqa: F401
from backend.domain.memory.indexer import rebuild_index
from backend.domain.memory.l1_extractor import extract_atoms_heuristic
from backend.domain.memory.memory_brain import MemoryBrain
from backend.domain.memory.paths import ensure_bot_memory_layout
from backend.domain.memory.profile_aggregator import aggregate_persona_profile
from backend.domain.memory.protocol import MemoryScope
from backend.domain.memory.store_l1 import list_atoms, read_atom_file, write_atom
from backend.domain.memory.topic_metadata import enrich_atom, infer_polarity
from backend.storage.config_store import normalize_config
from backend.storage.history_store import save_sessions_index


def _setup(tmp: str, bot_id: str = "b_evo"):
    root = Path(tmp)
    souls = root / "souls"
    history = root / "history"
    history.mkdir(parents=True)
    save_sessions_index(history / "sessions.json", [], backup=False)
    paths = ensure_bot_memory_layout(souls, bot_id)
    return souls, history, paths


def test_switch_message_extracts_polarity_and_reason() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _souls, _history, paths = _setup(tmp)
        msg = "我改成喝茶了，因为医生建议减少咖啡因"
        created = extract_atoms_heuristic(
            paths,
            session_id="s1",
            user_message=msg,
            assistant_message="好的，我会记住。",
        )
        assert len(created) == 1
        atom = enrich_atom(created[0])
        assert atom["polarity"] == "switch"
        assert "医生" in atom["reason"] or "咖啡因" in atom["reason"]
        assert atom["topic_key"] == "drink"


def test_three_atoms_same_topic_render_timeline() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _souls, _history, paths = _setup(tmp)
        write_atom(
            paths,
            atom_type="preference",
            content="用户喜欢咖啡，每天三杯",
            session_id="s1",
            topic_key="drink",
            seq=1,
        )
        write_atom(
            paths,
            atom_type="preference",
            content="用户改喝茶了，因为医生建议减少咖啡因",
            session_id="s2",
            topic_key="drink",
            polarity="switch",
            seq=2,
            reason="医生建议减少咖啡因",
        )
        write_atom(
            paths,
            atom_type="preference",
            content="用户现在只喝绿茶",
            session_id="s3",
            topic_key="drink",
            polarity="switch",
            seq=3,
        )
        profile = aggregate_persona_profile(paths)
        assert "演变" in profile
        assert "→ 当前" in profile
        assert "绿茶" in profile


def test_topic_chain_recall_injects_ordered_block() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls, history, paths = _setup(tmp)
        bot_id = "b_evo"
        write_atom(paths, atom_type="preference", content="喜欢咖啡", session_id="s1", topic_key="drink", seq=1)
        write_atom(
            paths,
            atom_type="preference",
            content="改喝茶因为医生要求",
            session_id="s2",
            topic_key="drink",
            polarity="switch",
            seq=2,
            reason="医生要求",
        )
        write_atom(paths, atom_type="preference", content="现在只喝绿茶", session_id="s3", topic_key="drink", seq=3)
        rebuild_index(paths)

        cfg = normalize_config({"multi_brain_enabled": True, "memory_retrieval_enabled": True})
        brain = MemoryBrain(souls, history, history / "sessions.json", lambda: cfg)
        block = brain.before_chat(
            MemoryScope(kind="bot", scope_id=bot_id),
            query="用户现在喝什么",
            session_summary="",
            budget_tokens=1200,
            session_id="s_q",
        )
        assert block
        assert "偏好演变" in block
        assert "→ 当前" in block
        assert "咖啡" in block
        assert "绿茶" in block


def test_evolution_query_gets_full_chain_block() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls, history, paths = _setup(tmp)
        bot_id = "b_evo"
        write_atom(paths, atom_type="preference", content="喜欢咖啡", session_id="s1", topic_key="drink", seq=1)
        write_atom(
            paths,
            atom_type="preference",
            content="改喝茶因为医生要求",
            session_id="s2",
            topic_key="drink",
            polarity="switch",
            seq=2,
            reason="医生要求",
        )
        write_atom(paths, atom_type="preference", content="现在只喝绿茶", session_id="s3", topic_key="drink", seq=3)
        rebuild_index(paths)

        cfg = normalize_config({"multi_brain_enabled": True, "memory_retrieval_enabled": True})
        brain = MemoryBrain(souls, history, history / "sessions.json", lambda: cfg)
        block = brain.before_chat(
            MemoryScope(kind="bot", scope_id=bot_id),
            query="描述用户饮品偏好的完整演变过程",
            session_summary="",
            budget_tokens=1200,
            session_id="s_q",
        )
        assert "偏好演变" in block
        assert "→ 当前" in block


def test_fact_query_prioritizes_unrelated_hits() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls, history, paths = _setup(tmp)
        bot_id = "b_evo"
        write_atom(paths, atom_type="preference", content="喜欢咖啡", session_id="s1", topic_key="drink", seq=1)
        write_atom(
            paths,
            atom_type="preference",
            content="改喝茶因为医生要求",
            session_id="s2",
            topic_key="drink",
            polarity="switch",
            seq=2,
        )
        write_atom(paths, atom_type="preference", content="现在只喝绿茶", session_id="s3", topic_key="drink", seq=3)
        write_atom(
            paths,
            atom_type="fact",
            content="用户的猫叫小花，三岁",
            session_id="s4",
            topic_key="pets",
            seq=10,
        )
        rebuild_index(paths)

        cfg = normalize_config({"multi_brain_enabled": True, "memory_retrieval_enabled": True})
        brain = MemoryBrain(souls, history, history / "sessions.json", lambda: cfg)
        block = brain.before_chat(
            MemoryScope(kind="bot", scope_id=bot_id),
            query="用户的猫叫什么名字",
            session_summary="",
            budget_tokens=400,
            session_id="s_q",
        )
        assert "小花" in block
        assert block.index("小花") < block.find("偏好演变") if "偏好演变" in block else True
        assert "偏好演变" not in block or "当前" in block


def test_split_recall_budget_fact_vs_evolution() -> None:
    from backend.domain.memory.topic_metadata import split_recall_budget

    hit, chain = split_recall_budget(1000, "用户的猫叫什么名字", {})
    assert hit > chain
    hit2, chain2 = split_recall_budget(1000, "偏好如何演变", {})
    assert chain2 >= hit2
    with tempfile.TemporaryDirectory() as tmp:
        _souls, _history, paths = _setup(tmp)
        legacy_path = paths.l1_dir / "legacy.md"
        legacy_path.write_text(
            "\n".join(
                [
                    "---",
                    'id: "atom_legacy1"',
                    'type: "preference"',
                    'layer: "L1"',
                    'session_id: "s1"',
                    'is_deleted: "false"',
                    'created_at: "2026-05-01T10:00:00"',
                    "---",
                    "",
                    "用户喜欢简洁回答",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        atoms = list_atoms(paths)
        assert len(atoms) == 1
        atom = enrich_atom(atoms[0])
        assert atom["topic_key"]
        assert atom["seq"] >= 0
        assert infer_polarity(atom["content"]) in {"positive", "negative", "switch"}
