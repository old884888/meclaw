"""Unit tests for reasoning payload and SSE parsing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.adapters import providers


def test_deepseek_reasoning_disabled_by_default():
    profile = providers.normalize_profile(
        {
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-v4-flash",
        }
    )
    payload = providers.build_payload(profile, [{"role": "user", "content": "hi"}], 100, True)
    assert payload["extra_body"] == {"thinking": {"type": "disabled"}}


def test_deepseek_reasoning_enabled_when_level_on():
    profile = providers.normalize_profile(
        {
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-v4-flash",
        }
    )
    payload = providers.build_payload(
        profile,
        [{"role": "user", "content": "hi"}],
        100,
        True,
        reasoning_level="medium",
    )
    assert payload["extra_body"] == {"thinking": {"type": "enabled"}}
    assert payload["reasoning_effort"] == "high"


def test_deepseek_anthropic_reasoning_effort_mapping():
    profile = providers.normalize_profile(
        {
            "provider": "anthropic",
            "base_url": "https://api.deepseek.com/anthropic",
            "api_key": "sk-test",
            "model": "deepseek-v4-flash",
            "optimizations": ["deepseek"],
        }
    )
    payload = providers.build_payload(
        profile,
        [{"role": "user", "content": "hi"}],
        100,
        True,
        reasoning_level="high",
    )
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["output_config"] == {"effort": "max"}


def test_parse_anthropic_thinking_delta():
    line = "data: " + json.dumps(
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "thinking_delta", "thinking": "step 1"},
        }
    )
    part, finish = providers._parse_anthropic_sse_line(line)
    assert part == ("reasoning", "step 1")
    assert finish is False


def test_effective_reasoning_for_bot():
    assert providers.effective_reasoning_for_bot({"reasoning_enabled": False}) == "off"
    assert providers.effective_reasoning_for_bot(
        {"reasoning_enabled": True, "reasoning_level": "high"}
    ) == "high"
    assert providers.effective_reasoning_for_bot(
        {"reasoning_enabled": True, "reasoning_level": "off"}
    ) == "medium"


def test_parse_openai_reasoning_content():
    line = "data: " + json.dumps(
        {
            "choices": [
                {
                    "delta": {"reasoning_content": "step 1"},
                    "finish_reason": None,
                }
            ]
        }
    )
    part, finish = providers._parse_openai_sse_line(line)
    assert part == ("reasoning", "step 1")
    assert finish is False


def test_parse_openai_content_only():
    line = "data: " + json.dumps(
        {
            "choices": [
                {
                    "delta": {"content": "hello"},
                    "finish_reason": None,
                }
            ]
        }
    )
    part, finish = providers._parse_openai_sse_line(line)
    assert part == ("content", "hello")
    assert finish is False


def test_history_messages_exclude_reasoning_field():
    messages = [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "a", "reasoning": "hidden chain"},
    ]
    history_msgs = [
        {"role": m["role"], "content": m.get("content", "")}
        for m in messages
        if m.get("role") in ("user", "assistant")
    ]
    assert history_msgs[1]["content"] == "a"
    assert "reasoning" not in history_msgs[1]
