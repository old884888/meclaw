"""File-backed knowledge store (L0 raw + L1 notes)."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from ...storage.common import now_iso, read_json, write_json_atomic

from .paths import KnowledgePaths, ensure_knowledge_layout

NOTE_SCHEMA_VERSION = 1
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = FRONTMATTER_RE.match(text.strip())
    if not m:
        return {}, text.strip()
    meta: dict[str, Any] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            meta[key] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()] if inner else []
        elif val.startswith('"') and val.endswith('"'):
            meta[key] = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            meta[key] = val[1:-1]
        else:
            meta[key] = val
    return meta, m.group(2).strip()


def _dump_frontmatter(meta: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for key, val in meta.items():
        if isinstance(val, list):
            items = ", ".join(json.dumps(x, ensure_ascii=False) for x in val)
            lines.append(f"{key}: [{items}]")
        elif isinstance(val, (int, float)):
            lines.append(f"{key}: {val}")
        else:
            lines.append(f'{key}: "{str(val).replace(chr(34), chr(39))}"')
    lines.append("---")
    lines.append("")
    lines.append(body.strip())
    lines.append("")
    return "\n".join(lines)


def load_sources(paths: KnowledgePaths) -> list[dict]:
    data = read_json(paths.sources_file, {"sources": []})
    return list(data.get("sources") or [])


def save_sources(paths: KnowledgePaths, sources: list[dict]) -> None:
    write_json_atomic(paths.sources_file, {"sources": sources}, backup=False)


def add_source(
    paths: KnowledgePaths,
    *,
    source_type: str,
    title: str,
    raw_path: str,
    url: str = "",
    status: str = "ok",
    error: str = "",
) -> dict:
    source = {
        "id": new_id("src"),
        "type": source_type,
        "title": title or "未命名来源",
        "url": url,
        "raw_path": raw_path,
        "status": status,
        "error": error,
        "created_at": now_iso(),
    }
    sources = load_sources(paths)
    sources.append(source)
    save_sources(paths, sources)
    return source


def write_raw(paths: KnowledgePaths, source_id: str, content: str, ext: str = "md") -> Path:
    path = paths.raw_dir / f"{source_id}.{ext}"
    path.write_text(content, encoding="utf-8")
    return path


def write_note(
    paths: KnowledgePaths,
    *,
    note_id: str,
    title: str,
    category: str,
    tags: list[str],
    source_id: str,
    source_url: str,
    summary: str,
    key_points: list[str],
    related_terms: list[str],
) -> Path:
    related_block = ""
    if related_terms:
        links = " ".join(f"[[{t}]]" for t in related_terms[:12])
        related_block = f"## 相关\n\n{links}\n"
    points_block = "\n".join(f"- {p}" for p in key_points if p.strip())
    body = f"## 摘要\n\n{summary.strip()}\n\n## 要点\n\n{points_block}\n\n{related_block}".strip() + "\n"
    meta = {
        "schema_version": NOTE_SCHEMA_VERSION,
        "id": note_id,
        "title": title,
        "category": category or "未分类",
        "tags": tags or [],
        "source_id": source_id,
        "source_url": source_url or "",
        "layer": "L1",
        "created_at": now_iso(),
    }
    path = paths.notes_dir / f"{note_id}.md"
    path.write_text(_dump_frontmatter(meta, body), encoding="utf-8")
    return path


def read_note_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    note_id = meta.get("id") or path.stem
    return {
        "id": note_id,
        "path": str(path),
        "meta": meta,
        "body": body,
        "title": meta.get("title") or path.stem,
        "category": meta.get("category") or "未分类",
        "tags": meta.get("tags") or [],
        "source_id": meta.get("source_id") or "",
        "source_url": meta.get("source_url") or "",
        "layer": meta.get("layer") or "L1",
        "created_at": meta.get("created_at") or "",
    }


def list_notes(paths: KnowledgePaths) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    if not paths.notes_dir.exists():
        return notes
    for path in sorted(paths.notes_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        item = read_note_file(path)
        if item:
            notes.append(item)
    return notes


def get_note(paths: KnowledgePaths, note_id: str) -> dict[str, Any] | None:
    direct = paths.notes_dir / f"{note_id}.md"
    if direct.exists():
        return read_note_file(direct)
    for path in paths.notes_dir.glob("*.md"):
        item = read_note_file(path)
        if item and item.get("id") == note_id:
            return item
    return None


def get_source(paths: KnowledgePaths, source_id: str) -> dict | None:
    for src in load_sources(paths):
        if src.get("id") == source_id:
            return src
    return None


def read_raw_content(paths: KnowledgePaths, source: dict) -> str:
    rel = source.get("raw_path") or ""
    if not rel:
        return ""
    path = paths.root.parent / rel if not Path(rel).is_absolute() else Path(rel)
    if not path.exists():
        alt = paths.raw_dir / f"{source.get('id', '')}.md"
        if alt.exists():
            path = alt
        else:
            return ""
    return path.read_text(encoding="utf-8")


def init_store(data_root: Path) -> KnowledgePaths:
    return ensure_knowledge_layout(data_root)
