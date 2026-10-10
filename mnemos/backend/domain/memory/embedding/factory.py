"""Construct an EmbeddingPort from config (with safe fallback)."""

from __future__ import annotations

import os
from typing import Any

from .api import ApiEmbedding
from .local import DEFAULT_LOCAL_MODEL, LocalEmbedding
from .port import EmbeddingPort, NullEmbedding


def _resolve_provider(cfg: dict) -> str:
    provider = str(cfg.get("embedding_provider") or "off").strip().lower()
    if provider not in ("local", "api", "off"):
        provider = "off"
    # Benchmark/dev bridge: env override when config is off.
    if provider == "off" and os.environ.get("MNEMOS_EMBED", "").strip().lower() == "local":
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


def create_embedding_port(cfg: dict, profiles: list[dict] | None = None) -> EmbeddingPort:
    """Return a usable embedding port, or NullEmbedding on any failure."""
    provider = _resolve_provider(cfg or {})
    if provider == "off":
        return NullEmbedding()

    model = str(cfg.get("embedding_model") or "").strip()
    if provider == "local":
        if not model and os.environ.get("MNEMOS_EMBED_MODEL"):
            model = os.environ.get("MNEMOS_EMBED_MODEL", "").strip()
        try:
            port = LocalEmbedding(model or DEFAULT_LOCAL_MODEL)
            return port if port.available else NullEmbedding()
        except Exception:  # noqa: BLE001
            return NullEmbedding()

    if provider == "api":
        profile_id = str(cfg.get("embedding_profile_id") or "").strip()
        profile = _find_profile(list(profiles or []), profile_id)
        if profile is None and profiles:
            profile = next((p for p in profiles if p.get("enabled", True)), profiles[0])
        if profile is None:
            return NullEmbedding()
        try:
            port = ApiEmbedding(profile, model)
            return port if port.available else NullEmbedding()
        except Exception:  # noqa: BLE001
            return NullEmbedding()

    return NullEmbedding()
