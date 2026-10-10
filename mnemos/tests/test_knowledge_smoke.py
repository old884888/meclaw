"""Smoke test for knowledge store + FTS (no LLM)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.knowledge.indexer import index_note, search_notes
from backend.domain.knowledge.paths import ensure_knowledge_layout
from backend.domain.knowledge.store import (
    add_source,
    get_note,
    read_raw_content,
    write_note,
    write_raw,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = ensure_knowledge_layout(root)
        source = add_source(
            paths,
            source_type="text",
            title="测试来源",
            raw_path="",
            status="ok",
        )
        write_raw(paths, source["id"], "# 测试\n\nMNEMOS 分层记忆测试正文。")
        source["raw_path"] = f"knowledge/raw/{source['id']}.md"
        note_id = "note_test001"
        write_note(
            paths,
            note_id=note_id,
            title="MNEMOS 测试卡片",
            category="测试",
            tags=["mnemos", "fts"],
            source_id=source["id"],
            source_url="",
            summary="这是一条测试摘要。",
            key_points=["要点一", "要点二"],
            related_terms=["Memory", "Knowledge"],
        )
        note = get_note(paths, note_id)
        assert note is not None
        index_note(paths, note)
        hits = search_notes(paths, "MNEMOS", limit=5)
        assert hits, "FTS should find MNEMOS"
        raw = read_raw_content(paths, source)
        assert "分层记忆" in raw
        print("knowledge smoke test OK")


if __name__ == "__main__":
    main()
