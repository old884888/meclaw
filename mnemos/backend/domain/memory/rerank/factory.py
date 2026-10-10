"""Construct a Reranker from config (with safe fallback)."""

from __future__ import annotations

import os
from typing import Any

from .api import ApiReranker
from .local import DEFAULT_RERANK_MODEL, LocalReranker
from .port import NullReranker, Reranker


def _resolve_rerank_enabled(cfg: dict) -> bool:
    if bool(cfg.get("rerank_enabled", False)):
        return True
    return os.environ.get("MNEMOS_RERANK", "").strip().lower() == "local"


def _resolve_rerank_provider(cfg: dict) -> str:
    provider = str(cfg.get("rerank_provider") or "off").strip().lower()
    if provider not in ("local", "api", "off"):
        provider = "off"
    if provider == "off" and _resolve_rerank_enabled(cfg):
        return "local"
    return provider


def _find_profile(profiles: list[dict], profile_id: str) -> dict | None:
    pid = (profile_id or "").strip()
    if not pid:
        return None
    for item in profiles or []:
        if str(item.get("id") or "") == pid:
            return item
    return None


def create_reranker(cfg: dict, profiles: list[dict] | None = None) -> Reranker:
    if not _resolve_rerank_enabled(cfg):
        return NullReranker()
    provider = _resolve_rerank_provider(cfg)
    model = str(cfg.get("rerank_model") or "").strip()
    if not model and os.environ.get("MNEMOS_RERANK_MODEL"):
        model = os.environ.get("MNEMOS_RERANK_MODEL", "").strip()

    if provider == "local":
        try:
            port = LocalReranker(model or DEFAULT_RERANK_MODEL)
            return port if port.available else NullReranker()
        except Exception:  # noqa: BLE001
            return NullReranker()

    if provider == "api":
        profile_id = str(cfg.get("rerank_profile_id") or "").strip()
        profile = _find_profile(list(profiles or []), profile_id)
        if profile is None and profiles:
            profile = next((p for p in profiles if p.get("enabled", True)), profiles[0])
        if profile is None:
            return NullReranker()
        try:
            port = ApiReranker(profile, model)
            return port if port.available else NullReranker()
        except Exception:  # noqa: BLE001
            return NullReranker()

    return NullReranker()
