"""Embedding API via OpenAI-compatible /embeddings endpoint."""

from __future__ import annotations

import math
from typing import Any

import requests

from ....adapters import providers
from .port import EmbeddingPort


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _embeddings_endpoint(profile: dict) -> str:
    base = (profile.get("base_url") or "").rstrip("/")
    if base.endswith("/embeddings"):
        return base
    if base.endswith("/v1"):
        return base + "/embeddings"
    if base.endswith("/chat/completions"):
        return base[: -len("/chat/completions")] + "/embeddings"
    return base + "/v1/embeddings"


class ApiEmbedding:
    def __init__(self, profile: dict, model: str, *, timeout: int = 60) -> None:
        self._profile = providers.normalize_profile(profile)
        self._model = (model or self._profile.get("model") or "").strip()
        self._timeout = timeout
        self._dim = 0
        self._load_error: Exception | None = None
        if not self._profile.get("api_key") or not self._model:
            self._load_error = RuntimeError("embedding API profile or model missing")

    @property
    def available(self) -> bool:
        return self._load_error is None and bool(self._model)

    @property
    def model_identity(self) -> str:
        if not self.available:
            return ""
        pid = str(self._profile.get("id") or "api")
        dim = self._dim or 0
        return f"api:{pid}:{self._model}:{dim}"

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        endpoint = _embeddings_endpoint(self._profile)
        headers = providers.build_headers(self._profile)
        resp = requests.post(
            endpoint,
            headers=headers,
            json={"model": self._model, "input": texts},
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(providers.format_http_error(resp.status_code, resp.text))
        data = resp.json()
        items: list[dict[str, Any]] = data.get("data") or []
        items.sort(key=lambda x: int(x.get("index", 0)))
        out: list[list[float]] = []
        for item in items:
            raw = item.get("embedding") or []
            out.append(_normalize([float(x) for x in raw]))
        return out

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.available:
            return [[] for _ in texts]
        stripped = [(t or "").strip() for t in texts]
        inputs = [t for t in stripped if t]
        by_text: dict[str, list[float]] = {}
        if inputs:
            try:
                vectors = self._call_api(inputs)
                if vectors and vectors[0] and not self._dim:
                    self._dim = len(vectors[0])
                by_text = dict(zip(inputs, vectors))
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(str(exc)) from exc
        return [by_text.get(t, []) if t else [] for t in stripped]
