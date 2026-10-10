"""Local embedding via fastembed (optional dependency)."""

from __future__ import annotations

import math
import os
from pathlib import Path

from .port import EmbeddingPort

DEFAULT_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MECLAW2_ROOT = Path(__file__).resolve().parents[4]

_model_cache: dict[str, object] = {}


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _embedding_cache_dir() -> str:
    for key in ("FASTEMBED_CACHE_PATH", "FASTEMBED_CACHE_DIR"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return raw
    return str((MECLAW2_ROOT / ".fastembed_cache").resolve())


class LocalEmbedding:
    def __init__(self, model: str = DEFAULT_LOCAL_MODEL) -> None:
        self._model_name = (model or DEFAULT_LOCAL_MODEL).strip() or DEFAULT_LOCAL_MODEL
        self._dim = 0
        self._load_error: Exception | None = None
        try:
            self._ensure_model()
        except Exception as exc:  # noqa: BLE001
            self._load_error = exc

    @property
    def available(self) -> bool:
        return self._load_error is None and self._dim > 0

    @property
    def model_identity(self) -> str:
        if not self.available:
            return ""
        return f"local:{self._model_name}:{self._dim}"

    def _ensure_model(self) -> object:
        if self._model_name in _model_cache:
            return _model_cache[self._model_name]
        from fastembed import TextEmbedding

        model = TextEmbedding(model_name=self._model_name, cache_dir=_embedding_cache_dir())
        probe = list(next(iter(model.embed(["probe"]))))
        self._dim = len(probe)
        _model_cache[self._model_name] = model
        return model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.available:
            return [[] for _ in texts]
        model = self._ensure_model()
        stripped = [(t or "").strip() for t in texts]
        inputs = [t for t in stripped if t]
        by_text: dict[str, list[float]] = {}
        if inputs:
            try:
                for text, vec in zip(inputs, model.embed(inputs)):
                    by_text[text] = _normalize([float(x) for x in vec])
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(str(exc)) from exc
        return [by_text.get(t, []) if t else [] for t in stripped]
