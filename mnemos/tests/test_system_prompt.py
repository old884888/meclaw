"""Tests for system prompt assembly."""

from pathlib import Path

from backend.storage.soul_store import (
    DEFAULT_PLATFORM_CONSTRAINTS,
    build_system_prompt,
    read_platform_constraints,
)


def test_build_system_prompt_includes_platform_constraints(tmp_path):
    souls_root = tmp_path / "souls"
    platform_dir = souls_root / "_platform"
    platform_dir.mkdir(parents=True)
    (platform_dir / "constraints.md").write_text("平台规则 A", encoding="utf-8")

    prompt = build_system_prompt(
        "我是测试角色",
        bot_constraints="Bot 专属约束",
        platform_constraints=read_platform_constraints(souls_root),
    )

    assert "我是测试角色" in prompt
    assert "[约束]\nBot 专属约束" in prompt
    assert "[Platform constraints]\n平台规则 A" in prompt


def test_build_system_prompt_uses_default_platform_when_file_missing(tmp_path):
    souls_root = tmp_path / "souls"
    souls_root.mkdir()

    prompt = build_system_prompt(
        "Soul only",
        platform_constraints=read_platform_constraints(souls_root),
    )

    assert prompt.startswith("Soul only")
    assert "[Platform constraints]" in prompt
    assert "## Reasoning" in prompt
    assert DEFAULT_PLATFORM_CONSTRAINTS.splitlines()[0] in prompt
