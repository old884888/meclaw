"""专家模式：三轮内部调用的问题解决引擎 + 草稿纸。"""

import os
import json
import re

# ===== 三轮 stage prompt =====

STAGE_SYSTEM = """\
你是一个结构化问题解决专家。你将按照精确的阶段指令工作，输出中间思考产物到 <scratchpad> 标签中。
<scratchpad> 内容不会展示给用户，仅作为你的工作内存。务必认真填写。"""

STAGE1_PROMPT = """\
## Stage 1: 问题解构 (Decomposition)

你的任务是将用户的问题转化为结构清晰、边界明确、根因可追溯的议题。

请依次完成：
1. **Brain Dump** — 列出所有碎片想法、假设、已知事实
2. **Root Cause Tree** — 对核心问题做 5 Whys 根因追溯，区分症状和病因
3. **Stakeholder Map** — 列出受影响方、诉求、潜在冲突
4. **Constraint List** — 硬约束和软约束

将全部产物写入 <scratchpad>，格式如下：

<scratchpad>
## Brain Dump
- ...

## Root Cause Tree
1. Why: ... → Because: ...
2. Why: ... → Because: ...

## Stakeholder Map
| 角色 | 诉求 | 冲突点 |
|------|------|--------|

## Constraints
- 硬约束: ...
- 软约束: ...
</scratchpad>

不要输出其他内容，只输出 <scratchpad> 块。"""

STAGE2_PROMPT = """\
## Stage 2: 方案生成 (Divergence)

你已经完成了问题解构（见上方草稿纸）。现在你的任务是最大化方案多样性，避免被首个可行方案绑架。

请依次完成：
1. **Cross-Domain Analogy** — 从至少 3 个异质领域（生物、军事、经济、生态、工程等）寻找同构问题及解法
2. **Extreme Scenarios** — 回答至少 2 个极端约束场景（预算 1%？1 小时内？禁用现有技术栈？）
3. **Second-Order Thinking** — 对每个初步方案列出直接后果 + 间接后果，识别正反馈/负反馈回路

更新 <scratchpad>，保留 Stage 1 的核心结论，追加 Stage 2 产物。格式：

<scratchpad>
## Stage 1 核心结论
（简要保留 Root Cause 和 Constraints 的关键点）

## Cross-Domain Analogies
1. 领域: ... → 同构问题: ... → 解法启示: ...

## Extreme Scenarios
- 场景1: ... → 破局思路: ...
- 场景2: ... → 破局思路: ...

## Candidate Solutions
### 方案 A: ...
- 直接后果: ...
- 间接后果: ...
- 正反馈回路: ...
- 负反馈回路: ...

### 方案 B: ...
...
</scratchpad>

不要输出其他内容，只输出 <scratchpad> 块。"""

STAGE3_PROMPT = """\
## Stage 3: 收敛与验证 (Convergence)

你已经完成问题解构和方案生成（见上方草稿纸）。现在做出理性选择并设计验证。

请依次完成：
1. **Decision Matrix** — 多维度加权评分（可行性、成本、风险、长期价值、复杂度），禁止仅凭直觉
2. **Pre-mortem** — 假设最终方案已彻底失败，倒推最可能的 3 个死因
3. **MVP Validation** — 设计最小可行验证方案

这次**直接输出最终结论**（不要 <scratchpad> 标签），格式如下：

## 决策分析

### 决策矩阵
| 方案 | 可行性 | 成本 | 风险 | 长期价值 | 综合得分 |
|------|--------|------|------|----------|----------|

### 推荐方案
（明确的结论和可执行建议）

### 事前尸检
如果失败，最可能的 3 个原因：
1. ...
2. ...
3. ...

### 验证计划
（最小可行验证步骤）

---
**置信度**: XX/100
**已知未知**: ...
**偏差警告**: ..."""


def get_scratchpad_path(soul_folder):
    return os.path.join(soul_folder, "memory", "scratchpad.md")


def read_scratchpad(soul_folder):
    path = get_scratchpad_path(soul_folder)
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def write_scratchpad(soul_folder, content):
    path = get_scratchpad_path(soul_folder)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass


def clear_scratchpad(soul_folder):
    write_scratchpad(soul_folder, "")


def parse_scratchpad(text):
    """提取 <scratchpad>...</scratchpad> 内容。"""
    match = re.search(r"<scratchpad>(.*?)</scratchpad>", text, re.DOTALL)
    return match.group(1).strip() if match else ""


def build_stage_messages(user_question, scratchpad_content, stage_prompt, soul_content="", immersion_preamble=""):
    """构建某一轮的 API 消息列表。"""
    system_parts = []
    if immersion_preamble:
        system_parts.append(immersion_preamble)
    if soul_content:
        system_parts.append(soul_content)
    system_parts.append(STAGE_SYSTEM)
    msgs = [{"role": "system", "content": "\n\n---\n\n".join(system_parts)}]
    content_parts = []
    if scratchpad_content:
        content_parts.append(f"[草稿纸]\n{scratchpad_content}")
    content_parts.append(f"[用户问题]\n{user_question}")
    content_parts.append(stage_prompt)
    msgs.append({"role": "user", "content": "\n\n".join(content_parts)})
    return msgs


def _push_stage_token(api_instance, stage_id, token):
    """向前端推送 Stage 流式 token。stage1/2 → 思考区；stage3 → 回答区。"""
    if not token:
        return
    try:
        if stage_id == "stage3":
            api_instance.window.evaluate_js(f"onToken({json.dumps(token)})")
        else:
            payload = json.dumps({"stageId": stage_id, "token": token}, ensure_ascii=False)
            api_instance.window.evaluate_js(f"onExpertStageToken({payload})")
    except Exception:
        pass


def _expert_api_call(api_instance, messages, stage_id=None):
    """专家模式专用 API 调用：流式输出，绕过 bot 的 thinking 设置。"""
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
                return None
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
        if token and token_type in ("content", "reasoning"):
            if token_type == "content":
                full_content += token
            elif stage_id in ("stage1", "stage2") and not full_content:
                full_content += token
            if stage_id:
                _push_stage_token(api_instance, stage_id, token)
        if finish:
            break

    if usage_info and hasattr(api_instance, "_log_cache_usage"):
        api_instance._log_cache_usage(usage_info)

    if full_content:
        return {"choices": [{"message": {"content": full_content}}], "usage": usage_info}

    if provider == "deepseek":
        payload["stream"] = False
    else:
        payload = build_payload(profile, messages, max_tokens, stream=False)

    if hasattr(api_instance, "_post_chat_json"):
        resp = api_instance._post_chat_json(url, payload, headers, stream=False, timeout=120)
        if hasattr(api_instance, "_handle_api_http_error"):
            if api_instance._handle_api_http_error(resp, url, profile):
                return None
    else:
        import requests
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()

    return parse_response(profile, resp.json())


STAGE_META = {
    "stage1": {"label": "问题解构", "icon": "🔍"},
    "stage2": {"label": "方案生成", "icon": "💡"},
    "stage3": {"label": "收敛验证", "icon": "✅"},
}


def _push_stage(api_instance, stage_id, status, content="", scratchpad=""):
    """向前端推送单个 Stage 的状态。"""
    meta = STAGE_META.get(stage_id, {})
    try:
        payload = json.dumps({
            "stageId": stage_id,
            "label": meta.get("label", stage_id),
            "icon": meta.get("icon", "📌"),
            "status": status,
            "content": content,
            "scratchpad": scratchpad,
        }, ensure_ascii=False)
        api_instance.window.evaluate_js(f"onExpertStage({payload})")
    except Exception:
        pass


def run_expert_pipeline(api_instance, user_question, soul_folder, soul_content="", immersion_preamble=""):
    """执行三轮内部调用的专家模式管道，每完成一个 Stage 推送到前端。"""
    stages = [
        ("stage1", STAGE1_PROMPT, True),
        ("stage2", STAGE2_PROMPT, True),
        ("stage3", STAGE3_PROMPT, False),
    ]

    scratchpad = ""
    final_content = ""

    for stage_id, prompt, is_sp in stages:
        if getattr(api_instance, "stop_flag", False):
            _push_stage(api_instance, stage_id, "error", content="已中断")
            return {"content": final_content or "专家模式已被用户中断", "reasoning": scratchpad}

        # 通知 stage 开始
        _push_stage(api_instance, stage_id, "running")

        msgs = build_stage_messages(user_question, scratchpad, prompt, soul_content, immersion_preamble)

        try:
            data = _expert_api_call(api_instance, msgs, stage_id=stage_id)
        except Exception as e:
            _push_stage(api_instance, stage_id, "error", content=str(e))
            return {"content": final_content or f"专家模式执行出错: {e}", "reasoning": scratchpad}

        if not data or not data.get("choices"):
            _push_stage(api_instance, stage_id, "error", content="API 返回空")
            return {"content": final_content or "专家模式 API 请求失败", "reasoning": scratchpad}

        message = data["choices"][0]["message"]
        content = message.get("content") or ""

        if is_sp:
            sp = parse_scratchpad(content)
            if sp:
                scratchpad = sp
                write_scratchpad(soul_folder, sp)
            else:
                scratchpad = content
                write_scratchpad(soul_folder, content)
            # 展示用内容：优先草稿纸 Markdown，避免露出 <scratchpad> 标签
            _push_stage(
                api_instance, stage_id, "done",
                content=scratchpad, scratchpad=scratchpad,
            )
        else:
            final_content = content
            _push_stage(api_instance, stage_id, "done", content=content, scratchpad=scratchpad)

    return {"content": final_content, "reasoning": scratchpad}
