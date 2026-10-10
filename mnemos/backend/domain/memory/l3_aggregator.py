"""L3 knowledge profile aggregation from L2 scenarios."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ...storage.common import now_iso
from ..knowledge.paths import memory_layer_paths
from .l2_aggregator import list_l2


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


def _read_l2_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n.*?\n---\s*\n(.*)$", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


def aggregate_l3(data_root: Path) -> list[dict[str, Any]]:
    """Build knowledge profile (L3) from existing L2 blocks."""
    mem = memory_layer_paths(data_root)
    mem.l3_dir.mkdir(parents=True, exist_ok=True)
    l2_items = list_l2(data_root)
    if not l2_items:
        return []

    sections = []
    source_l2_ids = []
    for item in l2_items:
        l2_id = item.get("id") or ""
        source_l2_ids.append(l2_id)
        path = mem.l2_dir / f"{l2_id}.md"
        body = _read_l2_body(path) if path.exists() else ""
        topic = item.get("topic") or item.get("title") or l2_id
        sections.append(f"### {topic}\n\n{body[:600]}")

    profile_body = "\n\n".join(
        [
            "## 知识画像（自动聚合）",
            "",
            f"当前共 {len(l2_items)} 个 L2 主题块，覆盖 {len(source_l2_ids)} 个主题域。",
            "",
            *sections,
        ]
    )
    l3_id = "l3_knowledge_profile"
    meta = {
        "schema_version": 1,
        "id": l3_id,
        "title": "MNEMOS 知识画像",
        "profile_type": "knowledge_profile",
        "source_l2_ids": source_l2_ids,
        "layer": "L3",
        "updated_at": now_iso(),
    }
    path = mem.l3_dir / f"{l3_id}.md"
    path.write_text(_dump_frontmatter(meta, profile_body), encoding="utf-8")
    return [
        {
            "id": l3_id,
            "title": meta["title"],
            "profile_type": meta["profile_type"],
            "source_l2_ids": source_l2_ids,
            "layer": "L3",
            "path": path.name,
        }
    ]


def list_l3(data_root: Path) -> list[dict[str, Any]]:
    mem = memory_layer_paths(data_root)
    items: list[dict[str, Any]] = []
    if not mem.l3_dir.exists():
        return items
    for path in sorted(mem.l3_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = path.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        meta: dict[str, Any] = {"id": path.stem, "title": path.stem, "layer": "L3"}
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')
        items.append(
            {
                "id": meta.get("id") or path.stem,
                "title": meta.get("title") or path.stem,
                "profile_type": meta.get("profile_type") or "",
                "layer": "L3",
                "path": path.name,
            }
        )
    return items
