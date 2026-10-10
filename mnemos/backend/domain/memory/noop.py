"""No-op memory service for MVP."""

from __future__ import annotations

from .protocol import CompressResult, MemoryScope


class NoOpMemoryService:
    """Keep the memory hooks alive while doing nothing."""

    def before_chat(
        self,
        scope: MemoryScope,
        query: str,
        session_summary: str,
        budget_tokens: int,
    ) -> str:
        return ""

    def after_turn(self, scope: MemoryScope, session_id: str, messages: list[dict]) -> None:
        return

    def on_compress(self, scope: MemoryScope, session_id: str, messages: list[dict]) -> CompressResult:
        return CompressResult(summary="", extracted_count=0)

