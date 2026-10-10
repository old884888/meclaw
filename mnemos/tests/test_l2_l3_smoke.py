"""L2/L3 aggregation smoke test (no LLM)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.knowledge.indexer import index_note
from backend.domain.knowledge.paths import ensure_knowledge_layout
from backend.domain.knowledge.store import add_source, get_note, write_note, write_raw
from backend.domain.memory.l2_aggregator import aggregate_l2, list_l2
from backend.domain.memory.l3_aggregator import aggregate_l3, list_l3


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = ensure_knowledge_layout(root)
        source = add_source(paths, source_type="text", title="t", raw_path="", status="ok")
        write_raw(paths, source["id"], "body")
        source["raw_path"] = f"knowledge/raw/{source['id']}.md"
        write_note(
            paths,
            note_id="note_a",
            title="A",
            category="测试类",
            tags=["t"],
            source_id=source["id"],
            source_url="",
            summary="s",
            key_points=["p"],
            related_terms=["X"],
        )
        write_note(
            paths,
            note_id="note_b",
            title="B",
            category="测试类",
            tags=["t"],
            source_id=source["id"],
            source_url="",
            summary="s2",
            key_points=["p2"],
            related_terms=["Y"],
        )
        for nid in ("note_a", "note_b"):
            n = get_note(paths, nid)
            if n:
                index_note(paths, n)
        l2 = aggregate_l2(root)
        assert len(l2) >= 1
        l3 = aggregate_l3(root)
        assert len(l3) == 1
        assert len(list_l2(root)) >= 1
        assert len(list_l3(root)) == 1
        print("L2/L3 smoke test OK")


if __name__ == "__main__":
    main()
