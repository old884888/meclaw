"""L2 session summary store."""

from __future__ import annotations

from pathlib import Path

from .paths import session_summary_path


def read_session_summary(history_dir: Path, session_id: str) -> str:
    path = session_summary_path(history_dir, session_id)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def write_session_summary(history_dir: Path, session_id: str, content: str) -> Path:
    path = session_summary_path(history_dir, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def list_session_summaries(history_dir: Path, bot_id: str, sessions_index: list[dict], limit: int = 3) -> list[dict]:
    """Return recent session summaries for the same bot (cross-session recall)."""
    bot_sessions = [s for s in sessions_index if s.get("bot_id") == bot_id]
    bot_sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    hits: list[dict] = []
    for s in bot_sessions[: max(limit * 2, 6)]:
        sid = s.get("id") or ""
        summary = read_session_summary(history_dir, sid)
        if not summary:
            continue
        hits.append(
            {
                "session_id": sid,
                "title": s.get("title") or sid,
                "summary": summary[:600],
                "updated_at": s.get("updated_at") or "",
            }
        )
        if len(hits) >= limit:
            break
    return hits
