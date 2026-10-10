"""L1 atomic memory store."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from ...storage.common import now_iso
from .memory_scoring import default_importance
from .paths import BotMemoryPaths
from .topic_metadata import assign_topic_key, enrich_atom, extract_reason, infer_polarity, infer_topic_key, next_atom_seq

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
VALID_TYPES = frozenset({"fact", "preference", "constraint", "todo"})
VALID_POLARITIES = frozenset({"positive", "negative", "switch"})


def new_atom_id() -> str:
    return f"atom_{uuid.uuid4().hex[:8]}"


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
    lines.extend(["---", "", body.strip(), ""])
    return "\n".join(lines)


def _parse_meta_value(key: str, raw: str) -> str | int | float | bool:
    text = (raw or "").strip().strip('"')
    if key in {"seq", "schema_version", "hit_count"}:
        try:
            return int(float(text))
        except ValueError:
            return 0
    if key in {"confidence", "importance"}:
        try:
            return float(text)
        except ValueError:
            return 0.0
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    return text


def _norm_content(text: str) -> str:
    return " ".join((text or "").split()).lower()


def _atom_dict_from_file(path: Path, meta: dict[str, Any], body: str) -> dict[str, Any]:
    return enrich_atom(
        {
            "id": meta.get("id") or path.stem,
            "path": str(path),
            "meta": meta,
            "type": meta.get("type") or "fact",
            "content": body,
            "session_id": meta.get("session_id") or "",
            "created_at": meta.get("created_at") or "",
            "topic_key": meta.get("topic_key") or "",
            "polarity": meta.get("polarity") or "",
            "seq": meta.get("seq"),
            "reason": meta.get("reason") or "",
            "importance": meta.get("importance"),
            "hit_count": meta.get("hit_count"),
            "subject": meta.get("subject") or "",
            "predicate": meta.get("predicate") or "",
            "object": meta.get("object") or "",
            "supersedes_id": meta.get("supersedes_id") or "",
            "superseded_by": meta.get("superseded_by") or "",
        }
    )


def update_atom_meta(path: Path, updates: dict[str, Any]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text.strip())
    if not m:
        return None
    meta: dict[str, Any] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = _parse_meta_value(k.strip(), v.strip())
    body = m.group(2).strip()
    for key, val in updates.items():
        if val is None or val == "":
            meta.pop(key, None)
        else:
            meta[key] = val
    path.write_text(_dump_frontmatter(meta, body), encoding="utf-8")
    return _atom_dict_from_file(path, meta, body)


def _is_archived_meta(meta: dict[str, Any]) -> bool:
    return str(meta.get("is_archived", "false")).lower() == "true"


def mark_atom_archived(
    paths: BotMemoryPaths,
    atom_id: str,
    *,
    reason: str = "",
    merged_into: str = "",
) -> None:
    atom = get_atom_by_id(paths, atom_id, include_archived=True)
    if not atom:
        return
    path = Path(str(atom.get("path") or ""))
    updates: dict[str, Any] = {"is_archived": True}
    if reason:
        updates["archive_reason"] = reason[:200]
    if merged_into:
        updates["merged_into"] = merged_into
    update_atom_meta(path, updates)


def increment_hit_count(paths: BotMemoryPaths, atom_id: str) -> None:
    atom = get_atom_by_id(paths, atom_id)
    if not atom:
        return
    path = Path(str(atom.get("path") or ""))
    meta = atom.get("meta") or {}
    count = int(meta.get("hit_count") or atom.get("hit_count") or 0) + 1
    update_atom_meta(path, {"hit_count": count})


def find_current_topic_atom(
    paths: BotMemoryPaths,
    topic_key: str,
    *,
    exclude_id: str = "",
) -> dict[str, Any] | None:
    key = (topic_key or "").strip()
    if not key:
        return None
    exclude = (exclude_id or "").strip()
    candidates: list[dict[str, Any]] = []
    for atom in list_atoms(paths):
        enriched = enrich_atom(dict(atom))
        if str(enriched.get("topic_key") or "") != key:
            continue
        if str(enriched.get("superseded_by") or "").strip():
            continue
        if exclude and str(enriched.get("id") or "") == exclude:
            continue
        candidates.append(enriched)
    if not candidates:
        return None
    candidates.sort(key=lambda a: int(a.get("seq") or 0))
    return candidates[-1]


def mark_superseded(paths: BotMemoryPaths, prior_id: str, new_id: str) -> None:
    prior = get_atom_by_id(paths, prior_id)
    if not prior:
        return
    path = Path(str(prior.get("path") or ""))
    update_atom_meta(path, {"superseded_by": new_id})


def apply_supersedes_link(paths: BotMemoryPaths, new_id: str, prior_id: str) -> None:
    prior = (prior_id or "").strip()
    new = (new_id or "").strip()
    if not prior or not new or prior == new:
        return
    if not get_atom_by_id(paths, prior):
        return
    new_atom = get_atom_by_id(paths, new)
    if not new_atom:
        return
    new_path = Path(str(new_atom.get("path") or ""))
    update_atom_meta(new_path, {"supersedes_id": prior})
    mark_superseded(paths, prior, new)


def link_supersede_on_write(
    paths: BotMemoryPaths,
    *,
    atom_id: str,
    topic_key: str,
    polarity: str,
) -> None:
    if polarity != "switch":
        return
    topic = (topic_key or "").strip()
    if not topic:
        return
    prior = find_current_topic_atom(paths, topic, exclude_id=atom_id)
    if not prior or str(prior.get("id") or "") == atom_id:
        return
    apply_supersedes_link(paths, atom_id, str(prior.get("id") or ""))


def resolve_supersedes_hint(
    paths: BotMemoryPaths,
    hint: Any,
    *,
    topic_key: str = "",
    embedding_port=None,
    scan_limit: int = 40,
) -> str:
    """Resolve LLM supersedes_hint to an existing atom id."""
    if not hint:
        return ""
    content_hint = ""
    if isinstance(hint, dict):
        atom_id = str(hint.get("supersedes_id") or hint.get("id") or "").strip()
        if atom_id and get_atom_by_id(paths, atom_id):
            return atom_id
        content_hint = str(
            hint.get("supersedes_content") or hint.get("content") or hint.get("supersedes_hint") or ""
        ).strip()
    else:
        text = str(hint).strip()
        if text.startswith("atom_") and get_atom_by_id(paths, text):
            return text
        content_hint = text

    if not content_hint:
        return ""

    topic = (topic_key or "").strip()
    target = _norm_content(content_hint)
    for atom in list_atoms(paths)[:scan_limit]:
        if str(atom.get("superseded_by") or "").strip():
            continue
        if topic and str(atom.get("topic_key") or "") != topic:
            continue
        body = str(atom.get("content") or "")
        if target in _norm_content(body) or _norm_content(body) in target:
            return str(atom.get("id") or "")

    if embedding_port is None or not getattr(embedding_port, "available", False):
        return ""
    try:
        new_vec = embedding_port.embed([content_hint])[0]
    except Exception:  # noqa: BLE001
        return ""
    if not new_vec:
        return ""
    best_id = ""
    best_score = 0.0
    for atom in list_atoms(paths)[:scan_limit]:
        if str(atom.get("superseded_by") or "").strip():
            continue
        if topic and str(atom.get("topic_key") or "") != topic:
            continue
        body = str(atom.get("content") or "").strip()
        if not body:
            continue
        try:
            vec = embedding_port.embed([body])[0]
        except Exception:  # noqa: BLE001
            continue
        if not vec or len(vec) != len(new_vec):
            continue
        score = sum(x * y for x, y in zip(new_vec, vec))
        if score > best_score:
            best_score = score
            best_id = str(atom.get("id") or "")
    if best_score >= 0.82 and best_id:
        return best_id
    return ""


def write_atom(
    paths: BotMemoryPaths,
    *,
    atom_type: str,
    content: str,
    session_id: str = "",
    source_turn_id: str = "",
    confidence: float = 0.8,
    tags: list[str] | None = None,
    topic_key: str = "",
    polarity: str = "",
    seq: int | None = None,
    reason: str = "",
    importance: float | None = None,
    subject: str = "",
    predicate: str = "",
    object_: str = "",
    supersedes_id: str = "",
    embedding_port=None,
    topic_cluster_cfg: dict | None = None,
    resolved_topic: str = "",
) -> Path:
    atom_type = atom_type if atom_type in VALID_TYPES else "fact"
    body = content.strip()
    if (resolved_topic or "").strip():
        topic = str(resolved_topic).strip()
    else:
        topic = assign_topic_key(
            body,
            explicit_key=topic_key,
            paths=paths,
            embedding_port=embedding_port,
            cfg=topic_cluster_cfg or {},
        )
    pol = polarity if polarity in VALID_POLARITIES else infer_polarity(body)
    reason_text = (reason or extract_reason(body)).strip()
    atom_seq = int(seq) if seq is not None else next_atom_seq(paths)
    atom_id = new_atom_id()
    imp = float(importance) if importance is not None else default_importance(atom_type)
    meta: dict[str, Any] = {
        "schema_version": 2,
        "id": atom_id,
        "type": atom_type,
        "layer": "L1",
        "session_id": session_id,
        "source_turn_id": source_turn_id,
        "confidence": confidence,
        "tags": tags or [],
        "is_deleted": False,
        "created_at": now_iso(),
        "topic_key": topic,
        "polarity": pol,
        "seq": atom_seq,
        "importance": round(max(0.0, min(1.0, imp)), 3),
        "hit_count": 0,
    }
    if reason_text:
        meta["reason"] = reason_text
    if (subject or "").strip():
        meta["subject"] = str(subject).strip()
    if (predicate or "").strip():
        meta["predicate"] = str(predicate).strip()
    if (object_ or "").strip():
        meta["object"] = str(object_).strip()
    prior_id = str(supersedes_id or "").strip()
    if prior_id:
        meta["supersedes_id"] = prior_id
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", body[:24]).strip("-") or atom_id
    path = paths.l1_dir / f"{now_iso()[:10]}-{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_frontmatter(meta, body), encoding="utf-8")
    if prior_id:
        apply_supersedes_link(paths, atom_id, prior_id)
    else:
        link_supersede_on_write(paths, atom_id=atom_id, topic_key=topic, polarity=pol)
    return path


def read_atom_file(path: Path, *, include_archived: bool = False) -> dict[str, Any] | None:
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
    if str(meta.get("is_deleted", "false")).lower() == "true":
        return None
    if not include_archived and _is_archived_meta(meta):
        return None
    return _atom_dict_from_file(path, meta, body)


def get_atom_by_id(paths: BotMemoryPaths, atom_id: str, *, include_archived: bool = False) -> dict | None:
    for path in sorted(paths.l1_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True) if paths.l1_dir.exists() else []:
        item = read_atom_file(path, include_archived=include_archived)
        if item and item.get("id") == atom_id:
            return item
    return None


def list_atoms(paths: BotMemoryPaths, *, include_archived: bool = False) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not paths.l1_dir.exists():
        return items
    for path in sorted(paths.l1_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        item = read_atom_file(path, include_archived=include_archived)
        if item:
            items.append(item)
    return items
