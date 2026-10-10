"""Topic keys, polarity, and evolution metadata for L1 atoms."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from ...storage.common import now_iso
from .paths import BotMemoryPaths

TOPIC_KEY_HINTS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"咖啡|茶|饮|喝|beverage|coffee|tea|drink|wine|beer|juice", re.I), "drink", "饮品偏好"),
    (re.compile(r"食|饮食|吃|菜|餐|过敏|忌口|food|meal|diet|allerg", re.I), "food", "饮食偏好"),
    (re.compile(r"写|文案|风格|语气|tone|writing|邮件|email", re.I), "writing", "写作风格"),
    (re.compile(r"旅|旅行|出行|酒店|航班|travel|trip|hotel|flight", re.I), "travel", "旅行"),
    (re.compile(r"运动|锻炼|健身|sport|exercise|gym|workout|running", re.I), "fitness", "运动健康"),
    (re.compile(r"工作|项目|代码|编程|work|project|code|dev|software", re.I), "work", "工作/项目"),
    (re.compile(r"音乐|歌|听|music|song|playlist|band", re.I), "music", "音乐"),
    (re.compile(r"阅读|书|读|book|read|novel", re.I), "reading", "阅读"),
    (re.compile(r"电影|电视|剧|movie|film|show|series", re.I), "media", "影视娱乐"),
    (re.compile(r"简洁|详细|长|短|回答|答复|reply|response|answer|concise|verbose", re.I), "reply_style", "回复偏好"),
    (re.compile(r"预算|价格|贵|便宜|money|budget|price|cost", re.I), "budget", "预算偏好"),
    (re.compile(r"宠物|猫|狗|pet|cat|dog", re.I), "pets", "宠物"),
    (re.compile(r"睡眠|作息|night|sleep|bedtime", re.I), "sleep", "作息"),
]

_SWITCH_HINTS = re.compile(
    r"改成|改为|换成|不再|以后不要|现在更|以前|曾经|used to|switched to|changed to|instead|rather than|不再喜欢",
    re.I,
)
_NEGATIVE_HINTS = re.compile(r"不要|别|不喜欢|讨厌|avoid|dislike|hate|never|can't stand", re.I)
_POSITIVE_HINTS = re.compile(r"喜欢|偏好|希望|love|prefer|enjoy|always", re.I)
_REASON_HINTS = re.compile(
    r"(?:因为|由于|原因是|since|because)\s*(.+)$",
    re.I,
)

EVOLUTION_QUERY_RE = re.compile(
    r"演变|变化|发展|过程|阶段|轨迹|历程|"
    r"以前|曾经|之前|后来|现在|改了|改成|换成|不再|"
    r"used to|evolution|evolved|changed over|shift(?:ed)?|progression|"
    r"initially|eventually|over time|journey|timeline|track full",
    re.I,
)
REASON_QUERY_RE = re.compile(
    r"为什么|为何|原因|理由|why|reason(?:ing)?|because|motivation",
    re.I,
)
FACT_RECALL_QUERY_RE = re.compile(
    r"是什么|叫什么|多少|哪(?:个|里|位|天|年)|谁|什么时候|"
    r"名字|称呼|记得.*吗|有没有|是否|"
    r"what is|what was|who|when|where|how many|how much|name|remember|recall",
    re.I,
)

_TOPIC_LABELS = {key: label for _, key, label in TOPIC_KEY_HINTS}
_ROMAN = ("①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩")


def query_suggests_evolution(query: str) -> bool:
    return bool(EVOLUTION_QUERY_RE.search(query or ""))


def query_suggests_reason_recall(query: str) -> bool:
    return bool(REASON_QUERY_RE.search(query or ""))


def query_suggests_fact_recall(query: str) -> bool:
    return bool(FACT_RECALL_QUERY_RE.search(query or ""))


def should_use_full_evolution_chain(query: str, atoms: list[dict[str, Any]]) -> bool:
    if len(atoms) <= 1:
        return False
    if query_suggests_evolution(query):
        return True
    if query_suggests_reason_recall(query):
        return True
    enriched = [enrich_atom(dict(a)) for a in atoms]
    if any(str(a.get("polarity") or "") == "switch" for a in enriched):
        if query_suggests_evolution(query) or query_suggests_reason_recall(query):
            return True
    return False


def split_recall_budget(
    budget_tokens: int,
    query: str,
    cfg: dict[str, Any] | None = None,
) -> tuple[int, int]:
    """Return ``(hit_budget, chain_budget)`` for two-phase recall."""
    budget = max(100, int(budget_tokens or 800))
    cfg = cfg or {}
    chain_ratio = float(cfg.get("memory_chain_budget_ratio") or 0.35)
    chain_ratio = max(0.15, min(0.55, chain_ratio))
    if query_suggests_evolution(query) or query_suggests_reason_recall(query):
        chain_ratio = max(chain_ratio, 0.5)
    elif query_suggests_fact_recall(query):
        chain_ratio = min(chain_ratio, 0.22)
    chain_budget = max(80, int(budget * chain_ratio))
    hit_budget = max(80, budget - chain_budget)
    return hit_budget, chain_budget


def max_chain_events_for_budget(chain_budget_tokens: int, *, default: int = 5) -> int:
    if chain_budget_tokens >= 400:
        return default
    if chain_budget_tokens >= 250:
        return 4
    if chain_budget_tokens >= 160:
        return 3
    return 2


def _match_regex_topic_key(content: str) -> str | None:
    text = (content or "").strip()
    for pattern, key, _label in TOPIC_KEY_HINTS:
        if pattern.search(text):
            return key
    return None


def infer_topic_key(content: str) -> str:
    text = (content or "").strip()
    regex_key = _match_regex_topic_key(text)
    if regex_key:
        return regex_key
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"misc_{digest}"


def assign_topic_key(
    content: str,
    *,
    explicit_key: str = "",
    paths: BotMemoryPaths | None = None,
    embedding_port=None,
    cfg: dict | None = None,
) -> str:
    """Regex-first topic assignment with optional embedding cluster fallback."""
    from .topic_registry import (
        KNOWN_TOPIC_KEYS,
        _derive_topic_label,
        _new_topic_key,
        cluster_enabled,
        find_best_topic,
        load_topic_registry,
        save_topic_registry,
        update_topic_centroid,
    )

    text = (content or "").strip()
    cfg = cfg or {}
    explicit = (explicit_key or "").strip()

    regex_key = _match_regex_topic_key(text)
    if regex_key:
        if paths is not None and cluster_enabled(cfg, embedding_port):
            try:
                vec = embedding_port.embed([text])[0]  # type: ignore[union-attr]
                if vec:
                    label = _TOPIC_LABELS.get(regex_key, regex_key)
                    update_topic_centroid(
                        paths,
                        regex_key,
                        vec,
                        content=text,
                        label=label,
                        embedding_port=embedding_port,
                    )
            except Exception:  # noqa: BLE001
                pass
        return regex_key

    if explicit and explicit in KNOWN_TOPIC_KEYS:
        if paths is not None and cluster_enabled(cfg, embedding_port):
            try:
                vec = embedding_port.embed([text])[0]  # type: ignore[union-attr]
                if vec:
                    update_topic_centroid(
                        paths,
                        explicit,
                        vec,
                        content=text,
                        label=_TOPIC_LABELS.get(explicit, explicit),
                        embedding_port=embedding_port,
                    )
            except Exception:  # noqa: BLE001
                pass
        return explicit

    if not cluster_enabled(cfg, embedding_port) or paths is None:
        if explicit and not explicit.startswith("misc_"):
            return explicit
        return infer_topic_key(text)

    try:
        vec = embedding_port.embed([text])[0]  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        return infer_topic_key(text)
    if not vec:
        return infer_topic_key(text)

    threshold = float(cfg.get("topic_cluster_threshold") or 0.85)
    threshold = max(0.5, min(0.99, threshold))
    registry = load_topic_registry(paths)
    model_id = getattr(embedding_port, "model_identity", "") or ""
    if model_id and registry.get("embedding_model") and registry.get("embedding_model") != model_id:
        from .topic_registry import rebuild_topic_centroids

        registry = rebuild_topic_centroids(paths, embedding_port=embedding_port)

    matched_key, score = find_best_topic(registry, vec, threshold=threshold)
    if matched_key:
        update_topic_centroid(
            paths,
            matched_key,
            vec,
            content=text,
            embedding_port=embedding_port,
        )
        return matched_key

    new_key = _new_topic_key(text)
    label = _derive_topic_label(text)
    topics = registry.setdefault("topics", {})
    topics[new_key] = {
        "label": label,
        "centroid": list(vec),
        "atom_count": 1,
        "updated_at": now_iso(),
    }
    if model_id:
        registry["embedding_model"] = model_id
    save_topic_registry(paths, registry)
    return new_key


def topic_label(topic_key: str, fallback_content: str = "", *, paths: BotMemoryPaths | None = None) -> str:
    if topic_key in _TOPIC_LABELS:
        return _TOPIC_LABELS[topic_key]
    if paths is not None:
        from .topic_registry import get_topic_label_from_registry, load_topic_registry

        label = get_topic_label_from_registry(load_topic_registry(paths), topic_key)
        if label:
            return label
    if topic_key.startswith("misc_"):
        return _infer_topic_label_legacy(fallback_content)
    if topic_key.startswith("topic_"):
        snippet = " ".join((fallback_content or "").split()).strip()[:24]
        return snippet or topic_key.replace("_", " ")
    return topic_key.replace("_", " ")


def _infer_topic_label_legacy(content: str) -> str:
    for pattern, _key, label in TOPIC_KEY_HINTS:
        if pattern.search(content or ""):
            return label
    return "其他"


def infer_polarity(content: str) -> str:
    text = (content or "").strip()
    if _SWITCH_HINTS.search(text):
        return "switch"
    if _NEGATIVE_HINTS.search(text):
        return "negative"
    if _POSITIVE_HINTS.search(text):
        return "positive"
    return "positive"


def extract_reason(content: str) -> str:
    text = (content or "").strip()
    match = _REASON_HINTS.search(text)
    if not match:
        return ""
    reason = (match.group(1) or "").strip()
    return reason[:200]


def next_atom_seq(paths: BotMemoryPaths) -> int:
    counter_path = paths.root / "l1_seq.counter"
    counter_path.parent.mkdir(parents=True, exist_ok=True)
    current = 0
    if counter_path.exists():
        try:
            current = int(counter_path.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            current = 0
    nxt = current + 1
    tmp = counter_path.with_suffix(".tmp")
    tmp.write_text(str(nxt), encoding="utf-8")
    os.replace(tmp, counter_path)
    return nxt


def _parse_meta_scalar(key: str, val: str) -> Any:
    raw = (val or "").strip().strip('"')
    if key in {"seq", "schema_version"}:
        try:
            return int(float(raw))
        except ValueError:
            return 0
    if key == "confidence":
        try:
            return float(raw)
        except ValueError:
            return 0.0
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    return raw


def _fallback_seq(atom: dict[str, Any]) -> int:
    meta = atom.get("meta") or {}
    created = str(atom.get("created_at") or meta.get("created_at") or "")
    if created:
        digits = re.sub(r"\D", "", created)
        if digits:
            return int(digits[-12:])
    path = atom.get("path")
    if path:
        p = Path(path)
        if p.exists():
            return int(p.stat().st_mtime * 1000)
    return 0


def enrich_atom(atom: dict[str, Any]) -> dict[str, Any]:
    meta = atom.get("meta") or {}
    content = str(atom.get("content") or "")
    topic_key = str(atom.get("topic_key") or meta.get("topic_key") or "").strip()
    if not topic_key:
        topic_key = infer_topic_key(content)
    polarity = str(atom.get("polarity") or meta.get("polarity") or infer_polarity(content))
    reason = str(atom.get("reason") or meta.get("reason") or extract_reason(content))
    seq_raw = atom.get("seq", meta.get("seq"))
    try:
        seq = int(seq_raw)
    except (TypeError, ValueError):
        seq = _fallback_seq(atom)
    atom["topic_key"] = topic_key
    atom["polarity"] = polarity if polarity in {"positive", "negative", "switch"} else infer_polarity(content)
    atom["reason"] = reason
    atom["seq"] = seq
    meta = atom.get("meta") or {}
    imp_raw = atom.get("importance", meta.get("importance"))
    try:
        atom["importance"] = float(imp_raw)
    except (TypeError, ValueError):
        from .memory_scoring import default_importance

        atom["importance"] = default_importance(str(atom.get("type") or meta.get("type") or "fact"))
    try:
        atom["hit_count"] = int(atom.get("hit_count", meta.get("hit_count", 0)) or 0)
    except (TypeError, ValueError):
        atom["hit_count"] = 0
    atom["supersedes_id"] = str(atom.get("supersedes_id") or meta.get("supersedes_id") or "")
    atom["superseded_by"] = str(atom.get("superseded_by") or meta.get("superseded_by") or "")
    return atom


def group_atoms_by_topic_key(atoms: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for atom in atoms:
        item = enrich_atom(dict(atom))
        key = str(item.get("topic_key") or infer_topic_key(str(item.get("content") or "")))
        groups.setdefault(key, []).append(item)
    for key in groups:
        groups[key].sort(key=lambda a: int(a.get("seq") or 0))
    return groups


def format_evolution_timeline(atoms: list[dict[str, Any]], *, max_events: int = 5) -> str:
    if not atoms:
        return ""
    ordered = sorted([enrich_atom(dict(a)) for a in atoms], key=lambda a: int(a.get("seq") or 0))
    if len(ordered) == 1:
        atom = ordered[0]
        return f"- {str(atom.get('content') or '')[:200]}"
    label = topic_label(str(ordered[-1].get("topic_key") or ""), str(ordered[-1].get("content") or ""))
    lines = [f"**{label}（演变）**"]
    tail = ordered[-max_events:]
    start_idx = max(0, len(ordered) - len(tail))
    for idx, atom in enumerate(tail):
        marker = _ROMAN[idx] if idx < len(_ROMAN) else f"{idx + 1}."
        ts = str(atom.get("created_at") or atom.get("meta", {}).get("created_at") or "")[:10]
        content = str(atom.get("content") or "").strip()[:200]
        reason = str(atom.get("reason") or "").strip()
        if idx == 0 and start_idx == 0:
            lines.append(f"{marker} {ts} {content}" if ts else f"{marker} {content}")
        else:
            arrow = f"{marker} {ts} → {content}" if ts else f"{marker} → {content}"
            if reason:
                arrow += f"  原因：{reason[:120]}"
            lines.append(arrow)
    current = str(ordered[-1].get("content") or "").strip()[:200]
    lines.append(f"→ 当前：{current}")
    return "\n".join(lines)


def format_topic_current_snapshot(topic_key: str, atoms: list[dict[str, Any]]) -> str:
    ordered = sorted([enrich_atom(dict(a)) for a in atoms], key=lambda a: int(a.get("seq") or 0))
    if not ordered:
        return ""
    latest = ordered[-1]
    label = topic_label(topic_key, str(latest.get("content") or ""))
    content = str(latest.get("content") or "").strip()[:180]
    if len(ordered) <= 1:
        return f"- [{latest.get('type', 'memory')}] {content}"
    return f"- [偏好·{label}] 当前：{content}"


def format_topic_chain_block(topic_key: str, atoms: list[dict[str, Any]], *, max_events: int = 5) -> str:
    ordered = sorted([enrich_atom(dict(a)) for a in atoms], key=lambda a: int(a.get("seq") or 0))
    if len(ordered) <= 1:
        atom = ordered[0]
        return f"- [{atom.get('type', 'memory')}] {str(atom.get('content') or '')[:200]}"
    label = topic_label(topic_key, str(ordered[-1].get("content") or ""))
    lines = [f"[偏好演变·{label}]"]
    tail = ordered[-max_events:]
    for idx, atom in enumerate(tail):
        marker = _ROMAN[idx] if idx < len(_ROMAN) else f"{idx + 1}."
        ts = str(atom.get("created_at") or "")[:10]
        content = str(atom.get("content") or "").strip()[:180]
        reason = str(atom.get("reason") or "").strip()
        if idx == 0:
            line = f"{marker} {ts} {content}" if ts else f"{marker} {content}"
        else:
            line = f"{marker} {ts} → {content}" if ts else f"{marker} → {content}"
            if reason:
                line += f"  原因：{reason[:100]}"
        lines.append(line)
    lines.append(f"→ 当前：{str(ordered[-1].get('content') or '')[:180]}")
    return "\n".join(lines)


def atoms_for_topic_keys(paths: BotMemoryPaths, topic_keys: set[str]) -> dict[str, list[dict[str, Any]]]:
    from .store_l1 import list_atoms

    groups = group_atoms_by_topic_key(list_atoms(paths))
    return {key: groups[key] for key in topic_keys if key in groups and len(groups[key]) > 1}
