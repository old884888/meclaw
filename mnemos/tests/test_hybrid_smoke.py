"""Hybrid retrieval smoke test (FTS + semantic + RRF)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.knowledge.hybrid import search_notes_hybrid
from backend.domain.knowledge.indexer import index_note
from backend.domain.knowledge.paths import ensure_knowledge_layout
from backend.domain.knowledge.store import add_source, get_note, write_note, write_raw


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = ensure_knowledge_layout(root)
        source = add_source(paths, source_type="text", title="s", raw_path="", status="ok")
        write_raw(paths, source["id"], "raw")
        source["raw_path"] = f"knowledge/raw/{source['id']}.md"

        write_note(
            paths,
            note_id="note_python",
            title="Python 检索",
            category="技术",
            tags=["python", "fts"],
            source_id=source["id"],
            source_url="",
            summary="讨论 Python 检索。",
            key_points=["关键词检索", "向量检索"],
            related_terms=["RRF"],
        )
        write_note(
            paths,
            note_id="note_cook",
            title="做饭笔记",
            category="生活",
            tags=["cook"],
            source_id=source["id"],
            source_url="",
            summary="烹饪记录。",
            key_points=["火候", "调味"],
            related_terms=["菜谱"],
        )
        for nid in ("note_python", "note_cook"):
            n = get_note(paths, nid)
            if n:
                index_note(paths, n)

        hits = search_notes_hybrid(paths, "python 检索", limit=5)
        assert hits, "hybrid should return results"
        assert any(h.get("id") == "note_python" for h in hits), hits
        assert "hybrid_score" in hits[0], hits[0]
        print("hybrid smoke test OK")


if __name__ == "__main__":
    main()
