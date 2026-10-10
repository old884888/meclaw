"""Wiki mode: derive pages and graph from L1 notes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..knowledge.paths import knowledge_paths
from ..knowledge.store import list_notes

WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _slug(name: str) -> str:
    name = (name or "page").strip()
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", name)
    return name.strip("-") or "page"


def rebuild_wiki(data_root: Path) -> dict[str, Any]:
    kpaths = knowledge_paths(data_root)
    wiki_root = data_root / "wiki"
    pages_dir = wiki_root / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    notes = list_notes(kpaths)
    pages: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    for note in notes:
        note_id = note.get("id") or ""
        title = note.get("title") or note_id
        pages[note_id] = {
            "id": note_id,
            "title": title,
            "kind": "note",
            "category": note.get("category") or "",
        }
        body = note.get("body") or ""
        for match in WIKI_LINK_RE.finditer(body):
            target = match.group(1).strip()
            if not target:
                continue
            slug = _slug(target)
            if slug not in pages:
                pages[slug] = {"id": slug, "title": target, "kind": "concept", "category": ""}
            edges.append({"from": note_id, "to": slug, "type": "related"})

        page_path = pages_dir / f"{note_id}.md"
        page_path.write_text(
            "\n".join(
                [
                    f"# {title}",
                    "",
                    f"来源卡片：`{note_id}`",
                    "",
                    body,
                ]
            ),
            encoding="utf-8",
        )

    for page_id, page in pages.items():
        if page.get("kind") != "concept":
            continue
        page_path = pages_dir / f"{page_id}.md"
        if page_path.exists():
            continue
        incoming = [edge["from"] for edge in edges if edge.get("to") == page_id]
        refs = "\n".join(f"- `{src}`" for src in incoming[:30]) or "- （暂无引用）"
        page_path.write_text(
            "\n".join(
                [
                    f"# {page.get('title') or page_id}",
                    "",
                    "概念页（由知识卡片中的 `[[交叉引用]]` 自动生成）",
                    "",
                    "## 引用来源",
                    refs,
                ]
            ),
            encoding="utf-8",
        )

    graph = {"nodes": list(pages.values()), "edges": edges}
    (wiki_root / "graph.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    (wiki_root / "index.json").write_text(
        json.dumps({"pages": list(pages.values()), "updated_at": __import__("datetime").datetime.now().isoformat()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return graph


def load_wiki_graph(data_root: Path) -> dict[str, Any]:
    path = data_root / "wiki" / "graph.json"
    if not path.exists():
        return rebuild_wiki(data_root)
    return json.loads(path.read_text(encoding="utf-8"))


def load_wiki_pages(data_root: Path) -> list[dict[str, Any]]:
    index = data_root / "wiki" / "index.json"
    if not index.exists():
        graph = rebuild_wiki(data_root)
        return graph.get("nodes", [])
    data = json.loads(index.read_text(encoding="utf-8"))
    return data.get("pages", [])


def load_wiki_page(data_root: Path, page_id: str) -> dict[str, Any]:
    page_id = (page_id or "").strip()
    if not page_id:
        raise FileNotFoundError("empty page id")

    graph = load_wiki_graph(data_root)
    node = next((item for item in graph.get("nodes", []) if item.get("id") == page_id), None)
    if not node:
        raise FileNotFoundError(page_id)

    page_path = data_root / "wiki" / "pages" / f"{page_id}.md"
    markdown = page_path.read_text(encoding="utf-8") if page_path.exists() else ""
    outgoing = [edge for edge in graph.get("edges", []) if edge.get("from") == page_id]
    incoming = [edge for edge in graph.get("edges", []) if edge.get("to") == page_id]

    linked_ids = {edge.get("to") for edge in outgoing if edge.get("to")}
    linked_ids.update(edge.get("from") for edge in incoming if edge.get("from"))
    linked_ids.discard(page_id)
    linked_pages = [
        next((item for item in graph.get("nodes", []) if item.get("id") == linked_id), {"id": linked_id, "title": linked_id})
        for linked_id in sorted(linked_ids)
    ]

    return {
        **node,
        "markdown": markdown,
        "outgoing": outgoing,
        "incoming": incoming,
        "linked_pages": linked_pages,
    }
