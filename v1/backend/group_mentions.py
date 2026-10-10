"""群聊 @ 解析、主动值掷骰与接话链余额计算。"""

import random
import re

USER_MENTION_LABEL = "用户"
DEFAULT_PROACTIVITY_PCT = 50
DEFAULT_CHAIN_BUDGET_MAX = 5
DEFAULT_GROUP_HISTORY_LIMIT = 40
DEFAULT_GROUP_COMPRESS_KEEP = 6
DEFAULT_GROUP_COMPRESS_THRESHOLD = 85


def normalize_group_meta(meta):
    """补齐群 meta 字段（就地修改并返回）。"""
    if not meta:
        return meta
    meta.setdefault("max_chain_rounds", DEFAULT_CHAIN_BUDGET_MAX)
    meta.setdefault("chain_fast_mode", True)
    meta.setdefault("chain_history_limit", DEFAULT_GROUP_HISTORY_LIMIT)
    meta.setdefault("auto_compress_enabled", False)
    meta.setdefault("auto_compress_threshold", DEFAULT_GROUP_COMPRESS_THRESHOLD)
    settings = meta.setdefault("member_settings", {})
    for bid in meta.get("member_bot_ids") or []:
        s = settings.setdefault(bid, {})
        if "proactivity_pct" not in s:
            s["proactivity_pct"] = int(s.get("auto_mention_pct", DEFAULT_PROACTIVITY_PCT))
        s.setdefault("proactivity_pct", DEFAULT_PROACTIVITY_PCT)
    return meta


def get_chain_budget_max(meta):
    """接话链上限（共用余额初始值）。"""
    return max(0, min(20, int((meta or {}).get("max_chain_rounds") or DEFAULT_CHAIN_BUDGET_MAX)))


def get_member_setting(meta, bot_id):
    settings = (meta or {}).get("member_settings") or {}
    s = settings.get(bot_id) or {}
    pct = s.get("proactivity_pct", s.get("auto_mention_pct", DEFAULT_PROACTIVITY_PCT))
    return {
        "proactivity_pct": max(0, min(100, int(pct))),
    }


def roll_pct(pct):
    p = max(0, min(100, int(pct)))
    if p <= 0:
        return False
    if p >= 100:
        return True
    return random.randint(1, 100) <= p


def has_user_mention(text):
    if not text:
        return False
    return f"@{USER_MENTION_LABEL}" in text


def _escape_name(name):
    return re.escape(name or "")


def parse_bot_mentions(text, member_bots, exclude_bot_id=None):
    """
    从正文解析 @成员名，返回有序去重的 bot_id 列表。
    member_bots: [{id, name, ...}, ...]
    """
    if not text:
        return []
    sorted_bots = sorted(
        member_bots,
        key=lambda b: len(b.get("name") or b.get("id") or ""),
        reverse=True,
    )
    found = []
    seen = set()
    for bot in sorted_bots:
        bid = bot.get("id", "")
        if not bid or bid == exclude_bot_id:
            continue
        name = (bot.get("name") or bid).strip()
        if not name:
            continue
        pattern = re.compile(rf"@{_escape_name(name)}(?!\S)")
        if pattern.search(text):
            if bid not in seen:
                seen.add(bid)
                found.append(bid)
    return found


def supplement_mention_programmatic(speaker_bot_id, member_bots, content):
    """主动值命中且正文无 @ 时，随机 @ 一名其他成员（零 token）。"""
    others = [b for b in member_bots if b.get("id") != speaker_bot_id]
    if not others:
        return content, False
    pick = random.choice(others)
    name = (pick.get("name") or pick.get("id") or "").strip()
    if not name:
        return content, False
    new_text = (content or "").rstrip() + f"\n\n@{name}，你呢？"
    return new_text, True


def process_bot_reply_chain(
    meta,
    speaker_bot_id,
    content,
    chain_state,
    member_bots,
    *,
    is_user_round=False,
):
    """
    Bot 回复后：解析/补 @、扣减接话链余额、生成接话队列。

    chain_state: {remaining_budget: int|None, budget_max: int|None, spoken_bot_ids: [str]}
    is_user_round: 用户 @ 多 Bot 首轮并行阶段，不扣余额、不扩链。
    """
    meta = normalize_group_meta(dict(meta or {}))
    chain_state = dict(chain_state or {})
    budget_max = int(chain_state.get("budget_max") or get_chain_budget_max(meta))
    remaining = chain_state.get("remaining_budget")
    if remaining is None:
        remaining = budget_max
    remaining = max(0, int(remaining))

    text = content or ""
    mention_user = has_user_mention(text)
    supplemented = False
    chain_exhausted = False
    blocked_count = 0

    if is_user_round or len(member_bots) < 2:
        parsed_ids = parse_bot_mentions(text, member_bots, exclude_bot_id=speaker_bot_id)
        return {
            "content": text,
            "mention_user": mention_user,
            "parsed_mention_bot_ids": parsed_ids,
            "queue": [],
            "remaining_budget": remaining,
            "budget_max": budget_max,
            "chain_exhausted": False,
            "supplemented": False,
        }

    parsed_ids = parse_bot_mentions(text, member_bots, exclude_bot_id=speaker_bot_id)
    if not parsed_ids and remaining > 0:
        pct = get_member_setting(meta, speaker_bot_id)["proactivity_pct"]
        if roll_pct(pct):
            text, supplemented = supplement_mention_programmatic(
                speaker_bot_id, member_bots, text
            )
            if supplemented:
                parsed_ids = parse_bot_mentions(text, member_bots, exclude_bot_id=speaker_bot_id)

    queue = []
    queued = set()
    for bid in parsed_ids:
        if bid in queued:
            continue
        if remaining <= 0:
            blocked_count += 1
            chain_exhausted = True
            continue
        queue.append(bid)
        queued.add(bid)
        remaining -= 1

    if blocked_count > 0:
        chain_exhausted = True

    return {
        "content": text,
        "mention_user": mention_user,
        "parsed_mention_bot_ids": parse_bot_mentions(text, member_bots, exclude_bot_id=speaker_bot_id),
        "queue": queue,
        "remaining_budget": remaining,
        "budget_max": budget_max,
        "chain_exhausted": chain_exhausted,
        "supplemented": supplemented,
    }


# 兼容旧调用名
def compute_chain_queue(
    meta,
    speaker_bot_id,
    content,
    chain_state,
    member_bots,
    *,
    is_user_triggered=False,
):
    return process_bot_reply_chain(
        meta,
        speaker_bot_id,
        content,
        chain_state,
        member_bots,
        is_user_round=bool(is_user_triggered),
    )


def build_member_mention_catalog(member_bots):
    """生成可 @ 成员对照表（写入群 system，要求模型严格照抄名字）。"""
    lines = []
    for b in member_bots:
        name = (b.get("name") or b.get("id") or "").strip()
        if not name:
            continue
        lines.append(f"  - @{name}")
    if not lines:
        return "  (none)"
    return "\n".join(lines)


def build_mention_instruction_block(member_bots, chain_enabled=True):
    """群聊 @ 格式说明。"""
    catalog = build_member_mention_catalog(member_bots)
    auto_extra = ""
    if chain_enabled and len(member_bots) >= 2:
        auto_extra = (
            "\nBot reply chain: @MemberName in the body hands off to that member; "
            "each @ costs one slot from the shared chain budget."
        )
    examples = []
    for b in member_bots[:2]:
        name = (b.get("name") or b.get("id") or "").strip()
        if name:
            examples.append(f"@{name}")
    ex_ok = f'"{examples[0]} what do you think?"' if examples else '"@MemberName what do you think?"'
    ex_bad = '"hey BotB" "tell BotC"' if len(examples) < 2 else (
        f'"hey {member_bots[0].get("name", "")}" '
        f'"tell {member_bots[1].get("name", "")}"'
    )
    return (
        "[@ mention format — strict]\n"
        "Only ASCII @ immediately followed by a member name is recognized "
        "(same as the composer @ picker). Colloquial name-only calls are ignored.\n"
        f"Mentionable members (names must match exactly):\n{catalog}\n"
        "Human user: @用户\n"
        f"Valid: {ex_ok}\n"
        f"Invalid: {ex_bad} (no reply chain, no highlight tag)\n"
        "Rules: use @MemberName in the sentence to hand off; never @ yourself; "
        "@用户 is decorative for the human.\n"
        "In history, a [Name] prefix marks that bot's message."
        + auto_extra
    )


def build_auto_interaction_prompt_lines(member_bots=None, auto_interaction_enabled=False):
    if member_bots:
        enabled = auto_interaction_enabled or len(member_bots) >= 2
        return build_mention_instruction_block(member_bots, enabled)
    return (
        "To hand off to another member use @MemberName (exact match to the member list); "
        "for the human use @用户.\n"
        "Colloquial name-only calls are not recognized as @mentions."
    )


def normalize_oral_mentions(text, member_bots, exclude_bot_id=None):
    """
    将常见口语称呼转为 @成员名，便于解析与高亮。
    仅处理尚未带 @ 的称呼模式，避免误伤正常叙述。
    """
    if not text:
        return text
    result = text
    sorted_bots = sorted(
        member_bots,
        key=lambda b: len(b.get("name") or b.get("id") or ""),
        reverse=True,
    )
    for bot in sorted_bots:
        bid = bot.get("id", "")
        if bid == exclude_bot_id:
            continue
        name = (bot.get("name") or bid).strip()
        if not name or f"@{name}" in result:
            continue
        esc = _escape_name(name)
        replacements = [
            (rf"喂[，,\s]*{esc}(?!\S)", f"@{name}"),
            (rf"跟[，,\s]*{esc}(?!\S)", f"@{name}"),
            (rf"对[，,\s]*{esc}[，,\s]*说", f"@{name}"),
            (rf"(?<![@\\w]){esc}[，,:：](?=\s)", f"@{name}，"),
        ]
        for pat, repl in replacements:
            new_result = re.sub(pat, repl, result, count=1)
            if new_result != result:
                result = new_result
                break
    return result
