"""Knowledge browse, search, ask, trace."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...adapters import providers
from .hybrid import search_notes_hybrid
from .indexer import rebuild_index, search_notes
from .paths import ensure_knowledge_layout
from .store import get_note, get_source, list_notes, read_raw_content


class KnowledgeService:
    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root
        self.paths = ensure_knowledge_layout(data_root)

    def list_notes(
        self,
        *,
        query: str = "",
        category: str = "",
        tag: str = "",
        strategy: str = "hybrid",
    ) -> list[dict[str, Any]]:
        notes = list_notes(self.paths)
        if category:
            notes = [n for n in notes if (n.get("category") or "") == category]
        if tag:
            notes = [n for n in notes if tag in (n.get("tags") or [])]
        if query.strip():
            hit_items = self.search(query, limit=50, strategy=strategy)
            hits = {h["id"]: h for h in hit_items}
            notes = [n for n in notes if n.get("id") in hits]
            for n in notes:
                n["snippet"] = hits.get(n["id"], {}).get("snippet", "")
        else:
            for n in notes:
                n.pop("path", None)
                n.pop("meta", None)
        return notes

    def get_note(self, note_id: str) -> dict[str, Any] | None:
        note = get_note(self.paths, note_id)
        if not note:
            return None
        return note

    def search(self, query: str, limit: int = 8, strategy: str = "hybrid") -> list[dict[str, Any]]:
        if not self.paths.index_db.exists() and list_notes(self.paths):
            rebuild_index(self.paths)
        mode = (strategy or "hybrid").strip().lower()
        if mode == "fts":
            return search_notes(self.paths, query, limit=limit)
        return search_notes_hybrid(self.paths, query, limit=limit)

    def trace(self, note_id: str) -> dict[str, Any]:
        note = get_note(self.paths, note_id)
        if not note:
            raise ValueError("知识卡片不存在")
        source_id = note.get("source_id") or ""
        source = get_source(self.paths, source_id) if source_id else None
        raw = read_raw_content(self.paths, source) if source else ""
        return {"note": note, "source": source, "raw": raw}

    def ask(self, profile: dict, question: str, limit: int = 5, strategy: str = "hybrid") -> dict[str, Any]:
        question = (question or "").strip()
        if not question:
            raise ValueError("问题不能为空")
        hits = self.search(question, limit=limit, strategy=strategy)
        if not hits:
            return {"answer": "知识库中暂无相关内容。你可以先导入资料。", "sources": []}

        context_blocks = []
        sources = []
        for hit in hits:
            note = get_note(self.paths, hit["id"])
            if not note:
                continue
            sources.append(
                {
                    "id": note.get("id"),
                    "title": note.get("title"),
                    "source_url": note.get("source_url") or "",
                    "source_id": note.get("source_id") or "",
                }
            )
            context_blocks.append(
                f"[{note.get('title')}]\n分类: {note.get('category')}\n{note.get('body', '')[:1200]}"
            )
        system = (
            "你是 MNEMOS 知识助手。请基于提供的知识卡片回答用户问题。"
            "如果资料不足，请明确说明。回答使用中文，简洁准确。"
        )
        user = "知识卡片：\n\n" + "\n\n---\n\n".join(context_blocks) + f"\n\n用户问题：{question}"
        answer = providers.chat_once(
            profile,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=1200,
            timeout=60,
        )
        return {"answer": answer.strip(), "sources": sources}
