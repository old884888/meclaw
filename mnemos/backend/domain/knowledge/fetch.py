"""Fetch readable text from a user-provided URL."""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urlparse

import requests

try:
    import trafilatura

    HAS_TRAFILATURA = True
except ImportError:  # pragma: no cover
    HAS_TRAFILATURA = False


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _extract_title(html: str) -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if not m:
        return ""
    return unescape(re.sub(r"\s+", " ", m.group(1))).strip()


def fetch_url(url: str, timeout: int = 20) -> dict:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {"ok": False, "title": "", "text": "", "error": "URL 无效，仅支持 http/https"}

    headers = {
        "User-Agent": "MNEMOS/1.0 (+local knowledge ingest)",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url.strip(), headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "title": "", "text": "", "error": f"抓取失败: {exc}"}

    content_type = (resp.headers.get("content-type") or "").lower()
    if "text/plain" in content_type:
        text = resp.text.strip()
        return {"ok": bool(text), "title": url, "text": text, "error": "" if text else "正文为空"}

    html = resp.text
    title = _extract_title(html)
    text = ""
    if HAS_TRAFILATURA:
        text = (trafilatura.extract(html, include_comments=False, include_tables=True) or "").strip()
    if not text:
        text = _strip_html(html)
    if not text:
        return {"ok": False, "title": title or url, "text": "", "error": "未能提取网页正文"}
    return {"ok": True, "title": title or url, "text": text, "error": ""}
