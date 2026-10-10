"""Unit tests for cache usage parsing in providers.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.adapters.providers import (
    _parse_anthropic_sse_line,
    _parse_openai_sse_line,
    parse_cache_usage,
)


# --- parse_cache_usage ---

def test_parse_cache_usage_none():
    result = parse_cache_usage(None)
    assert result["supported"] is False
    assert result["hit_rate"] is None


def test_parse_cache_usage_empty_dict():
    result = parse_cache_usage({})
    assert result["supported"] is False


def test_parse_cache_usage_deepseek_style():
    usage = {
        "prompt_tokens": 5000,
        "prompt_cache_hit_tokens": 3000,
        "prompt_cache_miss_tokens": 2000,
    }
    result = parse_cache_usage(usage)
    assert result["supported"] is True
    assert result["read"] == 3000
    assert result["create"] == 2000
    assert result["hit_rate"] == 60.0


def test_parse_cache_usage_openai_style():
    usage = {
        "cache_read_input_tokens": 8000,
        "cache_creation_input_tokens": 500,
    }
    result = parse_cache_usage(usage)
    assert result["supported"] is True
    assert result["read"] == 8000
    assert result["create"] == 500
    assert result["hit_rate"] == round(8000 / 8500 * 100, 1)


def test_parse_cache_usage_anthropic_style():
    usage = {
        "input_tokens": 100,
        "cache_read_input_tokens": 9000,
        "cache_creation_input_tokens": 1000,
    }
    result = parse_cache_usage(usage)
    assert result["supported"] is True
    assert result["hit_rate"] == 90.0


def test_parse_cache_usage_infers_miss_from_prompt_tokens():
    usage = {
        "prompt_tokens": 5000,
        "prompt_cache_hit_tokens": 3000,
    }
    result = parse_cache_usage(usage)
    assert result["supported"] is True
    assert result["read"] == 3000
    assert result["create"] == 2000
    assert result["hit_rate"] == 60.0


def test_parse_cache_usage_unknown_miss_does_not_fake_100():
    usage = {
        "cache_read_input_tokens": 4000,
    }
    result = parse_cache_usage(usage)
    assert result["supported"] is True
    assert result["read"] == 4000
    assert result["create"] == 0
    assert result["hit_rate"] is None


def test_parse_cache_usage_no_cache_fields():
    usage = {"prompt_tokens": 500, "completion_tokens": 100}
    result = parse_cache_usage(usage)
    assert result["supported"] is False
    assert result["hit_rate"] is None


def test_parse_cache_usage_zero_denominator():
    usage = {"cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    result = parse_cache_usage(usage)
    assert result["supported"] is False


# --- SSE parsers with usage_collector ---

def _sse(data: dict) -> str:
    return "data: " + json.dumps(data)


def test_openai_sse_captures_usage():
    collector: dict = {}
    line = _sse({"choices": [{"delta": {"content": "hi"}, "finish_reason": None}],
                 "usage": {"prompt_cache_hit_tokens": 2000, "prompt_cache_miss_tokens": 500}})
    part, finish = _parse_openai_sse_line(line, collector)
    assert part == ("content", "hi")
    assert collector.get("prompt_cache_hit_tokens") == 2000


def test_openai_sse_done():
    _, finish = _parse_openai_sse_line("data: [DONE]", None)
    assert finish is True


def test_openai_sse_no_usage_field():
    collector: dict = {}
    line = _sse({"choices": [{"delta": {"content": "hi"}, "finish_reason": None}]})
    _parse_openai_sse_line(line, collector)
    assert collector == {}


def test_anthropic_sse_captures_usage():
    collector: dict = {}
    line = _sse({"type": "message_start", "message": {},
                 "usage": {"cache_read_input_tokens": 5000, "cache_creation_input_tokens": 1000}})
    _parse_anthropic_sse_line(line, collector)
    assert collector.get("cache_read_input_tokens") == 5000


def test_anthropic_sse_accumulates_usage():
    collector: dict = {}
    line1 = _sse({"type": "message_start", "usage": {"cache_read_input_tokens": 3000}})
    line2 = _sse({"type": "message_delta", "usage": {"cache_read_input_tokens": 500}})
    _parse_anthropic_sse_line(line1, collector)
    _parse_anthropic_sse_line(line2, collector)
    assert collector["cache_read_input_tokens"] == 3500


def test_anthropic_sse_message_stop():
    _, finish = _parse_anthropic_sse_line(_sse({"type": "message_stop"}), None)
    assert finish is True


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
