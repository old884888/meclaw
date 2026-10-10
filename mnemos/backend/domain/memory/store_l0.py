"""L0 conversation evidence store."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...storage.common import now_iso, write_json_atomic
from .paths import BotMemoryPaths, ensure_bot_memory_layout


def save_turn_evidence(
    paths: BotMemoryPaths,
    *,
    session_id: str,
    messages: list[dict],
) -> Path | None:
    if len(messages) < 2:
        return None
    last_two = messages[-2:]
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "layer": "L0",
        "kind": "conversation",
        "session_id": session_id,
        "created_at": now_iso(),
        "messages": last_two,
    }
    fname = f"{session_id}_{now_iso().replace(':', '').replace('-', '')}.json"
    path = paths.l0_dir / fname
    write_json_atomic(path, evidence, backup=False)
    return path


def list_l0_evidence(
    paths: BotMemoryPaths,
    *,
    session_id: str = "",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    import json

    if not paths.l0_dir.exists():
        return [], 0
    all_paths = sorted(paths.l0_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if session_id:
        prefix = f"{session_id}_"
        all_paths = [p for p in all_paths if p.name.startswith(prefix)]
    total = len(all_paths)
    items: list[dict[str, Any]] = []
    for path in all_paths[offset : offset + limit]:
        try:
            ev = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        msgs = ev.get("messages") or []
        parts: list[str] = []
        for m in msgs:
            role = m.get("role", "")
            content = str(m.get("content") or "")[:120]
            if content:
                parts.append(f"{role}: {content}")
        items.append(
            {
                "id": path.stem,
                "session_id": ev.get("session_id") or "",
                "created_at": ev.get("created_at") or "",
                "message_count": len(msgs),
                "preview": " / ".join(parts)[:400],
            }
        )
    return items, total


def list_recent_evidence(paths: BotMemoryPaths, session_id: str, limit: int = 3) -> list[dict]:
    items: list[dict] = []
    pattern = f"{session_id}_*.json"
    for path in sorted(paths.l0_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            import json

            items.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            continue
        if len(items) >= limit:
            break
    return items
