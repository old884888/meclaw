"""Tests for P4d memory consolidation."""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.memory.consolidation.engine import maybe_run_consolidation, run_consolidation
from backend.domain.memory.consolidation.pins import is_pinned
from backend.domain.memory.paths import ensure_bot_memory_layout
from backend.domain.memory.store_l1 import list_atoms, write_atom
from backend.domain.memory.topic_registry import cosine_similarity
from backend.storage.config_store import normalize_config


class MockEmbedding:
    available = True
    model_identity = "test:mock:4"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def _cfg(**overrides) -> dict:
    base = normalize_config(
        {
            "memory_consolidation_enabled": True,
            "memory_l1_max_atoms": 2,
            "memory_topic_chain_max": 3,
            "memory_l3_max_chars": 100,
            "memory_consolidation_merge_threshold": 0.9,
            "memory_recency_half_life_days": 30,
        }
    )
    base.update(overrides)
    return base


def test_constraint_atom_is_pinned() -> None:
    assert is_pinned({"type": "constraint", "content": "no peanuts"})
    assert is_pinned({"type": "fact", "content": "x", "importance": 0.95})
    assert not is_pinned({"type": "fact", "content": "x", "importance": 0.4})


def test_archive_low_value_atoms() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls = Path(tmp) / "souls"
        paths = ensure_bot_memory_layout(souls, "b_arc")
        old = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        p = paths.l1_dir / "old-fact.md"
        p.write_text(
            "\n".join(
                [
                    "---",
                    'id: "atom_old1"',
                    'type: "fact"',
                    'layer: "L1"',
                    'confidence: "0.5"',
                    'importance: "0.4"',
                    'hit_count: "0"',
                    f'created_at: "{old}"',
                    'is_archived: "false"',
                    "---",
                    "",
                    "A stale low value fact",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        stats = run_consolidation(
            paths,
            souls_root=souls,
            bot_id="b_arc",
            cfg=_cfg(memory_l1_max_atoms=500),
            embedding_port=MockEmbedding(),
        )
        assert stats["archived"] >= 1
        assert list_atoms(paths) == []


def test_merge_similar_atoms() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls = Path(tmp) / "souls"
        paths = ensure_bot_memory_layout(souls, "b_merge")
        write_atom(
            paths,
            atom_type="fact",
            content="User loves blue shirts",
            topic_key="topic_style",
            resolved_topic="topic_style",
        )
        write_atom(
            paths,
            atom_type="fact",
            content="User loves blue shirts very much",
            topic_key="topic_style",
            resolved_topic="topic_style",
        )
        stats = run_consolidation(
            paths,
            souls_root=souls,
            bot_id="b_merge",
            cfg=_cfg(memory_l1_max_atoms=500),
            embedding_port=MockEmbedding(),
        )
        assert stats["merged"] >= 1
        active = list_atoms(paths)
        assert len(active) == 1


def _write_profile(souls: Path, bot_id: str, text: str) -> None:
    paths = ensure_bot_memory_layout(souls, bot_id)
    (paths.l3_dir / "user_profile.md").write_text(text, encoding="utf-8")


def test_compress_l3_when_over_threshold() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls = Path(tmp) / "souls"
        paths = ensure_bot_memory_layout(souls, "b_l3")
        _write_profile(souls, "b_l3", "X" * 500)
        stats = run_consolidation(
            paths,
            souls_root=souls,
            bot_id="b_l3",
            cfg=_cfg(memory_l3_max_chars=100),
            embedding_port=MockEmbedding(),
        )
        assert stats["l3_compressed"] == 1


def test_consolidation_disabled_is_noop() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls = Path(tmp) / "souls"
        paths = ensure_bot_memory_layout(souls, "b_off")
        write_atom(paths, atom_type="fact", content="hello")
        result = maybe_run_consolidation(
            paths,
            souls_root=souls,
            bot_id="b_off",
            cfg=_cfg(memory_consolidation_enabled=False),
            embedding_port=MockEmbedding(),
            force=True,
        )
        assert result is None or result.get("skipped")
        assert len(list_atoms(paths)) == 1


def test_cosine_identical_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
