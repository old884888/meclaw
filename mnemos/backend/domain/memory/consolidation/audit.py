"""Consolidation audit log."""

from __future__ import annotations

import json
from typing import Any

from ....storage.common import now_iso
from ..paths import BotMemoryPaths


def audit_path(paths: BotMemoryPaths):
    return paths.root / "consolidation_audit.jsonl"


def log_consolidation_event(paths: BotMemoryPaths, event: dict[str, Any]) -> None:
    path = audit_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"at": now_iso(), **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
