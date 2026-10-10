"""Config storage and normalization."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path

from ..adapters import providers

from .common import read_json, write_json_atomic

BOT_BRAIN_BOOL_FIELDS = (
    "persona_enabled",
    "memory_enabled",
    "cognitive_enabled",
    "learner_enabled",
    "memory_retrieval_enabled",
    "memory_write_enabled",
    "l1_extract_every_turn",
)

BOT_BRAIN_INT_FIELDS = (
    "memory_token_budget",
    "persona_token_budget",
    "cognitive_token_budget",
    "protection_zone_tokens",
    "compaction_tier1_pct",
    "compaction_tier2_pct",
    "compaction_tier3_pct",
    "summary_max_length",
)


DEFAULT_CONFIG = {
    "schema_version": 1,
    "api_profiles": [],
    "bots": [],
    "active_bot_id": "",
    "multi_brain_enabled": True,
    "brain_trace_enabled": False,
    "brains": {
        "persona_enabled": True,
        "memory_enabled": True,
        "cognitive_enabled": True,
        "learner_enabled": False,
    },
    "memory_enabled": True,
    "memory_retrieval_enabled": True,
    "memory_write_enabled": True,
    "memory_token_budget": 800,
    "persona_token_budget": 400,
    "cognitive_token_budget": 300,
    "protection_zone_tokens": 8000,
    "compaction_tier1_pct": 60,
    "compaction_tier2_pct": 80,
    "compaction_tier3_pct": 95,
    "l1_extract_every_turn": True,
    "l1_extract_mode": "hybrid",
    "l1_extract_max_atoms": 5,
    "l2_update_every_n_turns": 5,
    "l3_update_every_n_atoms": 5,
    "summary_max_length": 2000,
    "learner_enabled": False,
    "learner_schedule": "0 3 * * *",
    "knowledge_retrieval_strategy": "hybrid",
    "memory_retrieval_strategy": "hybrid",
    "memory_chain_budget_ratio": 0.35,
    "memory_chain_max_full": 2,
    "history_backup_generations": 3,
    "embedding_provider": "off",
    "embedding_model": "",
    "embedding_profile_id": "",
    "ann_enabled": True,
    "rerank_enabled": False,
    "rerank_provider": "off",
    "rerank_model": "",
    "rerank_profile_id": "",
    "rerank_candidate_pool": 20,
    "rerank_top_k": 5,
    "model_roles": {},
    "memory_dedupe_threshold": 0.92,
    "topic_cluster_enabled": True,
    "topic_cluster_threshold": 0.85,
    "memory_consolidation_enabled": False,
    "memory_l1_max_atoms": 300,
    "memory_topic_chain_max": 8,
    "memory_l3_max_chars": 1600,
    "memory_consolidation_merge_threshold": 0.93,
    "learner_nudge_enabled": False,
    "learner_nudge_dedupe_hours": 24,
    "skill_recall_enabled": False,
    "skill_token_budget": 400,
    "skill_recall_top_k": 1,
    "skill_recall_threshold": 0.65,
    "memory_recency_half_life_days": 90,
    "memory_score_relevance_weight": 1.0,
    "memory_score_importance_weight": 0.15,
    "memory_score_recency_weight": 0.1,
    "memory_score_hit_weight": 0.08,
}


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def default_bot(bot_id: str = "default") -> dict:
    return {
        "id": bot_id,
        "name": "MNEMOS",
        "avatar": "🤖",
        "profile_id": "",
        "model": "",
        "temperature": None,
        "max_tokens": None,
        "reasoning_enabled": False,
        "reasoning_level": "off",
        "reasoning_visible": True,
    }


def normalize_profile(p: dict) -> dict:
    x = providers.normalize_profile(p or {})
    if not x.get("id"):
        x["id"] = new_id("p")
    return x


def normalize_bot(bot: dict) -> dict:
    x = dict(bot or {})
    x.setdefault("id", new_id("b"))
    x.setdefault("name", "未命名 Bot")
    x.setdefault("avatar", "🤖")
    x.setdefault("profile_id", "")
    x.setdefault("model", "")
    x.setdefault("background_model", "")
    x.setdefault("temperature", None)
    x.setdefault("max_tokens", None)
    x.setdefault("reasoning_enabled", False)
    x.setdefault("reasoning_level", "off")
    x.setdefault("reasoning_visible", True)
    x["background_model"] = str(x.get("background_model") or "").strip()
    x["reasoning_enabled"] = bool(x.get("reasoning_enabled", False))
    x["reasoning_visible"] = bool(x.get("reasoning_visible", True))
    level = str(x.get("reasoning_level") or "off").strip().lower()
    x["reasoning_level"] = level if level in ("off", "low", "medium", "high") else "off"
    if not x["reasoning_enabled"]:
        x["reasoning_level"] = "off"
    x["brains"] = normalize_bot_brains(x.get("brains") or {})
    return x


def normalize_bot_brains(brains: dict) -> dict:
    src = dict(brains or {})
    out: dict[str, bool | int] = {}
    def _parse_bool(value: object) -> bool:
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("0", "false", "off", "no", "n"):
                return False
            if v in ("1", "true", "on", "yes", "y"):
                return True
        return bool(value)

    for key in BOT_BRAIN_BOOL_FIELDS:
        if key in src:
            out[key] = _parse_bool(src.get(key))
    for key in BOT_BRAIN_INT_FIELDS:
        if key not in src:
            continue
        raw = src.get(key)
        if raw is None or raw == "":
            continue
        try:
            out[key] = int(raw)
        except (TypeError, ValueError):
            continue
    from ..domain.brains.model_roles import normalize_model_roles

    if "model_roles" in src:
        roles = normalize_model_roles(src.get("model_roles"))
        if roles:
            out["model_roles"] = roles
    return out


def brains_defaults(cfg: dict) -> dict:
    raw = dict(cfg or {})
    brains = dict(raw.get("brains") or {})
    return {
        "persona_enabled": bool(brains.get("persona_enabled", True)),
        "memory_enabled": bool(brains.get("memory_enabled", True)),
        "cognitive_enabled": bool(brains.get("cognitive_enabled", True)),
        "learner_enabled": bool(brains.get("learner_enabled", False) or raw.get("learner_enabled", False)),
        "memory_retrieval_enabled": bool(raw.get("memory_retrieval_enabled", True)),
        "memory_write_enabled": bool(raw.get("memory_write_enabled", True)),
        "l1_extract_every_turn": bool(raw.get("l1_extract_every_turn", True)),
        "memory_token_budget": int(raw.get("memory_token_budget", 800) or 800),
        "persona_token_budget": int(raw.get("persona_token_budget", 400) or 400),
        "cognitive_token_budget": int(raw.get("cognitive_token_budget", 300) or 300),
        "protection_zone_tokens": int(raw.get("protection_zone_tokens", 8000) or 8000),
        "compaction_tier1_pct": int(raw.get("compaction_tier1_pct", 60) or 60),
        "compaction_tier2_pct": int(raw.get("compaction_tier2_pct", 80) or 80),
        "compaction_tier3_pct": int(raw.get("compaction_tier3_pct", 95) or 95),
        "summary_max_length": int(raw.get("summary_max_length", 2000) or 2000),
    }


def brains_config_for_bot(cfg: dict, bot: dict | None) -> dict:
    merged = brains_defaults(cfg)
    overrides = normalize_bot_brains((bot or {}).get("brains") or {})
    merged.update(overrides)
    return merged


def normalize_config(cfg: dict) -> dict:
    src = dict(cfg or {})
    raw = deepcopy(DEFAULT_CONFIG)
    raw.update(src)

    profiles = [normalize_profile(p) for p in (raw.get("api_profiles") or [])]
    # 去重，保留首次出现
    seen = set()
    dedup_profiles = []
    for p in profiles:
        pid = p.get("id", "")
        if pid in seen:
            continue
        seen.add(pid)
        dedup_profiles.append(p)
    raw["api_profiles"] = dedup_profiles

    bots = [normalize_bot(b) for b in (raw.get("bots") or [])]
    if not bots:
        bots = [default_bot("default")]
    seen = set()
    dedup_bots = []
    for b in bots:
        bid = b.get("id", "")
        if bid in seen:
            continue
        seen.add(bid)
        dedup_bots.append(b)
    raw["bots"] = dedup_bots

    active = raw.get("active_bot_id") or ""
    if not any(b["id"] == active for b in raw["bots"]):
        raw["active_bot_id"] = raw["bots"][0]["id"]

    raw["schema_version"] = 1
    raw["multi_brain_enabled"] = bool(raw.get("multi_brain_enabled", True))
    raw["brain_trace_enabled"] = bool(raw.get("brain_trace_enabled", False))
    brains = dict(DEFAULT_CONFIG["brains"])
    brains.update(dict(raw.get("brains") or {}))
    raw["brains"] = {
        "persona_enabled": bool(brains.get("persona_enabled", True)),
        "memory_enabled": bool(brains.get("memory_enabled", True)),
        "cognitive_enabled": bool(brains.get("cognitive_enabled", True)),
        "learner_enabled": bool(brains.get("learner_enabled", False)),
    }
    raw["memory_enabled"] = bool(raw.get("memory_enabled", True))
    raw["memory_retrieval_enabled"] = bool(raw.get("memory_retrieval_enabled", True))
    raw["memory_write_enabled"] = bool(raw.get("memory_write_enabled", True))
    raw["memory_token_budget"] = int(raw.get("memory_token_budget", 800) or 800)
    raw["persona_token_budget"] = int(raw.get("persona_token_budget", 400) or 400)
    raw["cognitive_token_budget"] = int(raw.get("cognitive_token_budget", 300) or 300)
    raw["protection_zone_tokens"] = int(raw.get("protection_zone_tokens", 8000) or 8000)
    raw["compaction_tier1_pct"] = int(raw.get("compaction_tier1_pct", 60) or 60)
    raw["compaction_tier2_pct"] = int(raw.get("compaction_tier2_pct", 80) or 80)
    raw["compaction_tier3_pct"] = int(raw.get("compaction_tier3_pct", 95) or 95)
    raw["l1_extract_every_turn"] = bool(raw.get("l1_extract_every_turn", True))
    mode = str(raw.get("l1_extract_mode") or "hybrid").strip().lower()
    raw["l1_extract_mode"] = mode if mode in ("heuristic", "llm", "hybrid") else "hybrid"
    raw["l1_extract_max_atoms"] = max(1, min(10, int(raw.get("l1_extract_max_atoms", 5) or 5)))
    raw["l2_update_every_n_turns"] = int(raw.get("l2_update_every_n_turns", 5) or 5)
    # Migrate legacy key `l3_update_every_n_turns` → `l3_update_every_n_atoms`.
    # Only fall back to the legacy value when the new key was not explicitly
    # provided by the caller (DEFAULT_CONFIG injects the new key into `raw`).
    if "l3_update_every_n_atoms" in src:
        _l3_atoms = src.get("l3_update_every_n_atoms")
    elif "l3_update_every_n_turns" in src:
        _l3_atoms = src.get("l3_update_every_n_turns")
    else:
        _l3_atoms = raw.get("l3_update_every_n_atoms", 5)
    raw["l3_update_every_n_atoms"] = int(_l3_atoms or 5)
    raw.pop("l3_update_every_n_turns", None)
    raw["summary_max_length"] = int(raw.get("summary_max_length", 2000) or 2000)
    raw["learner_enabled"] = bool(raw.get("learner_enabled", False))
    raw["learner_schedule"] = str(raw.get("learner_schedule", "0 3 * * *") or "0 3 * * *")
    ks = str(raw.get("knowledge_retrieval_strategy", "hybrid") or "hybrid").strip().lower()
    ms = str(raw.get("memory_retrieval_strategy", "hybrid") or "hybrid").strip().lower()
    raw["knowledge_retrieval_strategy"] = ks if ks in ("fts", "hybrid") else "hybrid"
    raw["memory_retrieval_strategy"] = ms if ms in ("fts", "hybrid") else "hybrid"
    raw["memory_chain_budget_ratio"] = max(
        0.15,
        min(0.55, float(raw.get("memory_chain_budget_ratio", 0.35) or 0.35)),
    )
    raw["memory_chain_max_full"] = max(1, min(4, int(raw.get("memory_chain_max_full", 2) or 2)))
    raw["history_backup_generations"] = max(
        1,
        min(10, int(raw.get("history_backup_generations", 3) or 3)),
    )
    ep = str(raw.get("embedding_provider") or "off").strip().lower()
    raw["embedding_provider"] = ep if ep in ("local", "api", "off") else "off"
    raw["embedding_model"] = str(raw.get("embedding_model") or "").strip()
    raw["embedding_profile_id"] = str(raw.get("embedding_profile_id") or "").strip()
    raw["ann_enabled"] = bool(raw.get("ann_enabled", True))
    raw["rerank_enabled"] = bool(raw.get("rerank_enabled", False))
    rp = str(raw.get("rerank_provider") or "off").strip().lower()
    raw["rerank_provider"] = rp if rp in ("local", "api", "off") else "off"
    raw["rerank_model"] = str(raw.get("rerank_model") or "").strip()
    raw["rerank_profile_id"] = str(raw.get("rerank_profile_id") or "").strip()
    raw["rerank_candidate_pool"] = max(5, min(50, int(raw.get("rerank_candidate_pool", 20) or 20)))
    raw["rerank_top_k"] = max(1, min(20, int(raw.get("rerank_top_k", 5) or 5)))
    from ..domain.brains.model_roles import normalize_model_roles

    raw["model_roles"] = normalize_model_roles(raw.get("model_roles"))
    raw["memory_dedupe_threshold"] = max(
        0.0,
        min(0.99, float(raw.get("memory_dedupe_threshold", 0.92) or 0.92)),
    )
    raw["topic_cluster_enabled"] = bool(raw.get("topic_cluster_enabled", True))
    raw["topic_cluster_threshold"] = max(
        0.5,
        min(0.99, float(raw.get("topic_cluster_threshold", 0.85) or 0.85)),
    )
    raw["memory_consolidation_enabled"] = bool(raw.get("memory_consolidation_enabled", False))
    raw["memory_l1_max_atoms"] = max(20, min(5000, int(raw.get("memory_l1_max_atoms", 300) or 300)))
    raw["memory_topic_chain_max"] = max(3, min(20, int(raw.get("memory_topic_chain_max", 8) or 8)))
    raw["memory_l3_max_chars"] = max(400, min(8000, int(raw.get("memory_l3_max_chars", 1600) or 1600)))
    raw["memory_consolidation_merge_threshold"] = max(
        0.85,
        min(0.99, float(raw.get("memory_consolidation_merge_threshold", 0.93) or 0.93)),
    )
    raw["learner_nudge_enabled"] = bool(raw.get("learner_nudge_enabled", False))
    raw["learner_nudge_dedupe_hours"] = max(
        1.0,
        min(168.0, float(raw.get("learner_nudge_dedupe_hours", 24) or 24)),
    )
    raw["skill_recall_enabled"] = bool(raw.get("skill_recall_enabled", False))
    raw["skill_token_budget"] = max(100, min(2000, int(raw.get("skill_token_budget", 400) or 400)))
    raw["skill_recall_top_k"] = max(1, min(3, int(raw.get("skill_recall_top_k", 1) or 1)))
    raw["skill_recall_threshold"] = max(
        0.4,
        min(0.99, float(raw.get("skill_recall_threshold", 0.65) or 0.65)),
    )
    raw["memory_recency_half_life_days"] = max(
        7.0,
        min(365.0, float(raw.get("memory_recency_half_life_days", 90) or 90)),
    )
    raw["memory_score_relevance_weight"] = max(
        0.0,
        float(raw.get("memory_score_relevance_weight", 1.0) or 1.0),
    )
    raw["memory_score_importance_weight"] = max(
        0.0,
        float(raw.get("memory_score_importance_weight", 0.15) or 0.15),
    )
    raw["memory_score_recency_weight"] = max(
        0.0,
        float(raw.get("memory_score_recency_weight", 0.1) or 0.1),
    )
    raw["memory_score_hit_weight"] = max(
        0.0,
        float(raw.get("memory_score_hit_weight", 0.08) or 0.08),
    )
    return raw


def load_config(path: Path) -> dict:
    cfg = read_json(path, DEFAULT_CONFIG)
    return normalize_config(cfg)


def save_config(path: Path, cfg: dict, backup: bool = True) -> dict:
    normalized = normalize_config(cfg)
    write_json_atomic(path, normalized, backup=backup)
    return normalized

