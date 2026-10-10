"""上下文分层组装 — Prompt Caching 纪律。

固定拼接顺序（缓存匹配物理约束）：
  tools → stable system → semi_stable system → conversation history → dynamic tail

- stable: 人设、固定技能、固定规则（无时间、路径、检索结果、摘要）
- semi_stable: 群成员表、项目概览（hash 未变可复用）
- dynamic: 摘要、记忆、群触发、工作目录、read_files、当前时间 — 合并后前缀到最后一条 user
"""

DYNAMIC_HEADER = "[Session context]"


def join_blocks(blocks):
    """合并非空文本块。"""
    parts = [str(b).strip() for b in blocks if b and str(b).strip()]
    if not parts:
        return ""
    return "\n\n---\n\n".join(parts)


def build_dynamic_context(dynamic_blocks):
    """将 dynamic 层多块合并为单段文本。"""
    body = join_blocks(dynamic_blocks)
    if not body:
        return ""
    return f"{DYNAMIC_HEADER}\n\n{body}"


def prefix_user_content(content, dynamic_text):
    """把动态上下文前缀到 user 消息正文。"""
    if not dynamic_text:
        return content
    base = content if content is not None else ""
    if isinstance(base, list):
        # multimodal: prefix text part
        parts = list(base)
        if parts and parts[0].get("type") == "text":
            parts[0] = {
                **parts[0],
                "text": f"{dynamic_text}\n\n{parts[0].get('text', '')}",
            }
        else:
            parts.insert(0, {"type": "text", "text": dynamic_text})
        return parts
    return f"{dynamic_text}\n\n{base}"


def assemble_api_messages(stable_system, semi_stable_blocks, dynamic_blocks, history_messages):
    """
    组装 OpenAI 兼容 messages 数组。

    history_messages: 已格式化的非 system 对话（user/assistant/tool...）
    dynamic 注入：优先前缀到最后一条 user；若无 user 则末尾追加一条仅含上下文的 user。
    """
    messages = []

    if stable_system and stable_system.strip():
        messages.append({"role": "system", "content": stable_system.strip()})

    semi_text = join_blocks(semi_stable_blocks)
    if semi_text:
        messages.append({"role": "system", "content": semi_text})

    messages.extend(history_messages)

    dynamic_text = build_dynamic_context(dynamic_blocks)
    if not dynamic_text:
        return messages

    last_user_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break

    if last_user_idx is not None:
        msg = dict(messages[last_user_idx])
        msg["content"] = prefix_user_content(msg.get("content"), dynamic_text)
        messages[last_user_idx] = msg
    else:
        messages.append({"role": "user", "content": dynamic_text})

    return messages
