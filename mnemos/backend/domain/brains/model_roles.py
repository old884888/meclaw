"""Model role resolution: executor / extraction / summary / embedding / rerank."""

from __future__ import annotations

from typing import Any, Callable

from ...adapters import providers

LLM_ROLES = frozenset({"executor", "extraction", "summary", "background"})
INFRA_ROLES = frozenset({"embedding", "rerank"})
ALL_ROLES = LLM_ROLES | INFRA_ROLES


def normalize_role_binding(raw: object) -> dict[str, str] | None:
    if not raw or not isinstance(raw, dict):
        return None
    out: dict[str, str] = {}
    profile_id = str(raw.get("profile_id") or "").strip()
    model = str(raw.get("model") or "").strip()
    provider = str(raw.get("provider") or "").strip().lower()
    if profile_id:
        out["profile_id"] = profile_id
    if model:
        out["model"] = model
    if provider:
        out["provider"] = provider
    return out or None


def normalize_model_roles(raw: object) -> dict[str, dict[str, str]]:
    if not raw or not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for role in ("executor", "extraction", "summary", "embedding", "rerank"):
        binding = normalize_role_binding(raw.get(role))
        if binding:
            out[role] = binding
    return out


def normalize_role_name(role: str) -> str:
    name = (role or "executor").strip().lower()
    if name in ALL_ROLES:
        return name
    return "executor"


def merged_role_binding(cfg: dict, bot: dict | None, role: str) -> dict[str, str] | None:
    role_name = normalize_role_name(role)
    bot_roles = normalize_model_roles(((bot or {}).get("brains") or {}).get("model_roles"))
    global_roles = normalize_model_roles(cfg.get("model_roles"))
    if role_name in bot_roles:
        return bot_roles[role_name]
    if role_name in global_roles:
        return global_roles[role_name]
    return None


def _apply_model_selection(
    merged: dict,
    *,
    selected: str,
    fallback: str,
    available: list[str],
) -> None:
    if selected and ((not available) or selected in available):
        merged["model"] = selected
    elif fallback and ((not available) or fallback in available):
        merged["model"] = fallback
    elif available:
        merged["model"] = available[0]


def resolve_llm_profile_for_role(
    cfg: dict,
    bot: dict,
    role: str,
    find_profile_fn: Callable[[str], dict | None],
) -> dict | None:
    """Resolve an LLM profile dict for executor/extraction/summary/background."""
    role_name = normalize_role_name(role)
    if role_name not in LLM_ROLES:
        role_name = "executor"

    binding: dict[str, str] | None = None
    if role_name == "executor":
        binding = merged_role_binding(cfg, bot, "executor")
    elif role_name in ("extraction", "summary"):
        binding = merged_role_binding(cfg, bot, role_name)

    profile_id = (binding or {}).get("profile_id") or str(bot.get("profile_id") or "").strip()
    profile = find_profile_fn(profile_id)
    if not profile:
        return None
    if not profile.get("enabled", True):
        return None

    merged = dict(profile)
    available = providers.profile_models(profile)
    bot_model = str(bot.get("model") or "").strip()
    background_model = str(bot.get("background_model") or "").strip()

    if role_name == "executor":
        selected = (binding or {}).get("model") or bot_model
        _apply_model_selection(merged, selected=selected, fallback=bot_model, available=available)
    elif role_name == "extraction":
        selected = (binding or {}).get("model") or background_model or bot_model
        _apply_model_selection(
            merged,
            selected=selected,
            fallback=background_model or bot_model,
            available=available,
        )
    elif role_name == "summary":
        selected = (binding or {}).get("model") or background_model or bot_model
        _apply_model_selection(
            merged,
            selected=selected,
            fallback=background_model or bot_model,
            available=available,
        )
    elif role_name == "background":
        selected = background_model or bot_model
        _apply_model_selection(
            merged,
            selected=selected,
            fallback=bot_model,
            available=available,
        )

    if bot.get("temperature") is not None:
        merged["temperature"] = bot["temperature"]
    if bot.get("max_tokens") is not None:
        merged["max_tokens"] = bot["max_tokens"]
    return merged


def resolve_infra_role(cfg: dict, bot: dict | None, role: str) -> dict[str, Any]:
    """Resolve embedding/rerank role; falls back to global P1/P2 config fields."""
    role_name = normalize_role_name(role)
    binding = merged_role_binding(cfg, bot, role_name)

    if role_name == "embedding":
        provider = str(cfg.get("embedding_provider") or "off").strip().lower()
        model = str(cfg.get("embedding_model") or "").strip()
        profile_id = str(cfg.get("embedding_profile_id") or "").strip()
        source = "global"
        if binding:
            if binding.get("provider"):
                provider = binding["provider"]
            if binding.get("model"):
                model = binding["model"]
            if binding.get("profile_id"):
                profile_id = binding["profile_id"]
            source = "role_binding"
        enabled = provider not in ("", "off")
        return {
            "role": "embedding",
            "provider": provider,
            "model": model,
            "profile_id": profile_id,
            "enabled": enabled,
            "source": source,
        }

    if role_name == "rerank":
        provider = str(cfg.get("rerank_provider") or "off").strip().lower()
        model = str(cfg.get("rerank_model") or "").strip()
        profile_id = str(cfg.get("rerank_profile_id") or "").strip()
        rerank_enabled = bool(cfg.get("rerank_enabled", False))
        source = "global"
        if binding:
            if binding.get("provider"):
                provider = binding["provider"]
            if binding.get("model"):
                model = binding["model"]
            if binding.get("profile_id"):
                profile_id = binding["profile_id"]
            source = "role_binding"
        enabled = rerank_enabled and provider not in ("", "off")
        return {
            "role": "rerank",
            "provider": provider,
            "model": model,
            "profile_id": profile_id,
            "enabled": enabled,
            "source": source,
        }

    return {"role": role_name, "enabled": False, "provider": "off", "model": "", "profile_id": "", "source": "none"}


def apply_infra_role_overrides(cfg: dict, bot: dict | None) -> dict:
    """Merge model_roles embedding/rerank bindings into effective runtime config."""
    out = dict(cfg or {})
    emb = resolve_infra_role(out, bot, "embedding")
    if emb.get("provider"):
        out["embedding_provider"] = emb["provider"]
    if emb.get("model"):
        out["embedding_model"] = emb["model"]
    if emb.get("profile_id"):
        out["embedding_profile_id"] = emb["profile_id"]

    rer = resolve_infra_role(out, bot, "rerank")
    if rer.get("provider"):
        out["rerank_provider"] = rer["provider"]
    if rer.get("model"):
        out["rerank_model"] = rer["model"]
    if rer.get("profile_id"):
        out["rerank_profile_id"] = rer["profile_id"]
    return out


def find_bot_in_cfg(cfg: dict, bot_id: str) -> dict | None:
    bid = str(bot_id or "").strip()
    if not bid:
        return None
    for item in cfg.get("bots") or []:
        if str(item.get("id") or "") == bid:
            return item
    return None


def effective_cfg_for_bot(cfg: dict, bot_id: str, effective_brains: dict | None = None) -> dict:
    out = dict(cfg or {})
    if effective_brains:
        out.update(dict(effective_brains))
    bot = find_bot_in_cfg(out, bot_id)
    if bot:
        out = apply_infra_role_overrides(out, bot)
    return out


def resolve_role_models_for_display(
    cfg: dict,
    bot: dict,
    profile_for_bot_fn: Callable[[dict, str], dict],
) -> dict[str, dict[str, Any]]:
    """Resolved models for brain status / UI."""
    out: dict[str, dict[str, Any]] = {}
    for role in ("executor", "extraction", "summary"):
        try:
            profile = profile_for_bot_fn(bot, role)
            out[role] = {
                "model": str(profile.get("model") or ""),
                "enabled": True,
                "source": "resolved",
            }
        except Exception:  # noqa: BLE001
            fallback = str(bot.get("model") or "")
            if role in ("extraction", "summary"):
                fallback = str(bot.get("background_model") or "").strip() or fallback
            out[role] = {"model": fallback, "enabled": bool(fallback), "source": "fallback"}

    for role in ("embedding", "rerank"):
        info = resolve_infra_role(cfg, bot, role)
        label = info.get("model") or info.get("provider") or "—"
        out[role] = {
            "model": str(label),
            "provider": str(info.get("provider") or "off"),
            "enabled": bool(info.get("enabled")),
            "source": str(info.get("source") or "global"),
        }
    return out
