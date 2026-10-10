"""Smoke test for wiki page loading."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.knowledge.indexer import index_note
from backend.domain.knowledge.paths import ensure_knowledge_layout
from backend.domain.knowledge.store import add_source, write_note, write_raw
from backend.domain.wiki.builder import load_wiki_page, rebuild_wiki


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = ensure_knowledge_layout(root)
        source = add_source(
            paths,
            source_type="text",
            title="Wiki Smoke",
            raw_path="",
            status="ok",
        )
        write_raw(paths, source["id"], "# Wiki Smoke\n\n正文。")
        source["raw_path"] = f"knowledge/raw/{source['id']}.md"
        note_id = "note_wiki001"
        write_note(
            paths,
            note_id=note_id,
            title="Wiki Smoke",
            category="测试",
            tags=["wiki"],
            source_id=source["id"],
            source_url="",
            summary="wiki smoke",
            key_points=["graph"],
            related_terms=["Graph Theory", "Knowledge Base"],
        )
        from backend.domain.knowledge.store import get_note

        note = get_note(paths, note_id)
        if note:
            index_note(paths, note)

        graph = rebuild_wiki(root)
        assert graph["nodes"], "expected wiki nodes"

        page = load_wiki_page(root, note_id)
        assert page["markdown"], "expected markdown body"
        assert page["outgoing"], "expected outgoing links"

        concept_id = next(node["id"] for node in graph["nodes"] if node.get("kind") == "concept")
        concept = load_wiki_page(root, concept_id)
        assert concept["incoming"], "expected incoming links for concept page"
        assert "引用来源" in concept["markdown"]

        missing_ok = False
        try:
            load_wiki_page(root, "missing-page-id")
        except FileNotFoundError:
            missing_ok = True
        assert missing_ok, "expected FileNotFoundError for missing page"

        print("wiki smoke test OK")


if __name__ == "__main__":
    main()
