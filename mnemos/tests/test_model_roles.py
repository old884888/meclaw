"""Tests for model role resolution (P3)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.brains.model_roles import (
    apply_infra_role_overrides,
    normalize_model_roles,
    resolve_infra_role,
    resolve_llm_profile_for_role,
)
from backend.storage.config_store import normalize_bot, normalize_config


def _profiles() -> list[dict]:
    return [
        {
            "id": "p_main",
            "name": "Main",
            "enabled": True,
            "base_url": "https://example.com",
            "api_key": "sk-test",
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-4o-nano"],
            "model": "gpt-4o",
        }
    ]


def _find_profile(profile_id: str) -> dict | None:
    for item in _profiles():
        if item["id"] == profile_id:
            return item
    return None


def test_default_roles_match_legacy_background() -> None:
    cfg = normalize_config({"api_profiles": _profiles(), "model_roles": {}})
    bot = normalize_bot(
        {
            "id": "b1",
            "profile_id": "p_main",
            "model": "gpt-4o",
            "background_model": "gpt-4o-mini",
        }
    )
    executor = resolve_llm_profile_for_role(cfg, bot, "executor", _find_profile)
    extraction = resolve_llm_profile_for_role(cfg, bot, "extraction", _find_profile)
    summary = resolve_llm_profile_for_role(cfg, bot, "summary", _find_profile)
    assert executor is not None and executor["model"] == "gpt-4o"
    assert extraction is not None and extraction["model"] == "gpt-4o-mini"
    assert summary is not None and summary["model"] == "gpt-4o-mini"


def test_bot_model_roles_override_background() -> None:
    cfg = normalize_config({"api_profiles": _profiles(), "model_roles": {}})
    bot = normalize_bot(
        {
            "id": "b1",
            "profile_id": "p_main",
            "model": "gpt-4o",
            "background_model": "gpt-4o-mini",
            "brains": {
                "model_roles": {
                    "extraction": {"profile_id": "p_main", "model": "gpt-4o-nano"},
                    "summary": {"profile_id": "p_main", "model": "gpt-4o-mini"},
                }
            },
        }
    )
    extraction = resolve_llm_profile_for_role(cfg, bot, "extraction", _find_profile)
    summary = resolve_llm_profile_for_role(cfg, bot, "summary", _find_profile)
    assert extraction is not None and extraction["model"] == "gpt-4o-nano"
    assert summary is not None and summary["model"] == "gpt-4o-mini"


def test_global_model_roles_inheritance() -> None:
    cfg = normalize_config(
        {
            "api_profiles": _profiles(),
            "model_roles": {
                "summary": {"profile_id": "p_main", "model": "gpt-4o-nano"},
            },
        }
    )
    bot = normalize_bot(
        {
            "id": "b1",
            "profile_id": "p_main",
            "model": "gpt-4o",
            "background_model": "",
        }
    )
    summary = resolve_llm_profile_for_role(cfg, bot, "summary", _find_profile)
    assert summary is not None and summary["model"] == "gpt-4o-nano"


def test_infra_roles_merge_with_global_config() -> None:
    cfg = normalize_config(
        {
            "embedding_provider": "local",
            "embedding_model": "default-model",
            "rerank_enabled": True,
            "rerank_provider": "local",
            "rerank_model": "rerank-base",
            "model_roles": {
                "embedding": {"provider": "api", "model": "text-embed", "profile_id": "p_main"},
            },
        }
    )
    bot = normalize_bot({"id": "b1", "profile_id": "p_main", "model": "gpt-4o"})
    emb = resolve_infra_role(cfg, bot, "embedding")
    assert emb["provider"] == "api"
    assert emb["model"] == "text-embed"
    merged = apply_infra_role_overrides(cfg, bot)
    assert merged["embedding_provider"] == "api"
    assert merged["embedding_model"] == "text-embed"

    rer = resolve_infra_role(cfg, bot, "rerank")
    assert rer["enabled"] is True
    assert rer["provider"] == "local"


def test_normalize_bot_brains_preserves_model_roles() -> None:
    bot = normalize_bot(
        {
            "id": "b1",
            "brains": {
                "model_roles": {
                    "extraction": {"profile_id": "p_main", "model": "gpt-4o-mini"},
                }
            },
        }
    )
    roles = (bot.get("brains") or {}).get("model_roles") or {}
    assert roles["extraction"]["model"] == "gpt-4o-mini"


def main() -> None:
    test_default_roles_match_legacy_background()
    test_bot_model_roles_override_background()
    test_global_model_roles_inheritance()
    test_infra_roles_merge_with_global_config()
    test_normalize_bot_brains_preserves_model_roles()
    print("model roles tests OK")


if __name__ == "__main__":
    main()
