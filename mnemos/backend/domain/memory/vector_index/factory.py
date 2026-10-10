"""Construct a VectorIndex from config."""

from __future__ import annotations

from ..embedding.factory import create_embedding_port
from ..embedding.port import EmbeddingPort
from .linear import LinearVectorIndex
from .port import NullVectorIndex, VectorIndex


def _ann_enabled(cfg: dict, embedding_port: EmbeddingPort | None) -> bool:
    if not bool(cfg.get("ann_enabled", True)):
        return False
    provider = str(cfg.get("embedding_provider") or "off").strip().lower()
    if provider == "off":
        return False
    return embedding_port is not None and embedding_port.available


def create_vector_index(cfg: dict, embedding_port: EmbeddingPort | None = None) -> VectorIndex:
    port = embedding_port or create_embedding_port(cfg, cfg.get("api_profiles") or [])
    if not _ann_enabled(cfg, port):
        return NullVectorIndex()
    # sqlite-vec optional path reserved; linear scan removes SEMANTIC_SCAN_LIMIT today.
    return LinearVectorIndex()
