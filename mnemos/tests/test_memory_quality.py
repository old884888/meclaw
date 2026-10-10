"""Tests for P4 memory quality: supersede, dedupe, composite scoring."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.memory.memory_scoring import (
    composite_recall_score,
    is_superseded,
    rerank_hits_by_quality,
)
from backend.domain.memory.paths import ensure_bot_memory_layout
from backend.domain.memory.store_l1 import (
    find_current_topic_atom,
    get_atom_by_id,
    increment_hit_count,
    write_atom,
)
from backend.domain.memory.topic_metadata import enrich_atom


def test_switch_atom_supersedes_prior() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = ensure_bot_memory_layout(Path(tmp) / "souls", "b_p4")
        path1 = write_atom(
            paths,
            atom_type="preference",
            content="我喜欢喝拿铁",
            topic_key="drink",
            polarity="positive",
        )
        path2 = write_atom(
            paths,
            atom_type="preference",
            content="我改成只喝美式了",
            topic_key="drink",
            polarity="switch",
            reason="更健康",
        )
        first_id = read_atom_id(path1)
        new_id = read_atom_id(path2)
        new_atom = get_atom_by_id(paths, new_id)
        first_atom = get_atom_by_id(paths, first_id)
        assert new_atom is not None and first_atom is not None
        assert str(new_atom.get("supersedes_id") or "") == first_id
        assert str(first_atom.get("superseded_by") or "") == new_id
        current = find_current_topic_atom(paths, "drink")
        assert current is not None
        assert current.get("id") == new_id


def read_atom_id(path: Path) -> str:
    from backend.domain.memory.store_l1 import read_atom_file

    atom = read_atom_file(path)
    assert atom is not None
    return str(atom.get("id"))


def test_increment_hit_count() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = ensure_bot_memory_layout(Path(tmp) / "souls", "b_hit")
        path = write_atom(paths, atom_type="fact", content="用户名叫 Alice")
        atom_id = read_atom_id(path)
        increment_hit_count(paths, atom_id)
        atom = get_atom_by_id(paths, atom_id)
        assert atom is not None
        assert int(atom.get("hit_count") or 0) == 1


def test_composite_score_prefers_constraint() -> None:
    constraint = enrich_atom({"type": "constraint", "content": "对花生过敏", "created_at": "2020-01-01T00:00:00+00:00"})
    fact = enrich_atom({"type": "fact", "content": "喜欢蓝色", "created_at": "2026-06-01T00:00:00+00:00"})
    cfg = {
        "memory_score_importance_weight": 0.5,
        "memory_score_recency_weight": 0.2,
        "memory_score_hit_weight": 0.0,
    }
    c_score = composite_recall_score(constraint, 0.5, cfg)
    f_score = composite_recall_score(fact, 0.5, cfg)
    assert c_score > f_score


def test_composite_score_boosts_hit_count() -> None:
    low_hit = enrich_atom(
        {
            "id": "a_low",
            "type": "fact",
            "content": "a",
            "hit_count": 0,
            "created_at": "2026-06-01T00:00:00+00:00",
        }
    )
    high_hit = enrich_atom(
        {
            "id": "a_high",
            "type": "fact",
            "content": "b",
            "hit_count": 8,
            "created_at": "2026-06-01T00:00:00+00:00",
        }
    )
    hits = [
        {"id": "a_low", "hybrid_score": 0.5},
        {"id": "a_high", "hybrid_score": 0.5},
    ]
    ranked = rerank_hits_by_quality(
        hits,
        {"a_low": low_hit, "a_high": high_hit},
        {"memory_score_hit_weight": 0.5, "memory_score_importance_weight": 0.0, "memory_score_recency_weight": 0.0},
    )
    assert ranked[0]["id"] == "a_high"


def test_composite_score_allows_zero_weights() -> None:
    atom = enrich_atom(
        {
            "id": "a_zero",
            "type": "fact",
            "content": "z",
            "hit_count": 5,
            "created_at": "2026-06-01T00:00:00+00:00",
        }
    )
    cfg = {
        "memory_score_relevance_weight": 0.0,
        "memory_score_importance_weight": 0.0,
        "memory_score_recency_weight": 0.0,
        "memory_score_hit_weight": 0.0,
    }
    score = composite_recall_score(atom, 0.5, cfg)
    assert score == 0.0


def test_quality_rerank_preserves_relevance_order_when_quality_disabled() -> None:
    atom_a = enrich_atom({"id": "a", "type": "fact", "content": "a", "created_at": "2026-06-01T00:00:00+00:00"})
    atom_b = enrich_atom({"id": "b", "type": "fact", "content": "b", "created_at": "2026-06-01T00:00:00+00:00"})
    atom_c = enrich_atom({"id": "c", "type": "fact", "content": "c", "created_at": "2026-06-01T00:00:00+00:00"})
    hits = [
        {"id": "a", "hybrid_score": 0.03},
        {"id": "b", "hybrid_score": 0.02},
        {"id": "c", "hybrid_score": 0.01},
    ]
    ranked = rerank_hits_by_quality(
        hits,
        {"a": atom_a, "b": atom_b, "c": atom_c},
        {
            "memory_score_relevance_weight": 1.0,
            "memory_score_importance_weight": 0.0,
            "memory_score_recency_weight": 0.0,
            "memory_score_hit_weight": 0.0,
        },
    )
    assert [x["id"] for x in ranked] == ["a", "b", "c"]


def main() -> None:
    test_switch_atom_supersedes_prior()
    test_increment_hit_count()
    test_composite_score_prefers_constraint()
    test_composite_score_boosts_hit_count()
    test_composite_score_allows_zero_weights()
    test_quality_rerank_preserves_relevance_order_when_quality_disabled()
    print("memory quality tests OK")


if __name__ == "__main__":
    main()
