import json
import os
import re
from datetime import datetime

from . import indexer
from .store import (
    append_memory_md_line,
    entries_dir,
    list_entries,
    list_items,
    read_entry,
    write_entry,
    write_item,
)

VALID_TYPES = {"fact", "preference", "project", "relationship", "quote", "document"}

LOW_QUALITY_PATTERNS = (
    r"用户今天",
    r"问了一个问题",
    r"进行了对话",
    r"聊天",
    r"天气",
    r"你好",
    r"谢谢",
)

JOKE_OR_RIDDLE_PATTERNS = (
    r"什么.+好吃",
    r"你知道吗",
    r"猜猜",
    r"谜语",
    r"鞋垫",
    r"孜然",
    r"记住哦\s*$",
    r"知道吗\s*$",
)


def _normalize(text):
    return re.sub(r"\s+", "", (text or "").lower())


def is_similar_to_existing(content, existing_items, threshold=0.75):
    norm = _normalize(content)
    if len(norm) < 4:
        return True
    for item in existing_items:
        other = _normalize(item.get("content", ""))
        if not other:
            continue
        if norm in other or other in norm:
            shorter, longer = (norm, other) if len(norm) <= len(other) else (other, norm)
            if len(shorter) / max(len(longer), 1) >= threshold:
                return True
    return False


def is_low_quality(candidate):
    content = (candidate.get("content") or "").strip()
    item_type = candidate.get("type", "fact")
    if len(content) < 6:
        return True
    action = (candidate.get("action") or "add").lower()
    if action == "ignore":
        return True
    if float(candidate.get("confidence", 0)) < 0.5:
        return True
    for pat in LOW_QUALITY_PATTERNS:
        if re.search(pat, content):
            if item_type not in ("preference", "fact"):
                return True
    for pat in JOKE_OR_RIDDLE_PATTERNS:
        if re.search(pat, content, re.IGNORECASE):
            return True
    # 自动提取的 quote 需高重要度，好句以用户手动收藏为主
    if item_type == "quote" and int(candidate.get("importance", 3)) < 4:
        return True
    return False


def parse_extraction_response(text):
    """Legacy: parse JSON array response."""
    text = (text or "").strip()
    if not text:
        return []
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return []


def parse_entry_response(text):
    """Parse Markdown entry response from LLM into structured data."""
    text = (text or "").strip()
    if not text:
        return None
    from .store import _parse_yaml_frontmatter, _parse_markdown_sections
    meta, body = _parse_yaml_frontmatter(text)
    title, summary, points, keywords_str = _parse_markdown_sections(body)
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()] if keywords_str else []
    related = meta.get("related", [])
    if isinstance(related, str):
        related = [r.strip() for r in related.split(",") if r.strip()]
    return {
        "title": title or "untitled",
        "type": meta.get("type", "fact"),
        "importance": int(meta.get("importance", 3)),
        "keywords": keywords,
        "related": related,
        "summary": summary,
        "points": points,
        "action": "add" if summary and points else "ignore",
    }


EXTRACTION_PROMPT = """请从以下对话片段中写一篇记忆文档（只输出 Markdown，不要其他文字）。

要求：
1. 摘要（3-5 句话，概括整个对话的核心内容、讨论过程和结论）
2. 要点（3-8 条，从摘要中提取关键决策、代码改动、技术选型等具体信息点）
3. 关键词（5-10 个标签用于检索匹配）
4. related：如果本次对话与近期其他对话有明显的因果或并列关系，列出相关 entry 文件名；没有则留空

不要记临时寒暄、单次提问、不确定内容、玩笑、谜语、段子。
明确偏好、长期项目、反复出现的习惯、重要事实才记。

输出格式（严格遵守，不要多余文字）：
---
type: preference|fact|project|relationship
importance: 1-5
keywords: [关键词1, 关键词2, ...]
related: [关联entry文件名1, 关联entry文件名2]
---

# 标题

## 摘要
（3-5 句话）

## 要点
- 要点1
- 要点2

## 关键词
关键词1, 关键词2, 关键词3

对话内容：
{conversation}
"""

EXTRACTION_PROMPT_MAX_QUOTES = """请从以下对话片段中写一篇记忆文档（只输出 Markdown，不要其他文字）。

要求：
1. 摘要（3-5 句话，概括整个对话的核心内容、讨论过程和结论）
2. 要点（3-8 条，从摘要中提取关键决策、代码改动、技术选型等具体信息点）
3. 关键词（5-10 个标签用于检索匹配）
4. related：如果本次对话与近期其他对话有明显的因果或并列关系，列出相关 entry 文件名；没有则留空
5. 可额外在要点中包含最多 3 条精彩、可复用的原话摘录（标注 [quote]）

不要记临时寒暄、单次提问、不确定内容、玩笑、谜语、段子。
明确偏好、长期项目、反复出现的习惯、重要事实才记。

输出格式（严格遵守，不要多余文字）：
---
type: preference|fact|project|relationship|quote
importance: 1-5
keywords: [关键词1, 关键词2, ...]
related: [关联entry文件名1, 关联entry文件名2]
---

# 标题

## 摘要
（3-5 句话）

## 要点
- 要点1
- 要点2
- [quote] 精彩原话摘录

## 关键词
关键词1, 关键词2, 关键词3

对话内容：
{conversation}
"""


def build_extraction_prompt(conversation_text, detail_level="standard"):
    if detail_level == "max":
        return EXTRACTION_PROMPT_MAX_QUOTES.format(conversation=conversation_text)
    return EXTRACTION_PROMPT.format(conversation=conversation_text)


def extract_candidates(call_api_sync, conversation_text, detail_level="standard"):
    """Extract memory candidates. Returns (is_entry, data) tuple."""
    prompt = build_extraction_prompt(conversation_text, detail_level)
    raw = call_api_sync([{"role": "user", "content": prompt}])
    # Try new Markdown entry format first
    entry = parse_entry_response(raw)
    if entry and entry.get("action") == "add":
        return True, entry
    # Fallback to legacy JSON format
    legacy = parse_extraction_response(raw)
    return False, legacy


def apply_entry(soul_folder, entry_data, session_id=""):
    """Apply a single entry (new Markdown format) to memory."""
    from .store import append_entry_index_line

    entry_type = entry_data.get("type", "fact")
    if entry_type not in VALID_TYPES or entry_type == "document":
        entry_type = "fact"

    summary = (entry_data.get("summary") or "").strip()
    points = entry_data.get("points") or []
    if not summary or not points:
        return {"written": 0, "merged_md": 0, "skipped": 1}

    # Check similarity against existing entries
    existing_entries = list_entries(soul_folder, limit=50)
    existing_summaries = [{"content": e.get("summary", "")} for e in existing_entries]
    if is_similar_to_existing(summary, existing_summaries):
        return {"written": 0, "merged_md": 0, "skipped": 1}

    result = write_entry(soul_folder, {
        "title": entry_data.get("title", "untitled"),
        "type": entry_type,
        "importance": entry_data.get("importance", 3),
        "keywords": entry_data.get("keywords", []),
        "related": entry_data.get("related", []),
        "summary": summary,
        "points": points,
    })
    if not result:
        return {"written": 0, "merged_md": 0, "skipped": 1}

    indexer.index_after_entry_write(soul_folder, result["file_path"])

    # Update memory.md with index entry
    today = datetime.now().strftime("%Y-%m-%d")
    title = entry_data.get("title", "untitled")
    desc = summary[:60] + ("..." if len(summary) > 60 else "")
    filename = result["filename"]
    md_line = f"- {today} [{title}](entries/{filename}) — {desc}"
    md_result = append_entry_index_line(soul_folder, md_line)
    merged_md = 1 if md_result.get("ok") and not md_result.get("skipped") else 0

    return {"written": 1, "merged_md": merged_md, "skipped": 0}


def apply_candidates(soul_folder, candidates, session_id="", max_quotes=0):
    """Legacy: apply JSON array candidates to memory."""
    existing = list_items(soul_folder, limit=200)
    written = 0
    merged_md = 0
    skipped = 0
    quote_written = 0
    today = datetime.now().strftime("%Y-%m-%d")

    for cand in candidates:
        if cand.get("type") == "document":
            skipped += 1
            continue
        item_type = cand.get("type", "fact")
        if item_type not in VALID_TYPES or item_type == "document":
            item_type = "fact"
        if item_type == "quote":
            if max_quotes <= 0 or quote_written >= max_quotes:
                skipped += 1
                continue
        if is_low_quality(cand):
            skipped += 1
            continue
        content = (cand.get("content") or "").strip()
        if is_similar_to_existing(content, existing):
            skipped += 1
            continue

        record, path = write_item(soul_folder, {
            "type": item_type,
            "content": content,
            "summary": cand.get("summary", ""),
            "keywords": cand.get("keywords", []),
            "importance": cand.get("importance", 3),
            "confidence": cand.get("confidence", 0.8),
            "source_session_id": session_id,
        })
        if not record:
            skipped += 1
            continue
        indexer.index_after_write(soul_folder, path)
        existing.append(record)
        written += 1
        if item_type == "quote":
            quote_written += 1

        importance = int(cand.get("importance", 3))
        confidence = float(cand.get("confidence", 0.8))
        if (
            item_type in ("fact", "preference")
            and importance >= 4
            and confidence >= 0.8
        ):
            line = f"- [{today}] {content}"
            result = append_memory_md_line(soul_folder, line)
            if result.get("ok") and not result.get("skipped"):
                merged_md += 1

    return {"written": written, "merged_md": merged_md, "skipped": skipped}


def run_memory_extraction(api, conversation_text, session_id="", detail_level="standard"):
    """Run extraction pipeline using api._call_api_sync and active bot soul folder."""
    soul_folder = ""
    if hasattr(api, "_resolve_memory_store_folder"):
        soul_folder = api._resolve_memory_store_folder() or ""
    if not soul_folder:
        bot = api.get_active_bot()
        soul_folder = api.resolve_app_path(bot.get("soul_folder", ""))
    if not soul_folder or not os.path.isdir(soul_folder):
        os.makedirs(soul_folder, exist_ok=True) if soul_folder else None
    if not soul_folder:
        return {"ok": False, "msg": "未配置灵魂文件夹"}

    from .store import ensure_layout
    ensure_layout(soul_folder)

    def _organizer_sync(msgs):
        return api._call_api_sync(msgs, use_organizer=True)

    is_entry, data = extract_candidates(_organizer_sync, conversation_text, detail_level)
    if is_entry:
        stats = apply_entry(soul_folder, data, session_id)
        return {"ok": True, **stats, "candidates": 1}
    else:
        max_quotes = 3 if detail_level == "max" else 0
        stats = apply_candidates(soul_folder, data, session_id, max_quotes=max_quotes)
        return {"ok": True, **stats, "candidates": len(data)}
