"""Pin rules for consolidation."""

from __future__ import annotations

from typing import Any

from ..memory_scoring import atom_importance


def is_pinned(atom: dict[str, Any], *, importance_threshold: float = 0.9) -> bool:
    meta = atom.get("meta") or {}
    atom_type = str(atom.get("type") or meta.get("type") or "").strip().lower()
    if atom_type == "constraint":
        return True
    if str(meta.get("chain_summary") or atom.get("chain_summary") or "").lower() == "true":
        return True
    return atom_importance(atom) >= float(importance_threshold or 0.9)
