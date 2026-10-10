"""Skill file storage with frontmatter."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from ...storage.common import now_iso
from .paths import BotSkillPaths, ensure_skill_layout

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
VALID_STATUSES = frozenset({"pending", "approved", "archived", "superseded"})


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


def _parse_meta_value(key: str, raw: str) -> Any:
    text = (raw or "").strip().strip('"')
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    return text


def read_skill_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text.strip())
    meta: dict[str, Any] = {}
    body = text.strip()
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = _parse_meta_value(k.strip(), v.strip())
        body = m.group(2).strip()
    status = str(meta.get("status") or "approved")
    return {
        "id": str(meta.get("id") or path.stem),
        "path": str(path),
        "title": str(meta.get("title") or path.stem),
        "status": status,
        "tags": meta.get("tags") or [],
        "topic_tags": str(meta.get("topic_tags") or ""),
        "content": body,
        "created_at": str(meta.get("created_at") or ""),
        "approved_at": str(meta.get("approved_at") or ""),
        "supersedes_id": str(meta.get("supersedes_id") or ""),
        "superseded_by": str(meta.get("superseded_by") or ""),
        "meta": meta,
    }


def write_skill(
    paths: BotSkillPaths,
    *,
    title: str,
    content: str,
    status: str = "approved",
    tags: list[str] | None = None,
    topic_tags: str = "",
    skill_id: str = "",
    supersedes_id: str = "",
) -> dict[str, Any]:
    sid = (skill_id or f"skill_{uuid.uuid4().hex[:8]}").strip()
    st = status if status in VALID_STATUSES else "approved"
    meta: dict[str, Any] = {
        "schema_version": 1,
        "id": sid,
        "title": (title or sid)[:120],
        "status": st,
        "tags": tags or [],
        "topic_tags": (topic_tags or "")[:80],
        "created_at": now_iso(),
        "approved_at": now_iso() if st == "approved" else "",
    }
    if supersedes_id:
        meta["supersedes_id"] = supersedes_id
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", meta["title"][:24]).strip("-") or sid
    path = paths.skills_dir / f"{sid}-{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_frontmatter(meta, content), encoding="utf-8")
    item = read_skill_file(path)
    assert item is not None
    if supersedes_id:
        prior = get_skill_by_id(paths, supersedes_id)
        if prior:
            prior_path = Path(str(prior.get("path") or ""))
            _update_skill_meta(prior_path, {"superseded_by": sid, "status": "superseded"})
    return item


def _update_skill_meta(path: Path, updates: dict[str, Any]) -> None:
    item = read_skill_file(path)
    if not item:
        return
    meta = dict(item.get("meta") or {})
    meta.update(updates)
    path.write_text(_dump_frontmatter(meta, str(item.get("content") or "")), encoding="utf-8")


def list_skills(paths: BotSkillPaths, *, status: str = "approved") -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not paths.skills_dir.exists():
        return items
    for path in sorted(paths.skills_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        item = read_skill_file(path)
        if not item:
            continue
        if status and str(item.get("status") or "") != status:
            continue
        items.append(item)
    return items


def get_skill_by_id(paths: BotSkillPaths, skill_id: str) -> dict[str, Any] | None:
    sid = (skill_id or "").strip()
    for item in list_skills(paths, status=""):
        if str(item.get("id") or "") == sid:
            return item
    return None


def archive_skill(paths: BotSkillPaths, skill_id: str) -> dict[str, Any] | None:
    item = get_skill_by_id(paths, skill_id)
    if not item:
        return None
    path = Path(str(item.get("path") or ""))
    _update_skill_meta(path, {"status": "archived"})
    return read_skill_file(path)


def create_skill_from_candidate(
    souls_root: Path,
    bot_id: str,
    *,
    title: str,
    content: str,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    paths = ensure_skill_layout(souls_root, bot_id)
    return write_skill(
        paths,
        title=title,
        content=content,
        status="approved",
        tags=tags or [],
    )
