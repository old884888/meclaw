"""L2 scenario aggregation from L1 knowledge notes."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from ...storage.common import now_iso
from ..knowledge.paths import knowledge_paths, memory_layer_paths
from ..knowledge.store import list_notes


def _slug(text: str) -> str:
    text = (text or "topic").strip().lower()
    text = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "topic"


def _dump_frontmatter(meta: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for key, val in meta.items():
        if isinstance(val, list):
            items = ", ".join(json.dumps(x, ensure_ascii=False) for x in val)
            lines.append(f"{key}: [{items}]")
        else:
            lines.append(f'{key}: "{str(val).replace(chr(34), chr(39))}"')
    lines.extend(["---", "", body.strip(), ""])
    return "\n".join(lines)


def aggregate_l2(data_root: Path) -> list[dict[str, Any]]:
    """Group L1 notes by category and write L2 scenario files."""
    kpaths = knowledge_paths(data_root)
    notes = list_notes(kpaths)
    groups: dict[str, list[dict]] = defaultdict(list)
    for note in notes:
        cat = (note.get("category") or "未分类").strip() or "未分类"
        groups[cat].append(note)

    mem = memory_layer_paths(data_root)
    mem.l2_dir.mkdir(parents=True, exist_ok=True)
    created: list[dict[str, Any]] = []

    for category, items in groups.items():
        if not items:
            continue
        l2_id = f"l2_{_slug(category)}"
        summaries = []
        for n in items:
            body = (n.get("body") or "").strip()
            summary_line = body.split("\n\n")[0].replace("## 摘要", "").strip() if body else n.get("title", "")
            summaries.append(f"- **{n.get('title', n.get('id'))}** ({n.get('id')}): {summary_line[:120]}")
        body = "\n".join(
            [
                f"## 主题：{category}",
                "",
                f"本主题聚合 {len(items)} 条 L1 知识卡片。",
                "",
                "## 包含条目",
                "",
                *summaries,
            ]
        )
        meta = {
            "schema_version": 1,
            "id": l2_id,
            "title": f"{category} 主题块",
            "topic": category,
            "source_l1_ids": [n.get("id") for n in items if n.get("id")],
            "layer": "L2",
            "updated_at": now_iso(),
        }
        path = mem.l2_dir / f"{l2_id}.md"
        path.write_text(_dump_frontmatter(meta, body), encoding="utf-8")
        created.append(
            {
                "id": l2_id,
                "title": meta["title"],
                "topic": category,
                "source_l1_ids": meta["source_l1_ids"],
                "layer": "L2",
                "path": str(path.name),
            }
        )
    return created


def list_l2(data_root: Path) -> list[dict[str, Any]]:
    mem = memory_layer_paths(data_root)
    items: list[dict[str, Any]] = []
    if not mem.l2_dir.exists():
        return items
    for path in sorted(mem.l2_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = path.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        meta: dict[str, Any] = {"id": path.stem, "title": path.stem, "layer": "L2"}
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')
        items.append(
            {
                "id": meta.get("id") or path.stem,
                "title": meta.get("title") or path.stem,
                "topic": meta.get("topic") or "",
                "layer": "L2",
                "path": path.name,
            }
        )
    return items


def _read_l2_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n.*?\n---\s*\n(.*)$", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


def search_l2(data_root: Path, query: str, limit: int = 3) -> list[dict[str, Any]]:
    q = (query or "").strip().lower()
    if not q:
        return []
    mem = memory_layer_paths(data_root)
    hits: list[dict[str, Any]] = []
    for item in list_l2(data_root):
        path = mem.l2_dir / f"{item.get('id', '')}.md"
        body = _read_l2_body(path).lower() if path.exists() else ""
        topic = (item.get("topic") or item.get("title") or "").lower()
        if q in topic or q in body or any(tok in topic or tok in body for tok in q.split() if len(tok) > 1):
            snippet = body[:200] if body else topic
            hits.append({**item, "snippet": snippet})
        if len(hits) >= limit:
            break
    return hits
