"""Tests for rolling session JSON backups."""

from __future__ import annotations

import json
from pathlib import Path

from backend.storage.common import read_json, rotate_file_backups, write_json_atomic
from backend.storage.history_store import save_messages


def test_three_saves_create_rotated_backups(tmp_path: Path) -> None:
    target = tmp_path / "s_test.json"
    write_json_atomic(target, {"v": 1}, backup_generations=3)
    write_json_atomic(target, {"v": 2}, backup_generations=3)
    write_json_atomic(target, {"v": 3}, backup_generations=3)

    assert read_json(target, {}) == {"v": 3}
    assert read_json(Path(f"{target}.bak1"), {}) == {"v": 2}
    assert read_json(Path(f"{target}.bak2"), {}) == {"v": 1}
    assert not Path(f"{target}.bak3").exists()


def test_rotation_drops_oldest_when_limit_exceeded(tmp_path: Path) -> None:
    target = tmp_path / "s_rotate.json"
    for version in range(1, 6):
        write_json_atomic(target, {"v": version}, backup_generations=3)

    assert read_json(target, {}) == {"v": 5}
    assert read_json(Path(f"{target}.bak1"), {}) == {"v": 4}
    assert read_json(Path(f"{target}.bak2"), {}) == {"v": 3}
    assert read_json(Path(f"{target}.bak3"), {}) == {"v": 2}
    assert not Path(f"{target}.bak4").exists()


def test_save_messages_writes_backup(tmp_path: Path) -> None:
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    save_messages(history_dir, "s_abc", [{"role": "user", "content": "hi"}], backup_generations=2)
    save_messages(history_dir, "s_abc", [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}], backup_generations=2)

    session_path = history_dir / "s_abc.json"
    bak1 = Path(f"{session_path}.bak1")
    assert session_path.exists()
    assert bak1.exists()
    messages = json.loads(session_path.read_text(encoding="utf-8"))
    assert len(messages) == 2
    old_messages = json.loads(bak1.read_text(encoding="utf-8"))
    assert len(old_messages) == 1


def test_rotate_noop_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    rotate_file_backups(missing, 3)
    assert not missing.exists()
