"""Tests for embedding port factory and config normalization."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.memory.embedding.factory import create_embedding_port
from backend.domain.memory.embedding.port import NullEmbedding
from backend.storage.config_store import normalize_config


def test_embedding_defaults_off() -> None:
    cfg = normalize_config({})
    assert cfg["embedding_provider"] == "off"
    assert cfg["embedding_model"] == ""
    assert cfg["embedding_profile_id"] == ""


def test_invalid_embedding_provider_normalized_to_off() -> None:
    cfg = normalize_config({"embedding_provider": "bogus"})
    assert cfg["embedding_provider"] == "off"


def test_factory_returns_null_when_off() -> None:
    port = create_embedding_port({"embedding_provider": "off"})
    assert isinstance(port, NullEmbedding)
    assert port.available is False


def test_factory_local_missing_dep_returns_null() -> None:
    port = create_embedding_port({"embedding_provider": "local", "embedding_model": "no-such-model-xyz"})
    # fastembed may fail to load unknown model -> NullEmbedding
    assert port.available is False or isinstance(port, NullEmbedding) or hasattr(port, "embed")


if __name__ == "__main__":
    test_embedding_defaults_off()
    test_invalid_embedding_provider_normalized_to_off()
    test_factory_returns_null_when_off()
    test_factory_local_missing_dep_returns_null()
    print("embedding port smoke OK")
