"""Context assembly discipline — Prompt Caching constraint for 2.0 multi-brain.

Fixed assembly order (cache-matching physical constraint):
  stable system → semi_stable system → conversation history → dynamic tail

- stable:      base system prompt + persona block (byte-stable across turns)
- semi_stable: reserved for project overview / group roster (empty in base 2.0)
- history:     user / assistant conversation turns
- dynamic:     memory retrieval, cognitive block, session summary, current time
               → merged into one segment and prefixed onto the last user message

Dynamic content is intentionally kept OUT of early system messages so that the
stable prefix can be reused by provider-side Prompt Caching / KV cache.
"""

from __future__ import annotations

DYNAMIC_HEADER = "[Session context]"


def join_blocks(blocks: list) -> str:
    """Merge non-empty text blocks with a separator."""
    parts = [str(b).strip() for b in blocks if b and str(b).strip()]
    if not parts:
        return ""
    return "\n\n---\n\n".join(parts)


def build_dynamic_context(dynamic_blocks: list) -> str:
    """Merge dynamic layer blocks into a single labelled segment."""
    body = join_blocks(dynamic_blocks)
    if not body:
        return ""
    return f"{DYNAMIC_HEADER}\n\n{body}"


def prefix_user_content(content, dynamic_text: str):
    """Prepend dynamic context onto a user message's content.

    Handles plain strings and multimodal lists (OpenAI vision format).
    Returns the same type as *content*.
    """
    if not dynamic_text:
        return content
    base = content if content is not None else ""
    if isinstance(base, list):
        parts = list(base)
        if parts and isinstance(parts[0], dict) and parts[0].get("type") == "text":
            parts[0] = {
                **parts[0],
                "text": f"{dynamic_text}\n\n{parts[0].get('text', '')}",
            }
        else:
            parts.insert(0, {"type": "text", "text": dynamic_text})
        return parts
    return f"{dynamic_text}\n\n{base}"


def assemble_api_messages(
    stable_system: str,
    semi_stable_blocks: list,
    dynamic_blocks: list,
    history_messages: list[dict],
) -> list[dict]:
    """Assemble an OpenAI-compatible messages list.

    Parameters
    ----------
    stable_system:
        The fully stable system prompt (base prompt + persona).  Should not
        contain any per-turn derived content.
    semi_stable_blocks:
        Optional blocks for content that changes infrequently (e.g. group
        roster, project overview).  Reserved / empty in base 2.0.
    dynamic_blocks:
        Per-turn dynamic content (memory retrieval, cognitive, summary, time).
        These are merged and injected as a prefix onto the last user message
        rather than inserted as an early system message.
    history_messages:
        Formatted user / assistant conversation turns (no system roles).
    """
    messages: list[dict] = []

    if stable_system and stable_system.strip():
        messages.append({"role": "system", "content": stable_system.strip()})

    semi_text = join_blocks(semi_stable_blocks)
    if semi_text:
        messages.append({"role": "system", "content": semi_text})

    messages.extend(history_messages)

    dynamic_text = build_dynamic_context(dynamic_blocks)
    if not dynamic_text:
        return messages

    last_user_idx: int | None = None
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
