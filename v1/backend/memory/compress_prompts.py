"""会话摘要详略：压缩上下文时的 prompt 模板。"""

VALID_DETAIL_LEVELS = ("minimal", "standard", "detailed", "max")

DETAIL_LEVEL_LABELS = {
    "minimal": "极简",
    "standard": "标准",
    "detailed": "详尽",
    "max": "琐碎 max",
}

_DEFAULT_DIRECTION = "保留关键信息、决定、结论和重要细节。"

_LEVEL_INSTRUCTIONS = {
    "minimal": (
        "请将以下对话压缩为极简摘要。\n"
        "要求：3～6 条 bullet，删除寒暄与重复；只保留对后续对话必需的信息；尽量最短。"
    ),
    "standard": (
        "请将以下对话压缩为简洁的摘要。\n"
        "要求：保留关键信息、决定、结论和重要细节；适度精简，不要复述全文。"
    ),
    "detailed": (
        "请将以下对话压缩为结构化摘要。\n"
        "要求：使用清晰小节，建议包含【背景】【要点】【已做决定】【结论】【待定事项】；\n"
        "保留比标准档更多细节，但仍避免粘贴整段对话原文。"
    ),
    "max": (
        "请将以下对话压缩为详尽、偏琐碎的结构化摘要。\n"
        "要求：按话题分小节列出尽量完整的要点（可多至 10～15 条）；\n"
        "可摘录 3～8 句对后续写作或讨论有价值的原话（用引号标出）；\n"
        "优先完整性，但仍禁止整段粘贴聊天记录。"
    ),
}


def normalize_detail_level(level):
    if level in VALID_DETAIL_LEVELS:
        return level
    return "standard"


def resolve_compress_summary_detail(config, bot, override=None):
    """解析摘要详略：手动 override > bot 覆盖 > 全局 > standard。"""
    if override is not None and str(override).strip():
        return normalize_detail_level(str(override).strip())
    if bot and bot.get("compress_summary_detail") is not None:
        val = bot.get("compress_summary_detail")
        if val:
            return normalize_detail_level(val)
    if config:
        return normalize_detail_level(config.get("compress_summary_detail", "standard"))
    return "standard"


def build_compress_prompt(conversation_text, direction_text="", detail_level="standard"):
    level = normalize_detail_level(detail_level)
    header = _LEVEL_INSTRUCTIONS[level]
    direction = (direction_text or "").strip() or _DEFAULT_DIRECTION
    return (
        f"{header}\n"
        f"压缩方向：{direction}\n\n"
        f"摘要将作为后续对话的上下文使用，确保不丢失对后续对话有用的信息。\n\n"
        f"对话内容：\n{conversation_text}\n请输出摘要："
    )
