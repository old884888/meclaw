"""Common storage utilities."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any):
    if not path.exists():
        return deepcopy(default)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def rotate_file_backups(path: Path, generations: int) -> None:
    """Rotate rolling backups as ``path.bak1``, ``path.bak2``, … before overwrite.

    Manual restore: copy ``session.json.bak1`` over ``session.json`` when the
    primary file is corrupted.
    """
    if generations <= 0 or not path.exists():
        return
    oldest = Path(f"{path}.bak{generations}")
    if oldest.exists():
        oldest.unlink()
    for idx in range(generations - 1, 0, -1):
        src = Path(f"{path}.bak{idx}")
        dst = Path(f"{path}.bak{idx + 1}")
        if src.exists():
            os.replace(src, dst)
    bak1 = Path(f"{path}.bak1")
    bak1.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def write_json_atomic(
    path: Path,
    data: Any,
    backup: bool = False,
    backup_generations: int = 0,
) -> None:
    ensure_parent(path)
    generations = backup_generations if backup_generations > 0 else (1 if backup else 0)
    if generations > 0 and path.exists():
        rotate_file_backups(path, generations)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

