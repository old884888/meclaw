"""Local cross-encoder reranker via fastembed (optional dependency)."""

from __future__ import annotations

from typing import Any

DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-base"

_model_cache: dict[str, object] = {}


class LocalReranker:
    def __init__(self, model: str = DEFAULT_RERANK_MODEL) -> None:
        self._model_name = (model or DEFAULT_RERANK_MODEL).strip() or DEFAULT_RERANK_MODEL
        self._load_error: Exception | None = None
        try:
            self._ensure_model()
        except Exception as exc:  # noqa: BLE001
            self._load_error = exc

    @property
    def available(self) -> bool:
        return self._load_error is None and self._model_name in _model_cache

    def _ensure_model(self) -> object:
        if self._model_name in _model_cache:
            return _model_cache[self._model_name]
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        model = TextCrossEncoder(model_name=self._model_name)
        _model_cache[self._model_name] = model
        return model

    def rerank(self, query: str, candidates: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
        if not candidates:
            return candidates
        if not self.available:
            return candidates[:top_k]
        docs = [str(c.get("body") or c.get("snippet") or "") for c in candidates]
        try:
            model = self._ensure_model()
            scores = list(model.rerank(query, docs))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(str(exc)) from exc
        ranked = sorted(zip(candidates, scores), key=lambda cs: float(cs[1]), reverse=True)
        out: list[dict[str, Any]] = []
        for cand, score in ranked[:top_k]:
            item = dict(cand)
            item["rerank_score"] = float(score)
            out.append(item)
        return out
