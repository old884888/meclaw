"""Tests for P4b structured L1 extraction."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.adapters import providers
from backend.domain.memory.l1_extractor import (
    build_structured_extract_prompt,
    extract_atoms,
    extract_atoms_llm,
    normalize_extract_atom,
    parse_extraction_json,
)
from backend.domain.memory.paths import ensure_bot_memory_layout
from backend.domain.memory.store_l1 import get_atom_by_id, write_atom
from backend.storage.config_store import normalize_config


def test_normalize_extract_atom_validates_schema() -> None:
    atom = normalize_extract_atom(
        {
            "type": "preference",
            "content": "User prefers tea",
            "topic_key": "drink",
            "polarity": "switch",
            "confidence": 0.9,
            "subject": "user",
            "predicate": "prefers",
            "object": "tea",
            "supersedes_hint": "coffee",
        }
    )
    assert atom is not None
    assert atom["type"] == "preference"
    assert atom["subject"] == "user"
    assert atom["supersedes_hint"] == "coffee"

    assert normalize_extract_atom({"type": "fact"}) is None
    assert normalize_extract_atom({"content": "x", "type": "unknown"})["type"] == "fact"


def test_parse_extraction_json_accepts_array() -> None:
    raw = 'Here you go:\n[{"type":"fact","content":"Name is Alice","confidence":0.95}]'
    atoms, err = parse_extraction_json(raw)
    assert err is None
    assert len(atoms) == 1
    assert atoms[0]["content"] == "Name is Alice"


def test_parse_extraction_json_rejects_invalid() -> None:
    atoms, err = parse_extraction_json("not json at all")
    assert not atoms
    assert err


def test_build_structured_extract_prompt_includes_limits() -> None:
    prompt = build_structured_extract_prompt("hello world user msg", "assistant reply", max_atoms=3)
    assert "0-3" in prompt
    assert "hello world user msg" in prompt


def test_invalid_llm_json_falls_back_to_heuristic() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = ensure_bot_memory_layout(Path(tmp) / "souls", "b_l1")
        warnings: list[str] = []
        original = providers.chat_once

        def fake_chat_once(profile: dict, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
            return "sorry, no json here"

        providers.chat_once = fake_chat_once
        try:
            created = extract_atoms_llm(
                {"api_key": "k", "model": "m"},
                paths,
                session_id="s1",
                user_message="我非常喜欢喝拿铁咖啡，每天都要一杯",
                assistant_message="好的，我会记住。",
                on_warning=warnings.append,
            )
        finally:
            providers.chat_once = original

        assert len(created) == 1
        assert any("fallback" in w.lower() for w in warnings)


def test_supersedes_hint_links_prior_atom() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = ensure_bot_memory_layout(Path(tmp) / "souls", "b_sup")
        prior_path = write_atom(
            paths,
            atom_type="preference",
            content="用户喜欢喝拿铁",
            session_id="s0",
            topic_key="drink",
        )
        from backend.domain.memory.store_l1 import read_atom_file

        prior = read_atom_file(prior_path)
        assert prior is not None
        prior_id = str(prior["id"])

        original = providers.chat_once

        def fake_chat_once(profile: dict, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
            return (
                '[{"type":"preference","content":"用户改成只喝美式","topic_key":"drink",'
                '"polarity":"switch","supersedes_hint":"拿铁","confidence":0.95}]'
            )

        providers.chat_once = fake_chat_once
        try:
            created = extract_atoms_llm(
                {"api_key": "k", "model": "m"},
                paths,
                session_id="s1",
                user_message="我改成只喝美式了，不再喝拿铁",
                assistant_message="明白。",
            )
        finally:
            providers.chat_once = original

        assert len(created) == 1
        new_atom = get_atom_by_id(paths, str(created[0]["id"]))
        assert new_atom is not None
        assert str(new_atom.get("supersedes_id") or "") == prior_id
        old_atom = get_atom_by_id(paths, prior_id)
        assert old_atom is not None
        assert str(old_atom.get("superseded_by") or "") == str(new_atom.get("id"))


def test_extract_atoms_respects_mode_and_budget() -> None:
    cfg = normalize_config({"l1_extract_mode": "heuristic", "l1_extract_max_atoms": 5})
    assert cfg["l1_extract_mode"] == "heuristic"
    assert cfg["l1_extract_max_atoms"] == 5

    with tempfile.TemporaryDirectory() as tmp:
        paths = ensure_bot_memory_layout(Path(tmp) / "souls", "b_mode")
        original = providers.chat_once
        calls = {"n": 0}

        def fake_chat_once(profile: dict, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
            calls["n"] += 1
            items = [
                {"type": "fact", "content": f"fact number {i}", "confidence": 0.5 + i * 0.01}
                for i in range(8)
            ]
            import json

            return json.dumps(items)

        providers.chat_once = fake_chat_once
        try:
            created = extract_atoms(
                paths,
                session_id="s1",
                user_message="short",
                assistant_message="ok",
                mode="heuristic",
                profile={"api_key": "k"},
            )
            assert calls["n"] == 0
            assert len(created) <= 1

            created_llm = extract_atoms(
                paths,
                session_id="s2",
                user_message="这是一段足够长的用户消息，应该触发结构化提取",
                assistant_message="收到",
                mode="llm",
                profile={"api_key": "k"},
                max_atoms=5,
            )
            assert calls["n"] == 1
            assert len(created_llm) == 5
        finally:
            providers.chat_once = original
