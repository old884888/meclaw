"""Unit tests for context_assembler — cache-discipline assembly."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.brains.context_assembler import (
    assemble_api_messages,
    build_dynamic_context,
    join_blocks,
    prefix_user_content,
)


def test_join_blocks_filters_empty():
    assert join_blocks(["", "  ", "hello"]) == "hello"
    assert join_blocks([]) == ""


def test_join_blocks_separator():
    result = join_blocks(["a", "b"])
    assert "a" in result and "b" in result
    assert "---" in result


def test_build_dynamic_context_empty():
    assert build_dynamic_context([]) == ""
    assert build_dynamic_context(["", "  "]) == ""


def test_build_dynamic_context_header():
    result = build_dynamic_context(["memory block"])
    assert result.startswith("[Session context]")
    assert "memory block" in result


def test_prefix_user_content_string():
    result = prefix_user_content("hello", "context")
    assert result.startswith("context")
    assert "hello" in result


def test_prefix_user_content_no_dynamic():
    assert prefix_user_content("hello", "") == "hello"
    assert prefix_user_content("hello", None) == "hello"


def test_prefix_user_content_none_base():
    result = prefix_user_content(None, "ctx")
    assert "ctx" in result


def test_prefix_user_content_multimodal_prepends_text():
    content = [{"type": "text", "text": "original"}, {"type": "image_url", "image_url": {"url": "x"}}]
    result = prefix_user_content(content, "dynamic")
    assert isinstance(result, list)
    assert result[0]["type"] == "text"
    assert "dynamic" in result[0]["text"]
    assert "original" in result[0]["text"]


def test_prefix_user_content_multimodal_no_text_part():
    content = [{"type": "image_url", "image_url": {"url": "x"}}]
    result = prefix_user_content(content, "dynamic")
    assert isinstance(result, list)
    assert result[0]["type"] == "text"
    assert result[0]["text"] == "dynamic"


# --- assemble_api_messages ---

def test_assemble_stable_is_first():
    msgs = assemble_api_messages(
        stable_system="sys",
        semi_stable_blocks=[],
        dynamic_blocks=[],
        history_messages=[{"role": "user", "content": "hi"}],
    )
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == "sys"


def test_assemble_dynamic_prefixes_last_user():
    history = [
        {"role": "user", "content": "turn1"},
        {"role": "assistant", "content": "reply1"},
        {"role": "user", "content": "turn2"},
    ]
    msgs = assemble_api_messages(
        stable_system="sys",
        semi_stable_blocks=[],
        dynamic_blocks=["mem block"],
        history_messages=history,
    )
    last_user = next(m for m in reversed(msgs) if m["role"] == "user")
    assert "[Session context]" in last_user["content"]
    assert "mem block" in last_user["content"]
    assert "turn2" in last_user["content"]


def test_assemble_dynamic_no_user_appends():
    msgs = assemble_api_messages(
        stable_system="sys",
        semi_stable_blocks=[],
        dynamic_blocks=["ctx"],
        history_messages=[{"role": "assistant", "content": "bot reply"}],
    )
    last = msgs[-1]
    assert last["role"] == "user"
    assert "ctx" in last["content"]


def test_assemble_no_dynamic_no_extra_message():
    history = [{"role": "user", "content": "q"}]
    msgs = assemble_api_messages(
        stable_system="sys",
        semi_stable_blocks=[],
        dynamic_blocks=[],
        history_messages=history,
    )
    assert len(msgs) == 2  # system + user
    assert msgs[1]["content"] == "q"


def test_assemble_history_between_stable_and_dynamic():
    """Dynamic content must appear after history (inside user prefix), not before."""
    history = [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "a"},
        {"role": "user", "content": "q2"},
    ]
    msgs = assemble_api_messages(
        stable_system="sys",
        semi_stable_blocks=[],
        dynamic_blocks=["dynamic"],
        history_messages=history,
    )
    roles = [m["role"] for m in msgs]
    # system must come first
    assert roles[0] == "system"
    # there should be no standalone dynamic system block before history
    system_msgs = [m for m in msgs if m["role"] == "system"]
    assert len(system_msgs) == 1
    assert system_msgs[0]["content"] == "sys"


def test_assemble_stable_excludes_dynamic_text():
    """Stable system must not contain the dynamic block text."""
    msgs = assemble_api_messages(
        stable_system="persona block",
        semi_stable_blocks=[],
        dynamic_blocks=["retrieved memory fact"],
        history_messages=[{"role": "user", "content": "q"}],
    )
    system_content = " ".join(m["content"] for m in msgs if m["role"] == "system")
    assert "retrieved memory fact" not in system_content


def test_assemble_semi_stable_adds_system():
    msgs = assemble_api_messages(
        stable_system="sys",
        semi_stable_blocks=["group roster"],
        dynamic_blocks=[],
        history_messages=[{"role": "user", "content": "q"}],
    )
    system_msgs = [m for m in msgs if m["role"] == "system"]
    assert len(system_msgs) == 2
    assert any("group roster" in m["content"] for m in system_msgs)


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception:
            print(f"  FAIL  {fn.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
