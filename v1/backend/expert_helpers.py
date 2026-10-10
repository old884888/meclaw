"""专家模式 / 专家会议共用的流式调用与解析工具。"""

import json
import re


def parse_confidence_basis(text):
    """从输出文本解析 Confidence(0-100) 与 Basis。缺失时给默认值。"""
    raw = text or ""
    confidence = 50
    basis = "假设"

    m = re.search(r"(?:置信度|Confidence)\s*[:：]\s*(\d{1,3})", raw, re.I)
    if m:
        try:
            confidence = max(0, min(100, int(m.group(1))))
        except ValueError:
            pass

    bm = re.search(r"(?:依据|Basis)\s*[:：]\s*([^\n]+)", raw, re.I)
    if bm:
        val = bm.group(1).strip()
        for label in ("推理", "事实", "假设", "类比", "reasoning", "fact", "assumption", "analogy"):
            if label.lower() in val.lower() or label in val:
                basis = {"reasoning": "推理", "fact": "事实", "assumption": "假设", "analogy": "类比"}.get(
                    label.lower(), label if label in ("推理", "事实", "假设", "类比") else basis
                )
                break
        else:
            basis = val[:20] if val else basis

    return {"confidence": confidence, "basis": basis}


def stream_chat_completion(api_instance, messages, on_token=None):
    """流式 API 调用，返回完整 content。on_token(token) 可选回调。"""
    from .providers import build_endpoint, build_headers, build_payload, parse_response, parse_stream_line

    profile = api_instance.get_active_profile()
    max_tokens = int(profile.get("max_tokens", 4096))
    provider = profile.get("provider", "generic")

    if provider == "deepseek":
        payload = {
            "model": profile["model"],
            "messages": messages,
            "temperature": float(profile.get("temperature", 0.7)),
            "max_tokens": max_tokens,
            "stream": True,
            "extra_body": {"thinking": {"type": "disabled"}},
        }
    else:
        payload = build_payload(profile, messages, max_tokens, stream=True)

    url = build_endpoint(profile)
    headers = build_headers(profile)
    if hasattr(api_instance, "_post_chat_json"):
        resp = api_instance._post_chat_json(url, payload, headers, stream=True, timeout=120)
        if hasattr(api_instance, "_handle_api_http_error"):
            if api_instance._handle_api_http_error(resp, url, profile):
                return ""
    else:
        import requests
        resp = requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
        resp.raise_for_status()

    full_content = ""
    usage_info = None
    for line in resp.iter_lines():
        if getattr(api_instance, "stop_flag", False):
            break
        if not line:
            continue
        line_str = line.decode("utf-8")
        token, finish, usage, _raw, token_type = parse_stream_line(profile, line_str)
        if usage:
            usage_info = usage
        if token and token_type == "content":
            full_content += token
            if on_token:
                on_token(token)
        if finish:
            break

    if usage_info and hasattr(api_instance, "_log_cache_usage"):
        api_instance._log_cache_usage(usage_info)

    if full_content:
        return full_content

    if provider == "deepseek":
        payload["stream"] = False
    else:
        payload = build_payload(profile, messages, max_tokens, stream=False)
    if hasattr(api_instance, "_post_chat_json"):
        resp = api_instance._post_chat_json(url, payload, headers, stream=False, timeout=120)
        if hasattr(api_instance, "_handle_api_http_error"):
            if api_instance._handle_api_http_error(resp, url, profile):
                return ""
    else:
        import requests
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
    data = parse_response(profile, resp.json())
    if data and data.get("choices"):
        return data["choices"][0]["message"].get("content") or ""
    return ""


class AppendOnlyStore:
    """冻结+追加式存储：只追加段落，不整块覆盖。"""

    def __init__(self, initial=""):
        self._sections = []
        if initial and initial.strip():
            self._sections.append(initial.strip())

    def append(self, text, header=None):
        block = (text or "").strip()
        if not block:
            return
        if header:
            block = f"## {header}\n{block}"
        self._sections.append(block)

    def read(self):
        return "\n\n".join(self._sections)

    def clear(self):
        self._sections = []
