"""MeClaw 2.0 chat-only backend entry."""

from __future__ import annotations

import asyncio
import io
import json
import threading
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .adapters import providers
from .domain.brains.brain_status import brain_status_for_bot
from .domain.brains.learner_brain import LearnerBrain
from .domain.brains.orchestrator import MultiBrainOrchestrator
from .domain.brains.runtime_status import (
    bump_learner_signal,
    mark_job_failed,
    mark_job_running,
    mark_job_success,
    save_session_cache_usage,
    save_session_trace,
    set_learner_status,
)
from .domain.memory.protocol import MemoryScope
from .storage.common import now_iso
from .storage.config_store import brains_config_for_bot, default_bot, load_config, normalize_bot, save_config
from .storage.history_store import (
    create_session,
    delete_session,
    load_messages,
    load_sessions_index,
    make_message,
    normalize_title,
    save_messages,
    save_sessions_index,
    update_session_meta,
)
from .storage.soul_store import (
    build_system_prompt,
    ensure_bot_soul_layout,
    read_constraints,
    read_platform_constraints,
    read_soul,
    write_constraints,
    write_soul,
)


@dataclass
class DataPaths:
    root: Path
    config: Path
    history_dir: Path
    sessions_index: Path
    souls_dir: Path


class AppContext:
    def __init__(self) -> None:
        meclaw2_root = Path(__file__).resolve().parents[1]
        data_root = Path(
            __import__("os").environ.get("MECLAW2_DATA_DIR", str(meclaw2_root / "data"))
        ).resolve()
        self.paths = DataPaths(
            root=data_root,
            config=data_root / "config.json",
            history_dir=data_root / "history",
            sessions_index=data_root / "history" / "sessions.json",
            souls_dir=data_root / "souls",
        )
        self.web_root = meclaw2_root / "web"
        self.config: dict = {}
        self.generation_lock = asyncio.Lock()
        self.active_generation: dict | None = None

    def ensure_bootstrap(self) -> None:
        self.paths.root.mkdir(parents=True, exist_ok=True)
        self.paths.history_dir.mkdir(parents=True, exist_ok=True)
        self.paths.souls_dir.mkdir(parents=True, exist_ok=True)

        self.config = load_config(self.paths.config)
        if not self.config.get("bots"):
            self.config["bots"] = [default_bot("default")]
        for bot in self.config.get("bots", []):
            ensure_bot_soul_layout(self.paths.souls_dir, bot["id"])
        self.config = save_config(self.paths.config, self.config, backup=True)

        if not self.paths.sessions_index.exists():
            save_sessions_index(self.paths.sessions_index, [], backup=False)

    def reload_config(self) -> dict:
        self.config = load_config(self.paths.config)
        return self.config

    def persist_config(self, cfg: dict, backup: bool = True) -> dict:
        self.config = save_config(self.paths.config, cfg, backup=backup)
        return self.config


ctx = AppContext()
app = FastAPI(title="MNEMOS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8766", "http://localhost:8766"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


def _mask_api_key(value: str) -> str:
    return providers.redact_api_key(value)


def _sanitize_profile(profile: dict) -> dict:
    p = providers.normalize_profile(profile)
    key = p.get("api_key", "") or ""
    p["has_api_key"] = bool(key)
    p["api_key"] = _mask_api_key(key) if key else ""
    return p


def _sanitize_config(cfg: dict) -> dict:
    out = dict(cfg)
    out["api_profiles"] = [_sanitize_profile(p) for p in cfg.get("api_profiles", [])]
    return out


def _history_backup_generations(cfg: dict | None = None) -> int:
    cfg = cfg or ctx.reload_config()
    return int(cfg.get("history_backup_generations", 3) or 3)


def _find_profile_in_cfg(profile_id: str, cfg: dict) -> dict | None:
    for p in cfg.get("api_profiles", []):
        if p.get("id") == profile_id:
            return p
    return None


def _bot_brain_status(bot: dict, cfg: dict | None = None) -> dict:
    cfg = cfg or ctx.config
    profile_id = (bot.get("profile_id") or "").strip()
    if not profile_id:
        return {
            "chat_ready": False,
            "brain_status": "unbound",
            "brain_message": "未配置大脑，请在编辑中绑定供应商",
            "provider_name": "",
        }
    profile = _find_profile_in_cfg(profile_id, cfg)
    if not profile:
        return {
            "chat_ready": False,
            "brain_status": "missing",
            "brain_message": "绑定的供应商不存在，请重新选择",
            "provider_name": "",
        }
    if profile.get("enabled", True) is False:
        return {
            "chat_ready": False,
            "brain_status": "disabled",
            "brain_message": "供应商已禁用",
            "provider_name": profile.get("name") or profile_id,
        }
    if not (profile.get("base_url") and profile.get("api_key") and providers.profile_models(profile)):
        return {
            "chat_ready": False,
            "brain_status": "incomplete",
            "brain_message": "供应商配置不完整，请前往设置补全",
            "provider_name": profile.get("name") or profile_id,
        }
    bot_model = (bot.get("model") or "").strip()
    available = providers.profile_models(profile)
    if not bot_model:
        return {
            "chat_ready": False,
            "brain_status": "no_model",
            "brain_message": "请在编辑 Bot 中选择模型",
            "provider_name": profile.get("name") or profile_id,
        }
    if bot_model not in available:
        return {
            "chat_ready": False,
            "brain_status": "invalid_model",
            "brain_message": "所选模型不在供应商列表中，请重新选择",
            "provider_name": profile.get("name") or profile_id,
        }
    return {
        "chat_ready": True,
        "brain_status": "ready",
        "brain_message": "",
        "provider_name": profile.get("name") or profile_id,
    }


def _public_bot(bot: dict, cfg: dict | None = None) -> dict:
    cfg = cfg or ctx.config
    out = dict(bot)
    out.update(_bot_brain_status(bot, cfg))
    out["effective_brains"] = brains_config_for_bot(cfg, bot)
    return out


def _find_profile(profile_id: str) -> dict | None:
    for p in ctx.config.get("api_profiles", []):
        if p.get("id") == profile_id:
            return p
    return None


def _find_bot(bot_id: str) -> dict | None:
    for b in ctx.config.get("bots", []):
        if b.get("id") == bot_id:
            return b
    return None


def _session_list() -> list[dict]:
    return load_sessions_index(ctx.paths.sessions_index)


def _save_session_list(items: list[dict]) -> None:
    save_sessions_index(
        ctx.paths.sessions_index,
        items,
        backup_generations=_history_backup_generations(),
    )


def _find_session(session_id: str) -> dict | None:
    for s in _session_list():
        if s.get("id") == session_id:
            return s
    return None


def _has_required_setup(cfg: dict) -> bool:
    bots = cfg.get("bots", [])
    if not bots:
        return False
    active = cfg.get("active_bot_id", "") or bots[0]["id"]
    bot = next((b for b in bots if b.get("id") == active), None)
    if not bot:
        return False
    profile = _find_profile(bot.get("profile_id", ""))
    if not profile:
        return False
    if not profile.get("enabled", True):
        return False
    return bool(
        profile.get("base_url")
        and profile.get("api_key")
        and providers.profile_models(profile)
        and (bot.get("model") or "").strip() in providers.profile_models(profile)
    )


def _profile_for_bot(bot: dict, role: str = "executor") -> dict:
    from .domain.brains.model_roles import resolve_llm_profile_for_role

    cfg = ctx.reload_config()
    merged = resolve_llm_profile_for_role(cfg, bot, role, _find_profile)
    if not merged:
        raise HTTPException(status_code=400, detail="当前 Bot 未绑定有效供应商")
    return merged


def _system_prompt(bot_id: str) -> str:
    souls_dir = ctx.paths.souls_dir
    return build_system_prompt(
        read_soul(souls_dir, bot_id),
        bot_constraints=read_constraints(souls_dir, bot_id),
        platform_constraints=read_platform_constraints(souls_dir),
    )


def _orchestrator() -> MultiBrainOrchestrator:
    return MultiBrainOrchestrator(
        souls_root=ctx.paths.souls_dir,
        history_dir=ctx.paths.history_dir,
        sessions_index_path=ctx.paths.sessions_index,
        config_getter=ctx.reload_config,
    )


def _max_context_for_bot(bot: dict) -> int:
    profile = _find_profile(bot.get("profile_id", "") or "")
    if profile:
        return int(profile.get("max_context") or 65536)
    return 65536


def _enrich_and_store_brain_trace(bot: dict, session_id: str, trace: dict) -> dict:
    if not session_id or not trace:
        return trace or {}
    models = trace.setdefault("models", {})
    try:
        executor_profile = _profile_for_bot(bot, role="executor")
        models["executor"] = str(executor_profile.get("model") or "")
    except HTTPException:
        models["executor"] = str(bot.get("model") or "")
    for role_key in ("extraction", "summary"):
        try:
            role_profile = _profile_for_bot(bot, role=role_key)
            models[role_key] = str(role_profile.get("model") or "")
        except HTTPException:
            models[role_key] = str(bot.get("background_model") or bot.get("model") or "")
    if models.get("extraction"):
        models["background"] = models["extraction"]
    save_session_trace(session_id, trace)
    return trace


def _build_api_messages(
    bot: dict,
    session_id: str,
    messages: list[dict],
    user_query: str,
) -> tuple[list[dict], dict]:
    cfg = ctx.reload_config()
    effective_brains = brains_config_for_bot(cfg, bot)
    if not cfg.get("multi_brain_enabled"):
        system = _system_prompt(bot["id"])
        api_messages = [{"role": "system", "content": system}]
        for m in messages:
            if m.get("role") in ("user", "assistant"):
                api_messages.append({"role": m["role"], "content": m.get("content", "")})
        return api_messages, {}

    system = _system_prompt(bot["id"])
    profile: dict | None = None
    try:
        profile = _profile_for_bot(bot, role="summary")
    except HTTPException:
        profile = None
    result = _orchestrator().prepare_turn(
        bot_id=bot["id"],
        session_id=session_id,
        system_base=system,
        history_messages=messages,
        user_query=user_query,
        max_context=_max_context_for_bot(bot),
        profile=profile,
        effective_brains=effective_brains,
    )
    trace = _enrich_and_store_brain_trace(bot, session_id, result.brain_trace)
    return result.api_messages, trace


async def _post_turn_hooks(
    session_id: str,
    bot: dict,
    messages: list[dict],
    user_content: str,
    assistant_content: str,
) -> None:
    cfg = ctx.reload_config()
    if not cfg.get("multi_brain_enabled"):
        return
    effective_brains = brains_config_for_bot(cfg, bot)
    scope = MemoryScope(kind="bot", scope_id=bot["id"])
    memory = _orchestrator().memory
    profile: dict | None = None
    try:
        profile = _profile_for_bot(bot, role="extraction")
    except HTTPException:
        profile = None

    await asyncio.to_thread(
        memory.after_turn,
        scope,
        session_id,
        messages,
        profile=profile,
        effective_brains=effective_brains,
    )

    learner_on = bool(effective_brains.get("learner_enabled"))
    set_learner_status(bot["id"], learner_on)
    if learner_on:
        mark_job_running(bot["id"], "learner")
        try:
            learner = LearnerBrain(ctx.paths.root)
            await asyncio.to_thread(
                learner.collect_signal,
                session_id=session_id,
                bot_id=bot["id"],
                user_input=user_content,
                assistant_output=assistant_content,
            )
            from .domain.learner.nudge import maybe_enqueue_nudge_candidate

            nudge_cfg = {**cfg, **effective_brains}
            candidate = await asyncio.to_thread(
                maybe_enqueue_nudge_candidate,
                learner,
                bot_id=bot["id"],
                session_id=session_id,
                user_input=user_content,
                assistant_output=assistant_content,
                messages=messages,
                cfg=nudge_cfg,
            )
            bump_learner_signal(bot["id"])
            if candidate:
                from .domain.brains.runtime_status import set_learner_pending_count

                set_learner_pending_count(bot["id"], learner.pending_count(bot["id"]))
            mark_job_success(bot["id"], "learner")
        except Exception as exc:  # noqa: BLE001
            mark_job_failed(bot["id"], "learner", str(exc))


def _save_user_message_and_prepare(session_id: str, content: str) -> tuple[dict, dict, list[dict], dict]:
    sessions = _session_list()
    session = next((s for s in sessions if s.get("id") == session_id), None)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    bot = _find_bot(session.get("bot_id", ""))
    if not bot:
        raise HTTPException(status_code=404, detail="会话对应 Bot 不存在")

    messages = load_messages(ctx.paths.history_dir, session_id)
    user_msg = make_message("user", content)
    messages.append(user_msg)
    save_messages(
        ctx.paths.history_dir,
        session_id,
        messages,
        backup_generations=_history_backup_generations(),
    )

    if (session.get("title") or "新对话") == "新对话" and content.strip():
        session["title"] = normalize_title(content)
    session["message_count"] = len(messages)
    session["updated_at"] = now_iso()
    _save_session_list(sessions)

    api_messages, brain_trace = _build_api_messages(bot, session_id, messages, content)
    return session, bot, api_messages, brain_trace


def _profile_update_keep_key(old: dict, incoming: dict) -> dict:
    updated = dict(old)
    for key in ("name", "base_url", "model", "models", "provider", "optimizations", "enabled", "temperature", "max_tokens", "max_context"):
        if key in incoming:
            updated[key] = incoming[key]
    if "api_key" in incoming:
        candidate = (incoming.get("api_key") or "").strip()
        if candidate and "*" not in candidate:
            updated["api_key"] = candidate
    return providers.normalize_profile(updated)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _test_profile_connection(profile: dict) -> tuple[bool, str]:
    p = providers.normalize_profile(profile)
    if not p.get("base_url") or not p.get("api_key") or not providers.profile_models(p):
        return False, "请先填写 Base URL、API Key，并至少配置一个模型"
    try:
        _ = providers.chat_once(
            p,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=8,
            timeout=15,
        )
        return True, "连接成功！API 正常工作。"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _append_assistant_message(
    session_id: str,
    bot_id: str,
    content: str,
    status: str,
    *,
    prior_versions: list[dict] | None = None,
    reasoning: str = "",
) -> dict:
    messages = load_messages(ctx.paths.history_dir, session_id)
    msg = make_message(
        "assistant",
        content,
        status=status,
        speaker_bot_id=bot_id,
        reasoning=reasoning or None,
    )
    if prior_versions:
        version_entry = {
            "content": content,
            "status": status,
            "created_at": msg["created_at"],
        }
        if reasoning:
            version_entry["reasoning"] = reasoning
        msg["versions"] = [
            *prior_versions,
            version_entry,
        ]
        msg["version_index"] = len(msg["versions"]) - 1
    messages.append(msg)
    save_messages(
        ctx.paths.history_dir,
        session_id,
        messages,
        backup_generations=_history_backup_generations(),
    )

    sessions = _session_list()
    update_session_meta(sessions, session_id, message_count=len(messages))
    _save_session_list(sessions)
    return msg


def _find_last_user_index(messages: list[dict]) -> int:
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            return i
    return -1


def _assistant_version_snapshot(msg: dict) -> dict:
    snap = {
        "content": msg.get("content", ""),
        "status": msg.get("status", "done"),
        "created_at": msg.get("created_at") or now_iso(),
    }
    if msg.get("reasoning"):
        snap["reasoning"] = msg["reasoning"]
    return snap


def _edit_last_user_and_prepare(session_id: str, content: str) -> tuple[dict, dict, list[dict], list[dict], dict]:
    text = (content or "").strip()
    if not text:
        raise ValueError("消息不能为空")

    sessions = _session_list()
    session = next((s for s in sessions if s.get("id") == session_id), None)
    if not session:
        raise ValueError("会话不存在")
    bot = _find_bot(session.get("bot_id", ""))
    if not bot:
        raise ValueError("会话对应 Bot 不存在")

    messages = load_messages(ctx.paths.history_dir, session_id)
    last_user_i = _find_last_user_index(messages)
    if last_user_i < 0:
        raise ValueError("没有可编辑的用户消息")

    prior_versions: list[dict] = []
    if last_user_i + 1 < len(messages) and messages[last_user_i + 1].get("role") == "assistant":
        assistant_msg = messages[last_user_i + 1]
        if assistant_msg.get("versions"):
            prior_versions = list(assistant_msg["versions"])
        else:
            prior_versions = [_assistant_version_snapshot(assistant_msg)]
        messages = messages[: last_user_i + 1]

    messages[last_user_i]["content"] = text
    save_messages(
        ctx.paths.history_dir,
        session_id,
        messages,
        backup_generations=_history_backup_generations(),
    )

    session["message_count"] = len(messages)
    session["updated_at"] = now_iso()
    _save_session_list(sessions)

    api_messages, brain_trace = _build_api_messages(bot, session_id, messages, text)
    return session, bot, api_messages, prior_versions, brain_trace


@app.get("/api/bots/{bot_id}/memory/l0")
def api_list_bot_memory_l0(
    bot_id: str,
    session_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    if not _find_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot 不存在")
    from .domain.memory.paths import ensure_bot_memory_layout
    from .domain.memory.store_l0 import list_l0_evidence

    paths = ensure_bot_memory_layout(ctx.paths.souls_dir, bot_id)
    lim = max(1, min(int(limit or 20), 100))
    off = max(0, int(offset or 0))
    items, total = list_l0_evidence(
        paths,
        session_id=(session_id or "").strip(),
        limit=lim,
        offset=off,
    )
    return {"ok": True, "items": items, "total": total}


@app.get("/api/bots/{bot_id}/memory/l1")
def api_list_bot_memory_l1(bot_id: str, limit: int = 100, offset: int = 0) -> dict:
    if not _find_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot 不存在")
    from .domain.memory.paths import ensure_bot_memory_layout
    from .domain.memory.store_l1 import list_atoms
    from .domain.memory.topic_metadata import topic_label

    paths = ensure_bot_memory_layout(ctx.paths.souls_dir, bot_id)
    atoms = list_atoms(paths)
    off = max(0, int(offset or 0))
    lim = max(1, min(int(limit or 100), 200))
    sliced = atoms[off : off + lim]
    items = [
        {
            "id": a.get("id"),
            "type": a.get("type"),
            "content": (a.get("content") or "")[:500],
            "session_id": a.get("session_id"),
            "created_at": a.get("created_at"),
            "topic_key": a.get("topic_key"),
            "topic_label": topic_label(
                str(a.get("topic_key") or ""),
                str(a.get("content") or ""),
                paths=paths,
            ),
        }
        for a in sliced
    ]
    return {"ok": True, "items": items, "total": len(atoms)}


@app.get("/api/bots/{bot_id}/memory/l2")
def api_list_bot_memory_l2(bot_id: str, limit: int = 20) -> dict:
    if not _find_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot 不存在")
    from .domain.memory.paths import ensure_bot_memory_layout
    from .domain.memory.store_l2 import list_session_summaries

    ensure_bot_memory_layout(ctx.paths.souls_dir, bot_id)
    lim = max(1, min(int(limit or 20), 50))
    sessions = _session_list()
    items = list_session_summaries(ctx.paths.history_dir, bot_id, sessions, limit=lim)
    return {"ok": True, "items": items}


@app.get("/api/bots/{bot_id}/memory/search")
def api_search_bot_memory(bot_id: str, q: str = "", limit: int = 10) -> dict:
    if not _find_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot 不存在")
    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="请提供搜索关键词 q")
    from .domain.memory.indexer import search_memory
    from .domain.memory.paths import ensure_bot_memory_layout

    paths = ensure_bot_memory_layout(ctx.paths.souls_dir, bot_id)
    lim = max(1, min(int(limit or 10), 30))
    hits = search_memory(paths, query, limit=lim)
    items = [
        {
            "id": h.get("id"),
            "type": h.get("type"),
            "layer": h.get("layer"),
            "session_id": h.get("session_id"),
            "snippet": (h.get("snippet") or h.get("body") or "")[:500],
        }
        for h in hits
    ]
    return {"ok": True, "items": items}


@app.get("/api/bots/{bot_id}/memory/l3")
def api_get_bot_memory_l3(bot_id: str) -> dict:
    if not _find_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot 不存在")
    from .domain.memory.store_l3 import read_user_profile

    return {"ok": True, "profile": read_user_profile(ctx.paths.souls_dir, bot_id)}


@app.get("/api/bots/{bot_id}/learner/candidates")
def api_list_learner_candidates(bot_id: str, status: str = "pending") -> dict:
    if not _find_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot 不存在")
    learner = LearnerBrain(ctx.paths.root)
    items = learner.list_candidates(bot_id=bot_id, status=(status or "pending").strip())
    return {"ok": True, "items": items, "total": len(items)}


@app.post("/api/bots/{bot_id}/learner/candidates/{candidate_id}/approve")
def api_approve_learner_candidate(bot_id: str, candidate_id: str) -> dict:
    if not _find_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot 不存在")
    learner = LearnerBrain(ctx.paths.root)
    cand = learner.get_candidate(candidate_id)
    if not cand or str(cand.get("bot_id") or "") != bot_id:
        raise HTTPException(status_code=404, detail="候选不存在")
    skill = None
    if str(cand.get("type") or "") == "skill_draft":
        from .domain.skills.store import create_skill_from_candidate

        title = str(cand.get("reason") or "Approved skill")[:120]
        skill = create_skill_from_candidate(
            ctx.paths.souls_dir,
            bot_id,
            title=title,
            content=str(cand.get("content") or ""),
        )
    updated = learner.update_candidate_status(candidate_id, "approved", note="manual approve")
    return {"ok": True, "candidate": updated, "skill": skill}


@app.post("/api/bots/{bot_id}/learner/candidates/{candidate_id}/reject")
def api_reject_learner_candidate(bot_id: str, candidate_id: str) -> dict:
    if not _find_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot 不存在")
    learner = LearnerBrain(ctx.paths.root)
    cand = learner.get_candidate(candidate_id)
    if not cand or str(cand.get("bot_id") or "") != bot_id:
        raise HTTPException(status_code=404, detail="候选不存在")
    updated = learner.update_candidate_status(candidate_id, "rejected", note="manual reject")
    return {"ok": True, "candidate": updated}


@app.delete("/api/bots/{bot_id}/memory/l1/{atom_id}")
def api_soft_delete_l1(bot_id: str, atom_id: str) -> dict:
    if not _find_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot 不存在")
    from .domain.memory.audit import mark_atom_deleted
    from .domain.memory.paths import ensure_bot_memory_layout

    paths = ensure_bot_memory_layout(ctx.paths.souls_dir, bot_id)
    target = paths.l1_dir / f"{atom_id}.md"
    if not target.exists():
        for p in paths.l1_dir.glob("*.md"):
            from .domain.memory.store_l1 import read_atom_file

            item = read_atom_file(p)
            if item and item.get("id") == atom_id:
                target = p
                break
    if not target.exists():
        raise HTTPException(status_code=404, detail="记忆不存在")
    mark_atom_deleted(target, paths, reason="user_delete")
    return {"ok": True}


@app.on_event("startup")
def _startup() -> None:
    ctx.ensure_bootstrap()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/system/data-info")
def api_data_info() -> dict:
    root = ctx.paths.root
    gens = _history_backup_generations()
    return {
        "ok": True,
        "data_dir": str(root),
        "exists": root.exists(),
        "history_backup_generations": gens,
    }


@app.get("/api/system/export")
def api_export_data() -> StreamingResponse:
    root = ctx.paths.root
    if not root.exists():
        raise HTTPException(status_code=404, detail="data directory not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            archive.write(path, arcname=f"data/{path.relative_to(root).as_posix()}")
    buf.seek(0)
    stamp = now_iso()[:10].replace("-", "")
    filename = f"mnemos-backup-{stamp}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/bootstrap")
def api_bootstrap() -> dict:
    cfg = ctx.reload_config()
    profiles = [_sanitize_profile(p) for p in cfg.get("api_profiles", [])]
    bots = [_public_bot(b, cfg) for b in cfg.get("bots", [])]
    return {
        "ok": True,
        "config": _sanitize_config(cfg),
        "providers": profiles,
        "bots": bots,
        "active_bot_id": cfg.get("active_bot_id", ""),
        "has_required_setup": _has_required_setup(cfg),
    }


@app.get("/api/config")
def api_get_config() -> dict:
    return {"ok": True, "config": _sanitize_config(ctx.reload_config())}


@app.put("/api/config")
def api_put_config(payload: dict[str, Any]) -> dict:
    cfg = ctx.reload_config()
    merged = dict(cfg)
    merged.update(payload or {})

    old_profiles = {p["id"]: p for p in cfg.get("api_profiles", [])}
    new_profiles = []
    for p in merged.get("api_profiles", []):
        pid = p.get("id")
        if pid and pid in old_profiles:
            new_profiles.append(_profile_update_keep_key(old_profiles[pid], p))
        else:
            np = providers.normalize_profile(p)
            if not np.get("id"):
                np["id"] = _new_id("p")
            new_profiles.append(np)
    merged["api_profiles"] = new_profiles

    saved = ctx.persist_config(merged, backup=True)
    for b in saved.get("bots", []):
        ensure_bot_soul_layout(ctx.paths.souls_dir, b["id"])
    return {"ok": True, "config": _sanitize_config(saved)}


@app.get("/api/providers")
def api_list_providers() -> dict:
    cfg = ctx.reload_config()
    return {"ok": True, "providers": [_sanitize_profile(p) for p in cfg.get("api_profiles", [])]}


@app.post("/api/providers")
def api_create_provider(payload: dict[str, Any]) -> dict:
    cfg = ctx.reload_config()
    p = providers.normalize_profile(payload)
    p["id"] = p.get("id") or _new_id("p")
    cfg["api_profiles"] = cfg.get("api_profiles", []) + [p]
    saved = ctx.persist_config(cfg, backup=True)
    return {"ok": True, "provider": _sanitize_profile(next(x for x in saved["api_profiles"] if x["id"] == p["id"]))}


@app.get("/api/providers/{profile_id}")
def api_get_provider(profile_id: str) -> dict:
    cfg = ctx.reload_config()
    p = next((x for x in cfg.get("api_profiles", []) if x.get("id") == profile_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return {"ok": True, "provider": _sanitize_profile(p)}


@app.put("/api/providers/{profile_id}")
def api_update_provider(profile_id: str, payload: dict[str, Any]) -> dict:
    cfg = ctx.reload_config()
    profiles = cfg.get("api_profiles", [])
    idx = next((i for i, x in enumerate(profiles) if x.get("id") == profile_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="供应商不存在")
    profiles[idx] = _profile_update_keep_key(profiles[idx], payload)
    cfg["api_profiles"] = profiles
    saved = ctx.persist_config(cfg, backup=True)
    return {"ok": True, "provider": _sanitize_profile(next(x for x in saved["api_profiles"] if x["id"] == profile_id))}


@app.delete("/api/providers/{profile_id}")
def api_delete_provider(profile_id: str) -> dict:
    cfg = ctx.reload_config()
    for b in cfg.get("bots", []):
        if b.get("profile_id") == profile_id:
            raise HTTPException(status_code=409, detail="该供应商已被 Bot 使用，无法删除")
    cfg["api_profiles"] = [p for p in cfg.get("api_profiles", []) if p.get("id") != profile_id]
    saved = ctx.persist_config(cfg, backup=True)
    return {"ok": True, "providers": [_sanitize_profile(p) for p in saved.get("api_profiles", [])]}


@app.post("/api/providers/{profile_id}/test")
def api_test_provider(profile_id: str) -> dict:
    cfg = ctx.reload_config()
    p = next((x for x in cfg.get("api_profiles", []) if x.get("id") == profile_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="供应商不存在")
    success, msg = _test_profile_connection(p)
    return {"ok": True, "success": success, "msg": msg}


@app.get("/api/bots")
def api_list_bots() -> dict:
    cfg = ctx.reload_config()
    bots = [_public_bot(b, cfg) for b in cfg.get("bots", [])]
    return {"ok": True, "bots": bots, "active_bot_id": cfg.get("active_bot_id", "")}


@app.post("/api/bots/reorder")
def api_reorder_bots(payload: dict[str, Any]) -> dict:
    order = payload.get("order") or []
    if not isinstance(order, list):
        raise HTTPException(status_code=400, detail="order 必须是数组")
    cfg = ctx.reload_config()
    bots = cfg.get("bots", [])
    bots_by_id = {b.get("id"): b for b in bots if b.get("id")}
    order_ids = [str(x).strip() for x in order if str(x).strip()]
    if set(order_ids) != set(bots_by_id.keys()):
        raise HTTPException(status_code=400, detail="order 与现有 Bot 列表不一致")
    cfg["bots"] = [bots_by_id[bot_id] for bot_id in order_ids]
    saved = ctx.persist_config(cfg, backup=True)
    return {"ok": True, "bots": [_public_bot(b, saved) for b in saved.get("bots", [])]}


@app.post("/api/bots")
def api_create_bot(payload: dict[str, Any]) -> dict:
    cfg = ctx.reload_config()
    bot = dict(default_bot(_new_id("b")))
    bot["name"] = (payload.get("name") or bot["name"]).strip() or bot["name"]
    avatar = (payload.get("avatar") or "").strip()
    bot["avatar"] = avatar or bot.get("avatar") or "🤖"
    bot["profile_id"] = payload.get("profile_id") or ""
    bot["model"] = payload.get("model") or ""
    bot["background_model"] = payload.get("background_model") or ""
    bot["brains"] = payload.get("brains") or {}
    bot["temperature"] = payload.get("temperature")
    bot["max_tokens"] = payload.get("max_tokens")
    if "reasoning_enabled" in payload:
        bot["reasoning_enabled"] = bool(payload.get("reasoning_enabled"))
    if "reasoning_level" in payload:
        bot["reasoning_level"] = payload.get("reasoning_level") or "off"
    if "reasoning_visible" in payload:
        bot["reasoning_visible"] = bool(payload.get("reasoning_visible"))
    bot = normalize_bot(bot)
    cfg["bots"] = cfg.get("bots", []) + [bot]
    cfg["active_bot_id"] = bot["id"]
    saved = ctx.persist_config(cfg, backup=True)
    ensure_bot_soul_layout(ctx.paths.souls_dir, bot["id"])
    return {"ok": True, "bot": _public_bot(next(x for x in saved["bots"] if x["id"] == bot["id"]), saved)}


@app.get("/api/bots/{bot_id}")
def api_get_bot(bot_id: str) -> dict:
    cfg = ctx.reload_config()
    bot = next((x for x in cfg.get("bots", []) if x.get("id") == bot_id), None)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot 不存在")
    return {"ok": True, "bot": _public_bot(bot, cfg)}


@app.get("/api/bots/{bot_id}/brain/status")
def api_bot_brain_status(bot_id: str, session_id: str | None = None) -> dict:
    cfg = ctx.reload_config()
    bot = _find_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot 不存在")
    public = _public_bot(bot, cfg)
    status = brain_status_for_bot(
        cfg=cfg,
        bot=bot,
        public_bot=public,
        session_id=session_id,
        souls_dir=ctx.paths.souls_dir,
        history_dir=ctx.paths.history_dir,
        sessions_index_path=ctx.paths.sessions_index,
        profile_for_bot_fn=_profile_for_bot,
        max_context_for_bot_fn=_max_context_for_bot,
    )
    return {"ok": True, "status": status}


@app.put("/api/bots/{bot_id}")
def api_update_bot(bot_id: str, payload: dict[str, Any]) -> dict:
    cfg = ctx.reload_config()
    bots = cfg.get("bots", [])
    idx = next((i for i, x in enumerate(bots) if x.get("id") == bot_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Bot 不存在")
    bot = dict(bots[idx])
    for key in (
        "name",
        "avatar",
        "profile_id",
        "model",
        "background_model",
        "temperature",
        "max_tokens",
        "brains",
        "reasoning_enabled",
        "reasoning_level",
        "reasoning_visible",
    ):
        if key in payload:
            bot[key] = payload[key]
    bot["name"] = (bot.get("name") or "").strip() or "未命名 Bot"
    if "avatar" in payload:
        avatar = (payload.get("avatar") or "").strip()
        bot["avatar"] = avatar or "🤖"
    bot = normalize_bot(bot)
    bots[idx] = bot
    cfg["bots"] = bots
    saved = ctx.persist_config(cfg, backup=True)
    ensure_bot_soul_layout(ctx.paths.souls_dir, bot_id)
    updated = next(x for x in saved["bots"] if x["id"] == bot_id)
    return {"ok": True, "bot": _public_bot(updated, saved)}


@app.delete("/api/bots/{bot_id}")
def api_delete_bot(bot_id: str) -> dict:
    cfg = ctx.reload_config()
    sessions = _session_list()
    if any(s.get("bot_id") == bot_id for s in sessions):
        raise HTTPException(status_code=409, detail="该 Bot 仍有关联会话，请先删除会话")
    bots = [b for b in cfg.get("bots", []) if b.get("id") != bot_id]
    if not bots:
        raise HTTPException(status_code=409, detail="至少保留一个 Bot")
    cfg["bots"] = bots
    if cfg.get("active_bot_id") == bot_id:
        cfg["active_bot_id"] = bots[0]["id"]
    saved = ctx.persist_config(cfg, backup=True)
    return {"ok": True, "bots": [_public_bot(b, saved) for b in saved["bots"]], "active_bot_id": saved["active_bot_id"]}


@app.get("/api/soul-files")
def api_soul_files(kind: str = "soul") -> dict:
    filename = "constraints.md" if (kind or "soul").strip().lower() == "constraints" else "soul.md"
    cfg = ctx.reload_config()
    bots_by_id = {b.get("id"): b for b in cfg.get("bots", [])}
    files: list[dict] = []
    souls_dir = ctx.paths.souls_dir
    if souls_dir.exists():
        for bot_dir in sorted(souls_dir.iterdir(), key=lambda p: p.name):
            if not bot_dir.is_dir() or bot_dir.name.startswith("_"):
                continue
            path = bot_dir / filename
            if not path.exists():
                continue
            bot_id = bot_dir.name
            bot = bots_by_id.get(bot_id)
            name = (bot or {}).get("name") or bot_id
            avatar = (bot or {}).get("avatar") or "📄"
            files.append(
                {
                    "bot_id": bot_id,
                    "label": f"{avatar} {name}",
                    "relative_path": f"souls/{bot_id}/{filename}",
                }
            )
    return {"ok": True, "kind": kind, "files": files}


@app.get("/api/bots/{bot_id}/soul")
def api_get_soul(bot_id: str) -> dict:
    if not _find_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot 不存在")
    return {
        "ok": True,
        "soul": read_soul(ctx.paths.souls_dir, bot_id),
        "constraints": read_constraints(ctx.paths.souls_dir, bot_id),
    }


@app.put("/api/bots/{bot_id}/soul")
def api_put_soul(bot_id: str, payload: dict[str, Any]) -> dict:
    if not _find_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot 不存在")
    write_soul(ctx.paths.souls_dir, bot_id, payload.get("soul", ""))
    if "constraints" in payload:
        write_constraints(ctx.paths.souls_dir, bot_id, payload.get("constraints", ""))
    return {"ok": True}


@app.get("/api/bots/{bot_id}/constraints")
def api_get_constraints(bot_id: str) -> dict:
    if not _find_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot 不存在")
    return {"ok": True, "constraints": read_constraints(ctx.paths.souls_dir, bot_id)}


@app.put("/api/bots/{bot_id}/constraints")
def api_put_constraints(bot_id: str, payload: dict[str, Any]) -> dict:
    if not _find_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot 不存在")
    write_constraints(ctx.paths.souls_dir, bot_id, payload.get("constraints", ""))
    return {"ok": True}


@app.get("/api/sessions")
def api_list_sessions(bot_id: str) -> dict:
    items = [s for s in _session_list() if s.get("bot_id") == bot_id]
    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return {"ok": True, "sessions": items}


@app.post("/api/sessions")
def api_new_session(payload: dict[str, Any]) -> dict:
    cfg = ctx.reload_config()
    bot_id = (payload.get("bot_id") or "").strip()
    if not bot_id or not any(b.get("id") == bot_id for b in cfg.get("bots", [])):
        raise HTTPException(status_code=400, detail="bot_id 无效")
    sessions = _session_list()
    item = create_session(sessions, bot_id=bot_id, title="新对话")
    _save_session_list(sessions)
    save_messages(
        ctx.paths.history_dir,
        item["id"],
        [],
        backup_generations=_history_backup_generations(),
    )
    return {"ok": True, "session": item}


@app.post("/api/sessions/{session_id}/switch")
def api_switch_session(session_id: str) -> dict:
    session = _find_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True, "session": session, "messages": load_messages(ctx.paths.history_dir, session_id)}


@app.put("/api/sessions/{session_id}")
def api_update_session(session_id: str, payload: dict[str, Any]) -> dict:
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    sessions = _session_list()
    updated = update_session_meta(sessions, session_id, title=title)
    if not updated:
        raise HTTPException(status_code=404, detail="会话不存在")
    _save_session_list(sessions)
    return {"ok": True, "session": updated}


@app.delete("/api/sessions/{session_id}")
def api_delete_session(session_id: str) -> dict:
    sessions = _session_list()
    new_sessions = delete_session(sessions, session_id)
    if len(new_sessions) == len(sessions):
        raise HTTPException(status_code=404, detail="会话不存在")
    _save_session_list(new_sessions)
    msg_path = ctx.paths.history_dir / f"{session_id}.json"
    if msg_path.exists():
        msg_path.unlink()
    return {"ok": True}


async def _run_generation(
    websocket: WebSocket,
    generation_id: str,
    session_id: str,
    content: str,
    stop_event: threading.Event,
    *,
    edit_last_user: bool = False,
    response_holder: dict[str, Any] | None = None,
) -> None:
    brain_trace: dict = {}
    try:
        if edit_last_user:
            session, bot, api_messages, prior_versions, brain_trace = _edit_last_user_and_prepare(session_id, content)
        else:
            session, bot, api_messages, brain_trace = _save_user_message_and_prepare(session_id, content)
            prior_versions = []
    except ValueError as exc:
        await websocket.send_json(
            {
                "event": "error",
                "generation_id": generation_id,
                "message": str(exc),
            }
        )
        async with ctx.generation_lock:
            if ctx.active_generation and ctx.active_generation.get("generation_id") == generation_id:
                ctx.active_generation = None
        return
    except HTTPException as exc:
        await websocket.send_json(
            {
                "event": "error",
                "generation_id": generation_id,
                "message": exc.detail,
            }
        )
        async with ctx.generation_lock:
            if ctx.active_generation and ctx.active_generation.get("generation_id") == generation_id:
                ctx.active_generation = None
        return

    if brain_trace and ctx.reload_config().get("brain_trace_enabled"):
        await websocket.send_json(
            {
                "event": "brain_trace",
                "generation_id": generation_id,
                "trace": brain_trace,
            }
        )

    profile = _profile_for_bot(bot)
    max_tokens = int(profile.get("max_tokens") or 4096)
    reasoning_level = providers.effective_reasoning_for_bot(bot)
    version_total = len(prior_versions) + 1
    version_current = version_total

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    raw_usage: dict = {}
    holder = response_holder if response_holder is not None else {}

    def worker() -> None:
        chunks: list[str] = []
        reasoning_chunks: list[str] = []
        try:
            for kind, token in providers.stream_chat_parts(
                profile,
                api_messages,
                max_tokens=max_tokens,
                stop_event=stop_event,
                usage_collector=raw_usage,
                reasoning_level=reasoning_level,
                response_holder=holder,
            ):
                if kind == "reasoning":
                    reasoning_chunks.append(token)
                    loop.call_soon_threadsafe(queue.put_nowait, ("reasoning_token", token))
                else:
                    chunks.append(token)
                    loop.call_soon_threadsafe(queue.put_nowait, ("token", token))
            status = "stopped" if stop_event.is_set() else "done"
            loop.call_soon_threadsafe(
                queue.put_nowait,
                ("finish", status, "".join(chunks), "".join(reasoning_chunks)),
            )
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(
                queue.put_nowait,
                ("error", str(exc), "".join(chunks), "".join(reasoning_chunks)),
            )

    threading.Thread(target=worker, daemon=True).start()

    partial = ""
    partial_reasoning = ""
    while True:
        kind, *rest = await queue.get()
        if kind == "reasoning_token":
            token = rest[0]
            partial_reasoning += token
            await websocket.send_json(
                {
                    "event": "reasoning_token",
                    "generation_id": generation_id,
                    "text": token,
                    "version_current": version_current,
                    "version_total": version_total,
                }
            )
            continue
        if kind == "token":
            token = rest[0]
            partial += token
            await websocket.send_json(
                {
                    "event": "token",
                    "generation_id": generation_id,
                    "text": token,
                    "version_current": version_current,
                    "version_total": version_total,
                }
            )
            continue

        if kind == "finish":
            status, full, reasoning_full = rest
            final_text = full or partial
            final_reasoning = reasoning_full or partial_reasoning
            assistant = _append_assistant_message(
                session_id,
                bot["id"],
                final_text,
                status,
                prior_versions=prior_versions or None,
                reasoning=final_reasoning,
            )
            evt = "stopped" if status == "stopped" else "done"
            await websocket.send_json(
                {
                    "event": evt,
                    "generation_id": generation_id,
                    "message": assistant,
                    "session_id": session_id,
                    "version_current": assistant.get("version_index", 0) + 1 if assistant.get("versions") else 1,
                    "version_total": len(assistant.get("versions") or [assistant]),
                }
            )
            # Emit cache usage event (best-effort; omit silently if unsupported)
            cache_info = providers.parse_cache_usage(raw_usage)
            save_session_cache_usage(session_id, cache_info)
            await websocket.send_json(
                {
                    "event": "cache_usage",
                    "generation_id": generation_id,
                    "session_id": session_id,
                    "cache_read": cache_info["read"],
                    "cache_create": cache_info["create"],
                    "hit_rate": cache_info["hit_rate"],
                    "supported": cache_info["supported"],
                }
            )
            if status in ("done", "stopped"):
                messages = load_messages(ctx.paths.history_dir, session_id)
                asyncio.create_task(
                    _post_turn_hooks(session_id, bot, messages, content, final_text)
                )
            break

        if kind == "error":
            err_text, partial_text, reasoning_partial = rest
            final_text = partial_text or f"❌ {err_text}"
            assistant = _append_assistant_message(
                session_id,
                bot["id"],
                final_text,
                "error",
                prior_versions=prior_versions or None,
                reasoning=reasoning_partial or partial_reasoning,
            )
            await websocket.send_json(
                {
                    "event": "error",
                    "generation_id": generation_id,
                    "message": str(err_text),
                    "assistant_message": assistant,
                    "version_current": assistant.get("version_index", 0) + 1 if assistant.get("versions") else 1,
                    "version_total": len(assistant.get("versions") or [assistant]),
                }
            )
            break

    async with ctx.generation_lock:
        if ctx.active_generation and ctx.active_generation.get("generation_id") == generation_id:
            ctx.active_generation = None


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"event": "error", "message": "消息格式错误（非 JSON）"})
                continue

            event = payload.get("event")
            if event == "send":
                generation_id = (payload.get("generation_id") or "").strip()
                session_id = (payload.get("session_id") or "").strip()
                content = (payload.get("content") or "").strip()
                edit_last_user = bool(payload.get("edit_last_user"))
                if not generation_id or not session_id or not content:
                    await websocket.send_json(
                        {
                            "event": "error",
                            "generation_id": generation_id or "",
                            "message": "send 事件缺少 generation_id / session_id / content",
                        }
                    )
                    continue

                async with ctx.generation_lock:
                    if ctx.active_generation is not None:
                        await websocket.send_json(
                            {
                                "event": "error",
                                "generation_id": generation_id,
                                "message": "已有进行中的生成，请先停止当前回复",
                            }
                        )
                        continue
                    stop_event = threading.Event()
                    response_holder: dict[str, Any] = {}
                    task = asyncio.create_task(
                        _run_generation(
                            websocket,
                            generation_id,
                            session_id,
                            content,
                            stop_event,
                            edit_last_user=edit_last_user,
                            response_holder=response_holder,
                        )
                    )

                    def _release_active_generation(finished: asyncio.Task) -> None:
                        async def _clear() -> None:
                            async with ctx.generation_lock:
                                active = ctx.active_generation
                                if active and active.get("generation_id") == generation_id:
                                    ctx.active_generation = None

                        asyncio.create_task(_clear())

                    task.add_done_callback(_release_active_generation)
                    ctx.active_generation = {
                        "generation_id": generation_id,
                        "stop_event": stop_event,
                        "task": task,
                        "response_holder": response_holder,
                    }
                continue

            if event == "stop":
                generation_id = (payload.get("generation_id") or "").strip()
                async with ctx.generation_lock:
                    active = ctx.active_generation
                    if not active:
                        await websocket.send_json(
                            {"event": "error", "generation_id": generation_id, "message": "当前没有进行中的生成"}
                        )
                        continue
                    if generation_id and active.get("generation_id") != generation_id:
                        await websocket.send_json(
                            {"event": "error", "generation_id": generation_id, "message": "generation_id 不匹配"}
                        )
                        continue
                    active["stop_event"].set()
                    holder = active.get("response_holder") or {}
                    resp = holder.get("response")
                    if resp is not None:
                        try:
                            resp.close()
                        except Exception:  # noqa: BLE001
                            pass
                continue

            await websocket.send_json({"event": "error", "message": f"未知事件: {event}"})
    except WebSocketDisconnect:
        async with ctx.generation_lock:
            active = ctx.active_generation
            if active and active.get("stop_event"):
                active["stop_event"].set()
                holder = active.get("response_holder") or {}
                resp = holder.get("response")
                if resp is not None:
                    try:
                        resp.close()
                    except Exception:  # noqa: BLE001
                        pass


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ctx.web_root / "index.html")


app.mount("/static", StaticFiles(directory=ctx.web_root), name="static")


@app.exception_handler(HTTPException)
async def _http_exc_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "msg": exc.detail})
