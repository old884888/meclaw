"""Layered memory service backed by knowledge FTS + L0 conversation evidence.

Deprecated for personal chat: use ``memory_brain.MemoryBrain`` when ``multi_brain_enabled``.
This module remains for knowledge-ingest workflows only.
"""

from __future__ import annotations

from pathlib import Path

from ..knowledge.hybrid import search_notes_hybrid
from ...storage.common import now_iso, write_json_atomic
from ..knowledge.indexer import search_notes
from ..knowledge.paths import ensure_knowledge_layout, ensure_memory_layout
from ..knowledge.store import get_note
from .l2_aggregator import search_l2
from .protocol import CompressResult, MemoryScope


class LayeredMemoryService:
    """TencentDB-inspired lightweight memory: L0 evidence + L1 note retrieval."""

    def __init__(self, data_root: Path, config_getter) -> None:
        self.data_root = data_root
        self.config_getter = config_getter
        self.knowledge_paths = ensure_knowledge_layout(data_root)
        self.memory_paths = ensure_memory_layout(data_root)

    def _cfg(self) -> dict:
        return self.config_getter() or {}

    def before_chat(
        self,
        scope: MemoryScope,
        query: str,
        session_summary: str,
        budget_tokens: int,
    ) -> str:
        cfg = self._cfg()
        if not cfg.get("memory_enabled") or not cfg.get("memory_retrieval_enabled"):
            return ""
        mode = (cfg.get("memory_retrieval_strategy") or "hybrid").strip().lower()
        if mode == "fts":
            hits = search_notes(self.knowledge_paths, query, limit=5)
        else:
            hits = search_notes_hybrid(self.knowledge_paths, query, limit=5)
        l2_hits = search_l2(self.data_root, query, limit=2)
        if not hits and not l2_hits:
            return ""
        lines = ["[MNEMOS 相关知识]"]
        budget = max(200, int(budget_tokens or 1200))
        used = 0
        for l2 in l2_hits:
            block = f"- [L2 主题] {l2.get('title')} ({l2.get('topic')})\n  {l2.get('snippet', '')[:300]}"
            est = len(block) // 2
            if used + est > budget:
                break
            lines.append(block)
            used += est
        for hit in hits:
            note = get_note(self.knowledge_paths, hit["id"])
            if not note:
                continue
            block = (
                f"- {note.get('title')} ({note.get('category')})\n"
                f"  source_id: {note.get('source_id')}\n"
                f"  { (note.get('body') or '')[:400] }"
            )
            est = len(block) // 2
            if used + est > budget:
                break
            lines.append(block)
            used += est
        if len(lines) <= 1:
            return ""
        return "\n".join(lines)

    def after_turn(self, scope: MemoryScope, session_id: str, messages: list[dict]) -> None:
        cfg = self._cfg()
        if not cfg.get("memory_enabled") or not cfg.get("memory_write_enabled"):
            return
        if len(messages) < 2:
            return
        last_two = messages[-2:]
        evidence = {
            "schema_version": 1,
            "layer": "L0",
            "kind": "conversation",
            "scope": {"kind": scope.kind, "scope_id": scope.scope_id},
            "session_id": session_id,
            "created_at": now_iso(),
            "messages": last_two,
        }
        fname = f"{session_id}_{now_iso().replace(':', '').replace('-', '')}.json"
        path = self.memory_paths.l0_dir / fname
        write_json_atomic(path, evidence, backup=False)

    def on_compress(self, scope: MemoryScope, session_id: str, messages: list[dict]) -> CompressResult:
        return CompressResult(summary="", extracted_count=0)
