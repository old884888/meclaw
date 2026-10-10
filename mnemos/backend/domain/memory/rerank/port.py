"""Reranker protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Reranker(Protocol):
    @property
    def available(self) -> bool:
        """True when reranking can run."""

    def rerank(self, query: str, candidates: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
        """Return top_k candidates ordered by relevance."""


class NullReranker:
    @property
    def available(self) -> bool:
        return False

    def rerank(self, query: str, candidates: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
        return candidates[:top_k]
