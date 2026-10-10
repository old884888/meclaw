"""Tests for bot-selected model surviving provider normalization."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.adapters import providers


def test_normalize_profile_preserves_explicit_model_in_list():
    profile = providers.normalize_profile(
        {
            "provider": "anthropic",
            "base_url": "https://api.deepseek.com/anthropic",
            "api_key": "sk-test",
            "model": "deepseek-v4-pro",
            "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
            "optimizations": ["deepseek"],
        }
    )
    assert profile["model"] == "deepseek-v4-pro"


def test_normalize_profile_defaults_to_first_model_when_unset():
    profile = providers.normalize_profile(
        {
            "provider": "anthropic",
            "base_url": "https://api.deepseek.com/anthropic",
            "api_key": "sk-test",
            "model": "",
            "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
        }
    )
    assert profile["model"] == "deepseek-v4-flash"


def test_build_payload_uses_bot_selected_model():
    merged = {
        "provider": "anthropic",
        "base_url": "https://api.deepseek.com/anthropic",
        "api_key": "sk-test",
        "model": "deepseek-v4-pro",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
        "optimizations": ["deepseek"],
    }
    payload = providers.build_payload(
        merged,
        [{"role": "user", "content": "hi"}],
        100,
        True,
    )
    assert payload["model"] == "deepseek-v4-pro"
