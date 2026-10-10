"""LLM extraction for knowledge notes."""

from __future__ import annotations

import json
import re
from typing import Any

from ...adapters import providers


EXTRACT_SYSTEM = """你是 MNEMOS 知识整理助手。请从给定资料中提取结构化知识，输出 JSON。
要求：
- title: 简短标题
- summary: 2-4 句摘要
- category: 一个自动分类（中文，简短）
- tags: 3-6 个标签
- key_points: 3-8 条要点
- related_terms: 3-8 个相关概念，用于 [[交叉引用]]
只输出 JSON，不要 markdown 代码块。"""


def _parse_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {}


def _fallback_extract(raw_text: str, title_hint: str = "") -> dict[str, Any]:
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    title = title_hint or (lines[0][:60] if lines else "未命名资料")
    summary = " ".join(lines[:3])[:400] if lines else raw_text[:400]
    return {
        "title": title,
        "summary": summary,
        "category": "未分类",
        "tags": [],
        "key_points": lines[:5],
        "related_terms": [],
    }


def extract_knowledge(profile: dict, raw_text: str, *, title_hint: str = "") -> dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        return _fallback_extract(text, title_hint)
    clipped = text[:12000]
    messages = [
        {"role": "system", "content": EXTRACT_SYSTEM},
        {
            "role": "user",
            "content": f"资料标题提示：{title_hint or '无'}\n\n资料正文：\n{clipped}",
        },
    ]
    try:
        reply = providers.chat_once(profile, messages=messages, max_tokens=1200, timeout=60)
        data = _parse_json(reply)
        if not data.get("title"):
            data["title"] = title_hint or _fallback_extract(text)["title"]
        data.setdefault("summary", "")
        data.setdefault("category", "未分类")
        data.setdefault("tags", [])
        data.setdefault("key_points", [])
        data.setdefault("related_terms", [])
        return data
    except Exception:  # noqa: BLE001
        return _fallback_extract(text, title_hint)
