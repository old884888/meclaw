"""Memory service abstraction for MeClaw 2.0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class MemoryScope:
    """Scope placeholder for future memory implementations."""

    kind: str
    scope_id: str


@dataclass
class CompressResult:
    """Placeholder output for future compression + extraction."""

    summary: str = ""
    extracted_count: int = 0


class MemoryService(Protocol):
    """Interface intentionally stable across MVP and future phases."""

    def before_chat(
        self,
        scope: MemoryScope,
        query: str,
        session_summary: str,
        budget_tokens: int,
    ) -> str:
        """Return extra system block for memory retrieval."""

    def after_turn(self, scope: MemoryScope, session_id: str, messages: list[dict]) -> None:
        """Capture a completed turn asynchronously."""

    def on_compress(self, scope: MemoryScope, session_id: str, messages: list[dict]) -> CompressResult:
        """Run compression/extraction pipeline."""

