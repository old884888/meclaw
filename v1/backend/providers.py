"""API 供应商适配层：统一 OpenAI / Anthropic / DeepSeek 的请求与响应格式。"""

import json
import requests


def build_headers(profile):
    """根据 provider 构建请求 headers。"""
    provider = profile.get("provider", "generic")
    api_key = profile.get("api_key", "")

    if provider == "anthropic":
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
    # OpenAI / DeepSeek / generic
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def build_endpoint(profile):
    """根据 provider 返回完整的 API endpoint URL。"""
    base = profile.get("base_url", "").rstrip("/")
    provider = profile.get("provider", "generic")

    if provider == "anthropic":
        # Anthropic: base_url 可能已含 /v1，也可能不含
        if base.endswith("/v1"):
            return base + "/messages"
        if base.endswith("/v1/messages"):
            return base
        return base + "/v1/messages"
    # OpenAI / DeepSeek / generic
    return base + "/chat/completions"


def build_payload(profile, messages, max_tokens, stream=False, tools=None):
    """根据 provider 构建请求 body。

    Args:
        profile: API 配置
        messages: OpenAI 格式的消息列表 [{"role": "system"/"user"/"assistant", "content": "..."}]
        max_tokens: 最大输出 token
        stream: 是否流式
        tools: 工具列表（可选）
    """
    provider = profile.get("provider", "generic")
    model = profile.get("model", "")

    if provider == "anthropic":
        return _build_anthropic_payload(profile, messages, model, max_tokens, stream, tools)
    elif provider == "deepseek":
        return _build_deepseek_payload(profile, messages, model, max_tokens, stream, tools)
    else:
        return _build_openai_payload(profile, messages, model, max_tokens, stream, tools)


def _build_anthropic_payload(profile, messages, model, max_tokens, stream, tools):
    """Anthropic Messages API 格式。"""
    # 提取 system 消息
    system_text = ""
    chat_messages = []
    for m in messages:
        if m.get("role") == "system":
            system_text = m.get("content", "")
        else:
            chat_messages.append(m)

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if system_text:
        payload["system"] = system_text
    payload["messages"] = chat_messages

    # Anthropic 不支持 temperature=0（最低 1），且 thinking 模式不支持 temperature
    temp = profile.get("temperature")
    if temp is not None and temp > 0:
        payload["temperature"] = float(temp)

    if tools:
        # Anthropic tool 格式略有不同
        anthropic_tools = []
        for t in tools:
            at = {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "input_schema": t.get("parameters", {}),
            }
            anthropic_tools.append(at)
        payload["tools"] = anthropic_tools

    return payload


def _build_openai_payload(profile, messages, model, max_tokens, stream, tools):
    """OpenAI 兼容格式。"""
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    temp = profile.get("temperature")
    if temp is not None:
        payload["temperature"] = float(temp)
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    return payload


def _build_deepseek_payload(profile, messages, model, max_tokens, stream, tools):
    """DeepSeek 格式（含 thinking 模式）。"""
    payload = _build_openai_payload(profile, messages, model, max_tokens, stream, tools)
    # DeepSeek thinking 模式需要 extra_body
    # 这里不处理，由调用方决定是否添加
    return payload


def parse_response(profile, data):
    """统一解析 API 响应为 OpenAI 格式。

    返回 {"choices": [{"message": {"content": "..."}}], "usage": {...}}
    """
    provider = profile.get("provider", "generic")

    if provider == "anthropic":
        return _parse_anthropic_response(data)
    # OpenAI / DeepSeek / generic: 直接返回
    return data


def _parse_anthropic_response(data):
    """将 Anthropic 响应转换为 OpenAI 格式。"""
    content_blocks = data.get("content", [])
    text_parts = []
    for block in content_blocks:
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    content = "".join(text_parts)

    usage = data.get("usage", {})
    openai_usage = {
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
    }

    return {
        "choices": [{
            "message": {"content": content, "role": "assistant"},
            "finish_reason": data.get("stop_reason", "stop"),
        }],
        "usage": openai_usage,
    }


def parse_stream_line(profile, line_str):
    """解析一行 SSE 数据，返回 (token_text, finish_reason, usage, raw_data, token_type)。

    token_type: "content" | "reasoning" | None
    对于 Anthropic，一行可能包含多个事件类型。
    对于 OpenAI，一行是 "data: {...}" 格式。
    """
    provider = profile.get("provider", "generic")

    if provider == "anthropic":
        return _parse_anthropic_stream_line(line_str)
    else:
        return _parse_openai_stream_line(line_str)


def _parse_openai_stream_line(line_str):
    """解析 OpenAI SSE 行。返回 (token, finish, usage, data, token_type)。"""
    if not line_str.startswith("data: "):
        return None, None, None, None, None
    data_str = line_str[6:].strip()
    if data_str == "[DONE]":
        return None, "stop", None, None, None
    try:
        data = json.loads(data_str)
        choice = data.get("choices", [{}])[0]
        delta = choice.get("delta", {})
        finish = choice.get("finish_reason")
        usage = data.get("usage")

        # DeepSeek reasoning_content / thinking
        reasoning = delta.get("reasoning_content", "") or delta.get("thinking", "")
        if reasoning:
            return reasoning, finish, usage, data, "reasoning"

        token = delta.get("content", "") or delta.get("text", "")
        if token:
            return token, finish, usage, data, "content"

        return None, finish, usage, data, None
    except (json.JSONDecodeError, KeyError, IndexError):
        return None, None, None, None, None


def _parse_anthropic_stream_line(line_str):
    """解析 Anthropic SSE 行。返回 (token, finish, usage, data, token_type)。

    Anthropic SSE 格式:
    event: content_block_delta
    data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"..."}}

    event: message_stop
    data: {"type":"message_stop"}
    """
    if line_str.startswith("data: "):
        data_str = line_str[6:].strip()
        try:
            data = json.loads(data_str)
            evt_type = data.get("type", "")

            if evt_type == "content_block_delta":
                delta = data.get("delta", {})
                if delta.get("type") == "text_delta":
                    return delta.get("text", ""), None, None, data, "content"
                # thinking_delta (Anthropic extended thinking)
                if delta.get("type") == "thinking_delta":
                    return delta.get("thinking", ""), None, None, data, "reasoning"
            elif evt_type == "message_stop":
                return None, "stop", None, data, None
            elif evt_type == "message_delta":
                usage = data.get("usage", {})
                return None, None, {
                    "prompt_tokens": 0,
                    "completion_tokens": usage.get("output_tokens", 0),
                    "total_tokens": usage.get("output_tokens", 0),
                }, data, None
        except (json.JSONDecodeError, KeyError):
            pass
    return None, None, None, None, None


def supports_reasoning(profile):
    """判断当前 profile 是否支持推理（thinking）模式。"""
    provider = profile.get("provider", "generic")
    if provider == "deepseek":
        return True
    # Anthropic 支持 extended thinking（但需要特殊处理）
    return False


def supports_tools(profile):
    """判断当前 profile 是否支持工具调用。"""
    provider = profile.get("provider", "generic")
    # Anthropic 和 OpenAI 都支持 tools
    return True


def normalize_profile(profile):
    """确保 profile 包含所有必要字段。"""
    profile.setdefault("id", "default")
    profile.setdefault("name", "")
    profile.setdefault("base_url", "")
    profile.setdefault("api_key", "")
    profile.setdefault("model", "")
    profile.setdefault("provider", "generic")
    profile.setdefault("temperature", 0.7)
    profile.setdefault("max_tokens", 4096)
    profile.setdefault("max_context", 65536)
    profile.setdefault("models", [])
    profile.setdefault("enabled", True)
    profile.setdefault("balance", {})
    return profile


def normalize_all_profiles(raw):
    """规范化配置中所有 API profiles。"""
    for p in raw.get("api_profiles", []):
        normalize_profile(p)


def fetch_profile_balance(profile):
    """查询供应商账户余额（仅支持部分供应商）。"""
    provider = profile.get("provider", "generic")
    base_url = profile.get("base_url", "").rstrip("/")
    api_key = profile.get("api_key", "")

    if not base_url or not api_key:
        return {"ok": False, "msg": "缺少 base_url 或 api_key"}

    try:
        import requests
        if provider == "deepseek":
            # DeepSeek 余额接口
            resp = requests.get(
                f"{base_url}/user/balance",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                balance = data.get("balance", {})
                return {
                    "ok": True,
                    "value": balance.get("total_balance", "N/A"),
                    "currency": balance.get("currency", "USD"),
                }
            return {"ok": False, "msg": f"查询失败: {resp.status_code}"}
        else:
            return {"ok": False, "msg": f"当前供应商 {provider} 不支持余额查询"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}
