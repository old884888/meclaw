"""Tests for memory index embedding cache columns."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

from pytest import approx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.memory.embedding.port import NullEmbedding
from backend.domain.memory.embedding.vectors import blob_to_vector, vector_to_blob
from backend.domain.memory.indexer import INDEX_SCHEMA_VERSION, rebuild_index, list_indexed_records
from backend.domain.memory.paths import ensure_bot_memory_layout
from backend.domain.memory.store_l1 import write_atom


class _FakeEmbedding:
    @property
    def available(self) -> bool:
        return True

    @property
    def model_identity(self) -> str:
        return "fake:test:3"

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            t = (text or "").strip()
            if not t:
                out.append([])
                continue
            out.append([1.0, 0.0, float(len(t))])
        return out


def test_vector_blob_roundtrip() -> None:
    vec = [0.1, -0.2, 0.3]
    got = blob_to_vector(vector_to_blob(vec))
    # 存储走 float32，读回是 float64，末位必然有误差（0.1 -> 0.10000000149011612）。
    # 语义上等价即通过。
    assert got == approx(vec)


def test_index_migration_and_cached_vector() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls = Path(tmp) / "souls"
        bot_id = "b_embed"
        paths = ensure_bot_memory_layout(souls, bot_id)
        write_atom(paths, atom_type="fact", content="用户喜欢简洁回答", session_id="s1")
        fake = _FakeEmbedding()
        rebuild_index(paths, embedding_port=fake)

        conn = sqlite3.connect(paths.index_db)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        cols = {row[1] for row in conn.execute("PRAGMA table_info(memory_index)")}
        conn.close()
        assert version >= INDEX_SCHEMA_VERSION
        assert "embedding" in cols
        assert "embedding_model" in cols

        records = list_indexed_records(paths, limit=10)
        assert records
        assert records[0].get("embedding_vector")
        assert records[0].get("embedding_model") == "fake:test:3"


def test_rebuild_without_port_leaves_null_embedding() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        souls = Path(tmp) / "souls"
        paths = ensure_bot_memory_layout(souls, "b_noembed")
        write_atom(paths, atom_type="fact", content="hello", session_id="s1")
        rebuild_index(paths, embedding_port=NullEmbedding())
        records = list_indexed_records(paths, limit=5)
        assert records[0].get("embedding_vector") is None


if __name__ == "__main__":
    test_vector_blob_roundtrip()
    test_index_migration_and_cached_vector()
    test_rebuild_without_port_leaves_null_embedding()
    print("indexer embedding smoke OK")
