"""Embedding port protocol and null implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingPort(Protocol):
    @property
    def available(self) -> bool:
        """True when real embeddings can be produced."""

    @property
    def model_identity(self) -> str:
        """Stable id for cached vectors, e.g. local:model:384."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one normalized vector per non-empty input text."""


class NullEmbedding:
    """Disabled / unavailable embedding backend."""

    @property
    def available(self) -> bool:
        return False

    @property
    def model_identity(self) -> str:
        return ""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return []
