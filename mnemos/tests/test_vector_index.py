"""Tests for vector index linear scan."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.memory.embedding.vectors import vector_to_blob
from backend.domain.memory.indexer import rebuild_index
from backend.domain.memory.paths import ensure_bot_memory_layout
from backend.domain.memory.store_l1 import write_atom
from backend.domain.memory.vector_index.factory import create_vector_index
from backend.domain.memory.vector_index.port import NullVectorIndex


class _FakeEmbedding:
    @property
    def available(self) -> bool:
        return True

    @property
    def model_identity(self) -> str:
        return "fake:test:3"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] if (t or "").strip() else [] for t in texts]


def test_vector_index_disabled_when_embedding_off() -> None:
    idx = create_vector_index({"embedding_provider": "off"}, _FakeEmbedding())
    assert isinstance(idx, NullVectorIndex)


def test_linear_index_returns_hits() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls = Path(tmp) / "souls"
        paths = ensure_bot_memory_layout(souls, "b_vi")
        write_atom(paths, atom_type="fact", content="用户对海鲜过敏", session_id="s1")
        fake = _FakeEmbedding()
        rebuild_index(paths, embedding_port=fake)
        idx = create_vector_index({"embedding_provider": "local", "ann_enabled": True}, fake)
        hits = idx.query(paths, "餐厅推荐主菜", limit=3, embedding_port=fake)
        assert hits


if __name__ == "__main__":
    test_vector_index_disabled_when_embedding_off()
    test_linear_index_returns_hits()
    print("vector index smoke OK")
