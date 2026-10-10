"""Tests for P4c embedding-based topic clustering."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.memory.paths import ensure_bot_memory_layout
from backend.domain.memory.store_l1 import list_atoms, write_atom
from backend.domain.memory.topic_metadata import assign_topic_key, topic_label
from backend.domain.memory.topic_registry import load_topic_registry, rebuild_topic_centroids
from backend.storage.config_store import normalize_config


class MockEmbedding:
    available = True
    model_identity = "test:mock:8"

    _FASHION = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    _TECH = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    _OTHER = [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            lower = (text or "").lower()
            if any(w in lower for w in ("dress", "outfit", "skirt", "wardrobe", "穿搭")):
                out.append(list(self._FASHION))
            elif any(w in lower for w in ("code", "python", "编程")):
                out.append(list(self._TECH))
            else:
                out.append(list(self._OTHER))
        return out


def _cluster_cfg(enabled: bool = True) -> dict:
    return {
        "topic_cluster_enabled": enabled,
        "topic_cluster_threshold": 0.85,
        "embedding_provider": "local" if enabled else "off",
    }


def test_regex_topic_wins_over_cluster() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = ensure_bot_memory_layout(Path(tmp) / "souls", "b_regex")
        embed = MockEmbedding()
        key = assign_topic_key(
            "我每天都要喝一杯拿铁咖啡",
            paths=paths,
            embedding_port=embed,
            cfg=_cluster_cfg(),
        )
        assert key == "drink"


def test_cluster_assigns_similar_open_domain_topic() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = ensure_bot_memory_layout(Path(tmp) / "souls", "b_cluster")
        embed = MockEmbedding()
        cfg = _cluster_cfg()

        key1 = assign_topic_key(
            "Today's outfit is a red dress",
            paths=paths,
            embedding_port=embed,
            cfg=cfg,
        )
        key2 = assign_topic_key(
            "She picked a blue skirt for the party",
            paths=paths,
            embedding_port=embed,
            cfg=cfg,
        )
        assert key1.startswith("topic_")
        assert key2 == key1

        registry = load_topic_registry(paths)
        assert int(registry["topics"][key1]["atom_count"]) == 2


def test_cluster_creates_separate_topics_for_dissimilar_content() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = ensure_bot_memory_layout(Path(tmp) / "souls", "b_split")
        embed = MockEmbedding()
        cfg = _cluster_cfg()

        fashion = assign_topic_key(
            "Her wardrobe has a new dress",
            paths=paths,
            embedding_port=embed,
            cfg=cfg,
        )
        tech = assign_topic_key(
            "User prefers Python for backend code",
            paths=paths,
            embedding_port=embed,
            cfg=cfg,
        )
        assert fashion != tech


def test_embedding_off_falls_back_to_misc_hash() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = ensure_bot_memory_layout(Path(tmp) / "souls", "b_off")
        key = assign_topic_key(
            "A cursed universe setting in fan fiction",
            paths=paths,
            embedding_port=MockEmbedding(),
            cfg={"topic_cluster_enabled": True, "embedding_provider": "off"},
        )
        assert key.startswith("misc_")


def test_write_atom_uses_topic_cluster_cfg() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = ensure_bot_memory_layout(Path(tmp) / "souls", "b_write")
        embed = MockEmbedding()
        write_atom(
            paths,
            atom_type="fact",
            content="New outfit with a vintage dress",
            session_id="s1",
            embedding_port=embed,
            topic_cluster_cfg=_cluster_cfg(),
        )
        write_atom(
            paths,
            atom_type="fact",
            content="Another skirt in the wardrobe",
            session_id="s2",
            embedding_port=embed,
            topic_cluster_cfg=_cluster_cfg(),
        )
        atoms = list_atoms(paths)
        assert len(atoms) == 2
        assert atoms[0]["topic_key"] == atoms[1]["topic_key"]


def test_rebuild_topic_centroids_from_atoms() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = ensure_bot_memory_layout(Path(tmp) / "souls", "b_rebuild")
        embed = MockEmbedding()
        cfg = _cluster_cfg()
        write_atom(
            paths,
            atom_type="preference",
            content="loves a red dress",
            session_id="s1",
            resolved_topic="topic_abc12345",
            embedding_port=embed,
            topic_cluster_cfg=cfg,
        )
        write_atom(
            paths,
            atom_type="preference",
            content="added another skirt",
            session_id="s2",
            resolved_topic="topic_abc12345",
            embedding_port=embed,
            topic_cluster_cfg=cfg,
        )
        registry = rebuild_topic_centroids(paths, embedding_port=embed)
        assert "topic_abc12345" in registry["topics"]
        assert int(registry["topics"]["topic_abc12345"]["atom_count"]) == 2


def test_config_normalizes_topic_cluster_fields() -> None:
    cfg = normalize_config({"topic_cluster_enabled": False, "topic_cluster_threshold": 1.5})
    assert cfg["topic_cluster_enabled"] is False
    assert cfg["topic_cluster_threshold"] == 0.99


def test_topic_label_reads_registry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = ensure_bot_memory_layout(Path(tmp) / "souls", "b_label")
        embed = MockEmbedding()
        key = assign_topic_key(
            "A very specific outfit note",
            paths=paths,
            embedding_port=embed,
            cfg=_cluster_cfg(),
        )
        label = topic_label(key, "A very specific outfit note", paths=paths)
        assert label
        assert label != key or key.startswith("topic_")
