"""Learner brain: offline signal collection and candidate queue."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ...storage.common import now_iso, write_json_atomic


class LearnerBrain:
    def __init__(self, data_root: Path) -> None:
        self.signals_dir = data_root / "learner" / "signals"
        self.candidates_dir = data_root / "learner" / "candidates"
        self.signals_dir.mkdir(parents=True, exist_ok=True)
        self.candidates_dir.mkdir(parents=True, exist_ok=True)

    def collect_signal(
        self,
        *,
        session_id: str,
        bot_id: str,
        user_input: str,
        assistant_output: str,
        usage: dict[str, Any] | None = None,
    ) -> None:
        record = {
            "session_id": session_id,
            "bot_id": bot_id,
            "user_input": (user_input or "")[:2000],
            "assistant_output": (assistant_output or "")[:2000],
            "usage": usage or {},
            "created_at": now_iso(),
            "processed": False,
        }
        path = self.signals_dir / f"{session_id}_{now_iso().replace(':', '').replace('-', '')}.json"
        write_json_atomic(path, record, backup=False)

    def list_pending_signals(self, limit: int = 50) -> list[dict]:
        items: list[dict] = []
        for path in sorted(self.signals_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                items.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
            if len(items) >= limit:
                break
        return items

    def save_candidate(
        self,
        *,
        bot_id: str,
        candidate_type: str,
        content: str,
        reason: str = "",
        status: str = "pending",
        source_session: str = "",
        trigger: str = "",
    ) -> dict[str, Any]:
        candidate_id = f"cand_{uuid.uuid4().hex[:8]}"
        record: dict[str, Any] = {
            "id": candidate_id,
            "bot_id": bot_id,
            "type": candidate_type,
            "content": content,
            "reason": reason,
            "status": status,
            "source_session": source_session,
            "trigger": trigger,
            "created_at": now_iso(),
        }
        path = self.candidates_dir / f"{candidate_id}.json"
        write_json_atomic(path, record, backup=False)
        record["path"] = path.name
        return record

    def list_candidates(self, bot_id: str | None = None, status: str = "pending") -> list[dict]:
        items: list[dict] = []
        for path in sorted(self.candidates_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                rec = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if bot_id and rec.get("bot_id") != bot_id:
                continue
            if status and rec.get("status") != status:
                continue
            rec.setdefault("id", path.stem)
            rec["path"] = path.name
            items.append(rec)
        return items

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        cid = (candidate_id or "").strip()
        if not cid:
            return None
        path = self.candidates_dir / f"{cid}.json"
        if not path.exists():
            for p in self.candidates_dir.glob("*.json"):
                try:
                    rec = json.loads(p.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                if str(rec.get("id") or "") == cid:
                    rec["path"] = p.name
                    return rec
            return None
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        rec.setdefault("id", path.stem)
        rec["path"] = path.name
        return rec

    def update_candidate_status(self, candidate_id: str, status: str, *, note: str = "") -> dict[str, Any] | None:
        rec = self.get_candidate(candidate_id)
        if not rec:
            return None
        path = self.candidates_dir / str(rec.get("path") or f"{candidate_id}.json")
        rec["status"] = status
        rec["updated_at"] = now_iso()
        if note:
            rec["review_note"] = note[:500]
        write_json_atomic(path, rec, backup=False)
        return rec

    def pending_count(self, bot_id: str | None = None) -> int:
        return len(self.list_candidates(bot_id=bot_id, status="pending"))
