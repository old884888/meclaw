"""Session and message persistence with rolling JSON backups."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from .common import now_iso, read_json, write_json_atomic


DEFAULT_INDEX = {"sessions": []}


def new_session_id() -> str:
    return f"s_{uuid.uuid4().hex[:12]}"


def normalize_title(text: str) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return "新对话"
    return clean[:30]


def load_sessions_index(path: Path) -> list[dict]:
    data = read_json(path, DEFAULT_INDEX)
    sessions = data.get("sessions") or []
    for s in sessions:
        s.setdefault("id", "")
        s.setdefault("bot_id", "")
        s.setdefault("title", "新对话")
        s.setdefault("created_at", now_iso())
        s.setdefault("updated_at", s["created_at"])
        s.setdefault("message_count", 0)
    return sessions


def save_sessions_index(path: Path, sessions: list[dict], backup: bool = False, backup_generations: int = 3) -> None:
    generations = backup_generations if backup_generations > 0 else (1 if backup else 0)
    write_json_atomic(path, {"sessions": sessions}, backup_generations=generations)


def session_file(history_dir: Path, session_id: str) -> Path:
    return history_dir / f"{session_id}.json"


def load_messages(history_dir: Path, session_id: str) -> list[dict]:
    return read_json(session_file(history_dir, session_id), [])


def save_messages(
    history_dir: Path,
    session_id: str,
    messages: list[dict],
    *,
    backup_generations: int = 3,
) -> None:
    write_json_atomic(
        session_file(history_dir, session_id),
        messages,
        backup_generations=backup_generations,
    )


def create_session(index: list[dict], bot_id: str, title: str = "新对话") -> dict:
    now = now_iso()
    item = {
        "id": new_session_id(),
        "bot_id": bot_id,
        "title": normalize_title(title),
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }
    index.insert(0, item)
    return item


def update_session_meta(index: list[dict], session_id: str, *, title: str | None = None, message_count: int | None = None) -> dict | None:
    now = now_iso()
    for s in index:
        if s.get("id") != session_id:
            continue
        if title is not None:
            s["title"] = normalize_title(title)
        if message_count is not None:
            s["message_count"] = max(0, int(message_count))
        s["updated_at"] = now
        return s
    return None


def delete_session(index: list[dict], session_id: str) -> list[dict]:
    return [s for s in index if s.get("id") != session_id]


def make_message(
    role: str,
    content: str,
    *,
    status: str | None = None,
    speaker_bot_id: str | None = None,
    reasoning: str | None = None,
) -> dict:
    msg = {
        "id": f"m_{uuid.uuid4().hex[:12]}",
        "role": role,
        "content": content,
        "created_at": now_iso(),
    }
    if status is not None:
        msg["status"] = status
    if speaker_bot_id:
        msg["speaker_bot_id"] = speaker_bot_id
    if reasoning:
        msg["reasoning"] = reasoning
    return msg

