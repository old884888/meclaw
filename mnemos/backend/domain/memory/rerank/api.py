"""API LLM reranker — scores each candidate with a cheap model."""

from __future__ import annotations

import json
import re
from typing import Any

from ....adapters import providers
from .port import Reranker

_SCORE_RE = re.compile(r"0\.\d+|1\.0|1|0")


class ApiReranker:
    def __init__(self, profile: dict, model: str, *, timeout: int = 45) -> None:
        self._profile = providers.normalize_profile(profile)
        self._model = (model or self._profile.get("model") or "").strip()
        self._timeout = timeout
        self._load_error: Exception | None = None
        if not self._profile.get("api_key") or not self._model:
            self._load_error = RuntimeError("rerank API profile or model missing")

    @property
    def available(self) -> bool:
        return self._load_error is None

    def rerank(self, query: str, candidates: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
        if not candidates or not self.available:
            return candidates[:top_k]
        lines = []
        for i, cand in enumerate(candidates, start=1):
            text = str(cand.get("body") or cand.get("snippet") or "")[:400]
            lines.append(f"{i}. {text}")
        prompt = (
            "Score each memory snippet for relevance to the user question.\n"
            "Reply with JSON array of floats in [0,1], one score per line item, same order.\n\n"
            f"Question: {query}\n\nSnippets:\n" + "\n".join(lines)
        )
        profile = dict(self._profile)
        profile["model"] = self._model
        raw = providers.chat_once(
            profile,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            timeout=self._timeout,
        )
        scores = _parse_scores(raw, len(candidates))
        ranked = sorted(zip(candidates, scores), key=lambda cs: float(cs[1]), reverse=True)
        out: list[dict[str, Any]] = []
        for cand, score in ranked[:top_k]:
            item = dict(cand)
            item["rerank_score"] = float(score)
            out.append(item)
        return out


def _parse_scores(raw: str, n: int) -> list[float]:
    text = raw or ""
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            arr = json.loads(text[start : end + 1])
            if isinstance(arr, list) and len(arr) >= n:
                return [float(x) for x in arr[:n]]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    found = [float(x) for x in _SCORE_RE.findall(text)]
    if len(found) >= n:
        return found[:n]
    return [0.5] * n
