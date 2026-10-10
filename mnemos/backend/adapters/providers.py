"""Minimal provider adapter for MeClaw 2.0 MVP.

Scope:
- generic (OpenAI-compatible)
- anthropic
- optimizations: deepseek (via profile.optimizations, not provider type)

MVP supports text chat streaming with optional separate reasoning streams.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

import requests


VALID_REASONING_LEVELS = frozenset({"off", "low", "medium", "high"})
_ANTHROPIC_THINKING_BUDGET = {"low": 1024, "medium": 4096, "high": 8192}
# DeepSeek only supports high/max; low/medium both map to high per API docs.
_DEEPSEEK_EFFORT_BY_LEVEL = {"low": "high", "medium": "high", "high": "max"}

def _parse_optimizations(value) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = value.replace(",", "\n").split("\n")
    else:
        items = []
    out: list[str] = []
    for item in items:
        name = str(item or "").strip().lower()
        if name and name not in out:
            out.append(name)
    return out


def _model_item_name(item) -> str:
    if isinstance(item, dict):
        for key in ("name", "id", "model"):
            val = str(item.get(key) or "").strip()
            if val:
                return val
        return ""
    return str(item or "").strip()


def _parse_models(value) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = value.replace(",", "\n").split("\n")
    else:
        items = []
    out: list[str] = []
    for item in items:
        name = _model_item_name(item)
        if name and name not in out:
            out.append(name)
    return out


def normalize_profile(profile: dict) -> dict:
    p = dict(profile or {})
    p.setdefault("id", "")
    p.setdefault("name", "")
    p.setdefault("base_url", "")
    p.setdefault("api_key", "")
    p.setdefault("model", "")
    p.setdefault("models", [])
    p.setdefault("provider", "generic")
    p.setdefault("optimizations", [])
    p.setdefault("enabled", True)
    p.setdefault("temperature", None)
    p.setdefault("max_tokens", 4096)
    p.setdefault("max_context", 65536)
    p["enabled"] = bool(p.get("enabled", True))
    try:
        p["max_context"] = int(p.get("max_context") or 65536)
    except (TypeError, ValueError):
        p["max_context"] = 65536
    provider = str(p.get("provider") or "generic").strip().lower()
    if provider == "deepseek":
        opts = _parse_optimizations(p.get("optimizations"))
        if "deepseek" not in opts:
            opts.append("deepseek")
        p["provider"] = "generic"
        p["optimizations"] = opts
    elif provider not in ("generic", "anthropic"):
        p["provider"] = "generic"
    else:
        p["provider"] = provider
    p["optimizations"] = _parse_optimizations(p.get("optimizations"))
    models = _parse_models(p.get("models"))
    if not models:
        models = _parse_models(p.get("model"))
    p["models"] = models
    explicit_model = str(p.get("model") or "").strip()
    if explicit_model and ((not models) or explicit_model in models):
        p["model"] = explicit_model
    elif models:
        p["model"] = models[0]
    else:
        p["model"] = explicit_model
    return p


def profile_models(profile: dict) -> list[str]:
    return list(normalize_profile(profile).get("models") or [])


def profile_optimizations(profile: dict) -> list[str]:
    return list(normalize_profile(profile).get("optimizations") or [])


def has_optimization(profile: dict, name: str) -> bool:
    return name in profile_optimizations(profile)


def normalize_reasoning_level(level: str | None, *, enabled: bool = True) -> str:
    if not enabled:
        return "off"
    lv = str(level or "off").strip().lower()
    if lv not in VALID_REASONING_LEVELS:
        return "off"
    return lv


def effective_reasoning_for_bot(bot: dict | None) -> str:
    if not bot:
        return "off"
    enabled = bool(bot.get("reasoning_enabled", False))
    level = normalize_reasoning_level(bot.get("reasoning_level"), enabled=enabled)
    if not enabled:
        return "off"
    if level == "off":
        return "medium"
    return level


def deepseek_effort_for_level(level: str) -> str:
    return _DEEPSEEK_EFFORT_BY_LEVEL.get(level, "high")


def apply_reasoning_to_payload(payload: dict, profile: dict, level: str) -> None:
    provider = profile.get("provider", "generic")
    is_deepseek = has_optimization(profile, "deepseek")
    if level == "off":
        if is_deepseek:
            if provider == "anthropic":
                payload["thinking"] = {"type": "disabled"}
            else:
                payload["extra_body"] = {"thinking": {"type": "disabled"}}
        return

    if provider == "anthropic":
        if is_deepseek:
            payload["thinking"] = {"type": "enabled"}
            payload["output_config"] = {"effort": deepseek_effort_for_level(level)}
            return
        payload["thinking"] = {
            "type": "enabled",
            "budget_tokens": _ANTHROPIC_THINKING_BUDGET.get(level, 4096),
        }
        return

    if is_deepseek:
        payload["extra_body"] = {"thinking": {"type": "enabled"}}
        payload["reasoning_effort"] = deepseek_effort_for_level(level)
        return

    if level in ("low", "medium", "high"):
        payload["reasoning_effort"] = level

def build_headers(profile: dict) -> dict:
    provider = profile.get("provider", "generic")
    api_key = profile.get("api_key", "")
    if provider == "anthropic":
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def build_endpoint(profile: dict) -> str:
    base = (profile.get("base_url") or "").rstrip("/")
    provider = profile.get("provider", "generic")
    if provider == "anthropic":
        if base.endswith("/v1/messages"):
            return base
        if base.endswith("/messages"):
            return base
        if base.endswith("/v1"):
            return base + "/messages"
        return base + "/v1/messages"
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/chat/completions"


def build_payload(
    profile: dict,
    messages: list[dict],
    max_tokens: int,
    stream: bool,
    *,
    reasoning_level: str = "off",
) -> dict:
    profile = normalize_profile(profile)
    provider = profile.get("provider", "generic")
    model = profile.get("model", "")
    level = normalize_reasoning_level(reasoning_level, enabled=reasoning_level != "off")
    if provider == "anthropic":
        system_text = ""
        chat_messages: list[dict] = []
        for m in messages:
            if m.get("role") == "system":
                system_text = m.get("content", "")
            else:
                chat_messages.append({"role": m.get("role"), "content": m.get("content", "")})
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "stream": stream,
            "messages": chat_messages,
        }
        temp = profile.get("temperature")
        if temp is not None and float(temp) > 0:
            payload["temperature"] = float(temp)
        if system_text:
            payload["system"] = system_text
        apply_reasoning_to_payload(payload, profile, level)
        return payload

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    temp = profile.get("temperature")
    if temp is not None:
        payload["temperature"] = float(temp)
    apply_reasoning_to_payload(payload, profile, level)
    return payload


def redact_api_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "****" + value[-4:]


def parse_cache_usage(usage_info: dict | None) -> dict[str, Any]:
    """Parse provider cache usage fields into a normalised dict.

    Supports OpenAI/DeepSeek and Anthropic field names.
    Returns ``{ read, create, hit_rate, supported }`` where ``supported``
    is False when neither field is present (no error raised).
    """
    if not usage_info or not isinstance(usage_info, dict):
        return {"read": 0, "create": 0, "hit_rate": None, "supported": False}

    def _as_int(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    details = usage_info.get("prompt_tokens_details") or {}
    if not isinstance(details, dict):
        details = {}

    # Prefer explicit cache fields when providers expose them.
    cache_read = _as_int(usage_info.get("cache_read_input_tokens"))
    if cache_read is None:
        cache_read = _as_int(usage_info.get("prompt_cache_hit_tokens"))
    if cache_read is None:
        cache_read = _as_int(details.get("cached_tokens"))

    cache_create = _as_int(usage_info.get("cache_creation_input_tokens"))
    if cache_create is None:
        cache_create = _as_int(usage_info.get("prompt_cache_miss_tokens"))

    # If miss/create is not reported, try deriving it from total prompt/input.
    if cache_create is None and cache_read is not None:
        prompt_total = _as_int(usage_info.get("prompt_tokens"))
        if prompt_total is None:
            prompt_total = _as_int(usage_info.get("input_tokens"))
        if prompt_total is not None:
            cache_create = max(prompt_total - cache_read, 0)

    if cache_read is None and cache_create is None:
        return {"read": 0, "create": 0, "hit_rate": None, "supported": False}

    read = max(cache_read or 0, 0)
    create = max(cache_create or 0, 0)

    if read == 0 and create == 0:
        return {"read": 0, "create": 0, "hit_rate": None, "supported": False}

    hit_rate = None
    if cache_create is not None:
        denom = read + create
        hit_rate = round(read / denom * 100, 1) if denom else 0.0

    return {
        "read": read,
        "create": create,
        "hit_rate": hit_rate,
        "supported": True,
    }


def _parse_openai_sse_line(
    raw_line: str, usage_collector: dict[str, Any] | None = None
) -> tuple[tuple[str, str] | None, bool]:
    if not raw_line.startswith("data: "):
        return None, False
    data_str = raw_line[6:].strip()
    if data_str == "[DONE]":
        return None, True
    try:
        data = json.loads(data_str)
    except json.JSONDecodeError:
        return None, False
    if usage_collector is not None and data.get("usage"):
        usage_collector.update(data["usage"])
    choice = (data.get("choices") or [{}])[0]
    delta = choice.get("delta") or {}
    reasoning = delta.get("reasoning_content") or ""
    content = delta.get("content") or delta.get("text") or ""
    finish = bool(choice.get("finish_reason"))
    if reasoning:
        return ("reasoning", reasoning), finish
    if content:
        return ("content", content), finish
    return None, finish


def _parse_anthropic_sse_line(
    raw_line: str, usage_collector: dict[str, Any] | None = None
) -> tuple[tuple[str, str] | None, bool]:
    if not raw_line.startswith("data: "):
        return None, False
    data_str = raw_line[6:].strip()
    try:
        data = json.loads(data_str)
    except json.JSONDecodeError:
        return None, False
    evt_type = data.get("type", "")
    if usage_collector is not None and data.get("usage"):
        for k, v in data["usage"].items():
            if k in usage_collector:
                usage_collector[k] = (usage_collector.get(k) or 0) + (v or 0)
            else:
                usage_collector[k] = v or 0
    if evt_type == "message_stop":
        return None, True
    if evt_type == "content_block_delta":
        delta = data.get("delta") or {}
        dtype = delta.get("type") or ""
        if dtype == "thinking_delta":
            text = delta.get("thinking") or ""
            if text:
                return ("reasoning", text), False
        if dtype == "text_delta":
            text = delta.get("text") or ""
            if text:
                return ("content", text), False
    return None, False


def _post_json(url: str, payload: dict, headers: dict, stream: bool = False, timeout: int = 120):
    """Serialize payload with deterministic key order for stable prefix caching."""
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return requests.post(url, data=body, headers=headers, stream=stream, timeout=timeout)


def stream_chat_parts(
    profile: dict,
    messages: list[dict],
    max_tokens: int,
    stop_event,
    timeout: int = 120,
    usage_collector: dict[str, Any] | None = None,
    *,
    reasoning_level: str = "off",
    response_holder: dict[str, Any] | None = None,
) -> Iterable[tuple[str, str]]:
    """Yield ``(kind, text)`` stream parts where kind is ``content`` or ``reasoning``."""
    profile = normalize_profile(profile)
    endpoint = build_endpoint(profile)
    headers = build_headers(profile)
    payload = build_payload(
        profile,
        messages,
        max_tokens=max_tokens,
        stream=True,
        reasoning_level=reasoning_level,
    )

    response = _post_json(endpoint, payload, headers, stream=True, timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(format_http_error(response.status_code, response.text))

    if response_holder is not None:
        response_holder["response"] = response

    is_anthropic = profile.get("provider") == "anthropic"
    parser = _parse_anthropic_sse_line if is_anthropic else _parse_openai_sse_line

    try:
        for line in response.iter_lines(decode_unicode=True):
            if stop_event.is_set():
                break
            if not line:
                continue
            part, finish = parser(line, usage_collector)
            if part:
                yield part
            if finish:
                break
    finally:
        if response_holder is not None:
            response_holder.pop("response", None)
        response.close()


def stream_chat(
    profile: dict,
    messages: list[dict],
    max_tokens: int,
    stop_event,
    timeout: int = 120,
    usage_collector: dict[str, Any] | None = None,
    *,
    reasoning_level: str = "off",
) -> Iterable[str]:
    """Yield answer content tokens from provider stream."""
    for kind, token in stream_chat_parts(
        profile,
        messages,
        max_tokens=max_tokens,
        stop_event=stop_event,
        timeout=timeout,
        usage_collector=usage_collector,
        reasoning_level=reasoning_level,
    ):
        if kind == "content":
            yield token


def chat_once(profile: dict, messages: list[dict], max_tokens: int, timeout: int = 30) -> str:
    """Non-stream call, mainly for test connection."""
    profile = normalize_profile(profile)
    endpoint = build_endpoint(profile)
    headers = build_headers(profile)
    payload = build_payload(profile, messages, max_tokens=max_tokens, stream=False)
    response = _post_json(endpoint, payload, headers, stream=False, timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(format_http_error(response.status_code, response.text))
    data = response.json()
    if profile.get("provider") == "anthropic":
        blocks = data.get("content") or []
        return "".join((b.get("text") or "") for b in blocks if b.get("type") == "text")
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return msg.get("content", "") or ""


def format_http_error(status_code: int, response_text: str) -> str:
    snippet = (response_text or "").strip()[:500]
    if status_code == 401:
        return "API Key 无效，请检查配置"
    if status_code == 404:
        return "请求 404，请检查 Base URL 与模型名称"
    return f"API 返回 {status_code}: {snippet}"

