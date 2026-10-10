"""Vector index protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..embedding.port import EmbeddingPort
from ..paths import BotMemoryPaths


@runtime_checkable
class VectorIndex(Protocol):
    @property
    def available(self) -> bool:
        """True when vector recall can run."""

    def query(
        self,
        paths: BotMemoryPaths,
        query: str,
        *,
        limit: int,
        embedding_port: EmbeddingPort,
    ) -> list[dict[str, Any]]:
        """Return semantic hits sorted by relevance."""


class NullVectorIndex:
    @property
    def available(self) -> bool:
        return False

    def query(
        self,
        paths: BotMemoryPaths,
        query: str,
        *,
        limit: int,
        embedding_port: EmbeddingPort,
    ) -> list[dict[str, Any]]:
        return []
