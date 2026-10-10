"""Super brain status aggregation for UI."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...storage.common import now_iso
from ...storage.config_store import brains_config_for_bot
from ...storage.history_store import load_messages
from ..memory.compaction import context_ratio, estimate_messages_tokens
from ..memory.paths import bot_memory_paths
from ..memory.store_l2 import list_session_summaries, read_session_summary
from ..memory.store_l3 import DEFAULT_PROFILE, profile_path
from .budgets import estimate_tokens
from .model_roles import resolve_role_models_for_display
from .runtime_status import get_session_cache_usage, get_session_trace, jobs_for_bot


def _iso_from_mtime(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except OSError:
        return ""


def memory_stats_for_bot(
    souls_dir: Path,
    history_dir: Path,
    sessions_index_path: Path,
    bot_id: str,
) -> dict[str, Any]:
    paths = bot_memory_paths(souls_dir, bot_id)
    l0_count = 0
    l1_count = 0
    last_write_at = ""

    if paths.l0_dir.exists():
        l0_files = list(paths.l0_dir.glob("*.json"))
        l0_count = len(l0_files)
        if l0_files:
            latest = max(l0_files, key=lambda p: p.stat().st_mtime)
            last_write_at = _iso_from_mtime(latest)

    if paths.l1_dir.exists():
        l1_count = len(list(paths.l1_dir.glob("*.md")))

    from ...storage.history_store import load_sessions_index

    sessions = load_sessions_index(sessions_index_path)
    l2_items = list_session_summaries(history_dir, bot_id, sessions, limit=50)
    l2_count = len(l2_items)

    l3_available = False
    l3_path = profile_path(souls_dir, bot_id)
    if l3_path.exists():
        try:
            text = l3_path.read_text(encoding="utf-8").strip()
            l3_available = bool(text and text != DEFAULT_PROFILE.strip())
        except OSError:
            l3_available = False

    index_status = "missing"
    if paths.index_db.exists():
        index_status = "ready"
    elif paths.l1_dir.exists() and l1_count > 0:
        index_status = "missing"

    return {
        "l0_count": l0_count,
        "l1_count": l1_count,
        "l2_count": l2_count,
        "l3_available": l3_available,
        "index_status": index_status,
        "last_write_at": last_write_at,
        "last_recall_count": 0,
        "last_error": "",
    }


def context_status_for_session(
    bot: dict,
    session_id: str | None,
    *,
    history_dir: Path,
    max_context: int,
    trace: dict[str, Any],
    effective_brains: dict[str, Any],
) -> dict[str, Any]:
    cache_usage = get_session_cache_usage(session_id or "")
    cache_section: dict[str, Any] = {
        "read": cache_usage.get("read", 0),
        "create": cache_usage.get("create", 0),
        "hit_rate": cache_usage.get("hit_rate"),
        "supported": bool(cache_usage.get("supported", False)),
        "updated_at": cache_usage.get("updated_at", ""),
    }

    if not session_id:
        return {
            "max_context": max_context,
            "estimated_tokens": 0,
            "ratio": 0.0,
            "compact_tier": 0,
            "protection_zone_tokens": int(effective_brains.get("protection_zone_tokens") or 8000),
            "summary_active": False,
            "cache": cache_section,
        }

    messages = load_messages(history_dir, session_id)
    api_like = [{"role": m.get("role"), "content": m.get("content", "")} for m in messages if m.get("role") in ("user", "assistant")]
    estimated = estimate_messages_tokens(api_like)
    ratio = float(trace.get("context_ratio") or context_ratio(api_like, max_context))
    summary = read_session_summary(history_dir, session_id)
    return {
        "max_context": max_context,
        "estimated_tokens": estimated,
        "ratio": round(ratio, 3),
        "compact_tier": int(trace.get("compact_tier") or 0),
        "protection_zone_tokens": int(effective_brains.get("protection_zone_tokens") or 8000),
        "summary_active": bool(summary.strip()),
        "cache": cache_section,
    }


def _brain_section(
    name: str,
    *,
    enabled: bool,
    active: bool,
    trace: dict[str, Any],
    budget_key: str | None = None,
    effective_brains: dict[str, Any] | None = None,
    status: str = "ready",
) -> dict[str, Any]:
    tokens = trace.get("tokens") or {}
    token_key = name if name != "executor" else "system"
    if name == "persona":
        token_key = "persona"
    elif name == "memory":
        token_key = "memory"
    elif name == "cognitive":
        token_key = "cognitive"
    tokens_used = int(tokens.get(token_key) or 0)
    out: dict[str, Any] = {
        "enabled": enabled,
        "active": active,
        "status": status if enabled else "disabled",
        "tokens_used": tokens_used,
    }
    if budget_key and effective_brains is not None:
        out["budget"] = int(effective_brains.get(budget_key) or 0)
    return out


def _resolve_models(bot: dict, profile_for_bot_fn, cfg: dict | None = None) -> tuple[str, str, dict[str, dict[str, Any]]]:
    executor = (bot.get("model") or "").strip()
    background = (bot.get("background_model") or "").strip() or executor
    role_models: dict[str, dict[str, Any]] = {}
    if cfg is not None:
        role_models = resolve_role_models_for_display(cfg, bot, profile_for_bot_fn)
        executor = str((role_models.get("executor") or {}).get("model") or executor)
        background = str((role_models.get("extraction") or {}).get("model") or background)
    else:
        try:
            executor = str(profile_for_bot_fn(bot, role="executor").get("model") or executor)
            background = str(profile_for_bot_fn(bot, role="extraction").get("model") or background)
        except Exception:  # noqa: BLE001
            pass
    return executor, background, role_models


def brain_status_for_bot(
    *,
    cfg: dict,
    bot: dict,
    public_bot: dict,
    session_id: str | None,
    souls_dir: Path,
    history_dir: Path,
    sessions_index_path: Path,
    profile_for_bot_fn,
    max_context_for_bot_fn,
) -> dict[str, Any]:
    effective = brains_config_for_bot(cfg, bot)
    multi_on = bool(cfg.get("multi_brain_enabled"))
    chat_ready = bool(public_bot.get("chat_ready"))
    has_override = bool(
        (bot.get("background_model") or "").strip()
        or ((bot.get("brains") or {}).get("model_roles"))
        or (bot.get("brains") or {})
    )
    executor_model, background_model, role_models = _resolve_models(bot, profile_for_bot_fn, cfg)
    extraction_model = str((role_models.get("extraction") or {}).get("model") or background_model)
    summary_model = str((role_models.get("summary") or {}).get("model") or background_model)

    trace = get_session_trace(session_id or "") if session_id else {}
    activated = set(trace.get("activated") or [])
    memory_trace = trace.get("memory") or {}

    mem_stats = memory_stats_for_bot(souls_dir, history_dir, sessions_index_path, bot["id"])
    mem_stats["enabled"] = multi_on and bool(effective.get("memory_enabled", True))
    mem_stats["retrieval_enabled"] = bool(effective.get("memory_retrieval_enabled", True))
    mem_stats["write_enabled"] = bool(effective.get("memory_write_enabled", True))
    mem_stats["last_recall_count"] = int(memory_trace.get("recall_count") or 0)

    max_ctx = max_context_for_bot_fn(bot)
    ctx_status = context_status_for_session(
        bot,
        session_id,
        history_dir=history_dir,
        max_context=max_ctx,
        trace=trace,
        effective_brains=effective,
    )

    jobs = jobs_for_bot(bot["id"])
    if not effective.get("learner_enabled"):
        jobs["learner"]["status"] = "disabled"
    else:
        jobs["learner"]["status"] = jobs["learner"].get("status") or "idle"
    if extraction_model and not jobs["l1_extraction"].get("model"):
        jobs["l1_extraction"]["model"] = extraction_model
    if summary_model and not jobs["tier3_summary"].get("model"):
        jobs["tier3_summary"]["model"] = summary_model

    health_status = "standby"
    health_label = "已就绪"
    health_message = "选择或新建会话后开始对话"
    if not chat_ready:
        health_status = "error"
        health_label = "配置异常"
        health_message = public_bot.get("brain_message") or "Bot 未就绪"
    elif not multi_on:
        health_status = "warn"
        health_label = "单脑模式"
        health_message = "多脑子编排已关闭，仅使用基础 system + history"
    elif not mem_stats["retrieval_enabled"] and not mem_stats["write_enabled"]:
        health_status = "warn"
        health_label = "记忆关闭"
        if mem_stats["enabled"]:
            health_message = "记忆脑已启用，但检索与写入均在设置中关闭"
        else:
            health_message = "记忆检索与写入均已关闭"
    else:
        health_status = "ok"
        health_label = "运行正常"
        health_message = "多脑子已启用，发送消息后将更新本轮 trace"

    if chat_ready and session_id and not trace:
        health_message = "会话已打开，发送消息后将显示编排 trace"

    brains = {
        "executor": _brain_section(
            "executor",
            enabled=chat_ready,
            active=True,
            trace=trace,
            status="ready" if chat_ready else "error",
        ),
        "persona": _brain_section(
            "persona",
            enabled=multi_on and bool(effective.get("persona_enabled", True)),
            active="persona" in activated,
            trace=trace,
            budget_key="persona_token_budget",
            effective_brains=effective,
        ),
        "memory": _brain_section(
            "memory",
            enabled=multi_on and bool(effective.get("memory_enabled", True)),
            active="memory" in activated,
            trace=trace,
            budget_key="memory_token_budget",
            effective_brains=effective,
        ),
        "cognitive": _brain_section(
            "cognitive",
            enabled=multi_on and bool(effective.get("cognitive_enabled", True)),
            active="cognitive" in activated,
            trace=trace,
            budget_key="cognitive_token_budget",
            effective_brains=effective,
        ),
        "learner": {
            "enabled": multi_on and bool(effective.get("learner_enabled")),
            "active": False,
            "status": jobs["learner"].get("status") or "disabled",
            "tokens_used": 0,
        },
    }

    return {
        "health": {
            "status": health_status,
            "label": health_label,
            "message": health_message,
            "last_updated_at": now_iso(),
        },
        "bot": {
            "id": bot.get("id"),
            "name": bot.get("name"),
            "provider_name": public_bot.get("provider_name") or "",
            "chat_ready": chat_ready,
            "config_source": "bot_override" if has_override else "global_default",
            "executor_model": executor_model,
            "background_model": background_model,
            "extraction_model": extraction_model,
            "summary_model": summary_model,
            "model_roles": role_models,
            "multi_brain_enabled": multi_on,
        },
        "brains": brains,
        "memory": mem_stats,
        "context": ctx_status,
        "background_jobs": jobs,
        "turn_trace": trace,
    }
