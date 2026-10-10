"""Soft delete audit for memory records."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import BotMemoryPaths


def soft_delete_record(
    paths: BotMemoryPaths,
    *,
    table: str,
    record_id: str,
    reason: str = "",
    deleted_by: str = "user",
) -> None:
    paths.deleted_audit.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "table": table,
        "record_id": record_id,
        "deleted_at": datetime.utcnow().isoformat() + "Z",
        "deleted_by": deleted_by,
        "delete_reason": reason,
    }
    with paths.deleted_audit.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def mark_atom_deleted(atom_path: Path, paths: BotMemoryPaths, *, reason: str = "") -> None:
    if not atom_path.exists():
        return
    text = atom_path.read_text(encoding="utf-8")
    if "is_deleted:" not in text:
        text = text.replace("---\n", '---\nis_deleted: "true"\n', 1)
    else:
        text = text.replace('is_deleted: "false"', 'is_deleted: "true"')
    atom_path.write_text(text, encoding="utf-8")
    atom_id = atom_path.stem
    soft_delete_record(paths, table="l1", record_id=atom_id, reason=reason)
