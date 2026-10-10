"""Tests for rerank factory and config."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.memory.rerank.factory import create_reranker
from backend.domain.memory.rerank.port import NullReranker
from backend.storage.config_store import normalize_config


def test_rerank_defaults_disabled() -> None:
    cfg = normalize_config({})
    assert cfg["rerank_enabled"] is False
    assert cfg["rerank_provider"] == "off"
    assert cfg["rerank_candidate_pool"] == 20
    assert cfg["rerank_top_k"] == 5


def test_factory_returns_null_when_disabled() -> None:
    port = create_reranker({"rerank_enabled": False})
    assert isinstance(port, NullReranker)


if __name__ == "__main__":
    test_rerank_defaults_disabled()
    test_factory_returns_null_when_disabled()
    print("rerank port smoke OK")
