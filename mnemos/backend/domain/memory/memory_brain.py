"""Memory brain — personal conversation memory facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...storage.history_store import load_sessions_index
from .compaction import compact_messages
from .l1_extractor import extract_atoms
from .paths import BotMemoryPaths, ensure_bot_memory_layout, session_summary_path
from .protocol import CompressResult, MemoryScope
from .store_l0 import list_recent_evidence, save_turn_evidence
from .store_l1 import get_atom_by_id, list_atoms
from .topic_metadata import (
    atoms_for_topic_keys,
    enrich_atom,
    format_topic_chain_block,
    format_topic_current_snapshot,
    max_chain_events_for_budget,
    should_use_full_evolution_chain,
    split_recall_budget,
)
from .store_l2 import list_session_summaries, read_session_summary, write_session_summary
from .indexer import rebuild_index, search_memory
from .tier3_summarizer import refresh_running_summary_if_needed
from ..brains.budgets import estimate_tokens, fit_lines_to_budget


class MemoryBrain:
    def __init__(
        self,
        souls_root: Path,
        history_dir: Path,
        sessions_index_path: Path,
        config_getter,
    ) -> None:
        self.souls_root = souls_root
        self.history_dir = history_dir
        self.sessions_index_path = sessions_index_path
        self.config_getter = config_getter
        # Diagnostics for the most recent before_chat recall (consumed by the
        # orchestrator to populate brain_trace). Reset on every before_chat call.
        self.last_recall_debug: list[dict] = []
        self._embedding_port_cache: tuple[tuple[str, str, str], object] | None = None
        self._reranker_cache: tuple[tuple[str, str, str, str, bool], object] | None = None
        self._vector_index_cache: tuple[tuple[str, str, str, bool], object] | None = None

    def _cfg(self) -> dict:
        return self.config_getter() or {}

    def _embedding_port(self, cfg: dict | None = None):
        from .embedding.factory import create_embedding_port

        effective = dict(cfg or self._cfg())
        key = (
            str(effective.get("embedding_provider") or "off"),
            str(effective.get("embedding_model") or ""),
            str(effective.get("embedding_profile_id") or ""),
        )
        if self._embedding_port_cache and self._embedding_port_cache[0] == key:
            return self._embedding_port_cache[1]
        profiles = list((self._cfg() or {}).get("api_profiles") or [])
        port = create_embedding_port(effective, profiles)
        self._embedding_port_cache = (key, port)
        return port

    def _reranker(self, cfg: dict | None = None):
        from .rerank.factory import create_reranker

        effective = dict(cfg or self._cfg())
        key = (
            str(effective.get("rerank_enabled", False)),
            str(effective.get("rerank_provider") or "off"),
            str(effective.get("rerank_model") or ""),
            str(effective.get("rerank_profile_id") or ""),
            bool(effective.get("rerank_enabled", False)),
        )
        if self._reranker_cache and self._reranker_cache[0] == key:
            return self._reranker_cache[1]
        profiles = list((self._cfg() or {}).get("api_profiles") or [])
        port = create_reranker(effective, profiles)
        self._reranker_cache = (key, port)
        return port

    def _vector_index(self, cfg: dict | None = None):
        from .vector_index.factory import create_vector_index

        effective = dict(cfg or self._cfg())
        key = (
            str(effective.get("embedding_provider") or "off"),
            str(effective.get("embedding_model") or ""),
            str(effective.get("embedding_profile_id") or ""),
            bool(effective.get("ann_enabled", True)),
        )
        if self._vector_index_cache and self._vector_index_cache[0] == key:
            return self._vector_index_cache[1]
        embed = self._embedding_port(effective)
        idx = create_vector_index(effective, embed)
        self._vector_index_cache = (key, idx)
        return idx

    def _effective_cfg(self, effective_brains: dict | None = None, bot_id: str = "") -> dict:
        from ..brains.model_roles import effective_cfg_for_bot

        cfg = dict(self._cfg())
        if bot_id:
            return effective_cfg_for_bot(cfg, bot_id, effective_brains)
        if effective_brains:
            cfg.update(dict(effective_brains))
        return cfg

    def _paths(self, bot_id: str) -> BotMemoryPaths:
        return ensure_bot_memory_layout(self.souls_root, bot_id)

    def before_chat(
        self,
        scope: MemoryScope,
        query: str,
        session_summary: str,
        budget_tokens: int,
        *,
        session_id: str = "",
        cross_session: bool = False,
        l0_deep_recall: bool = False,
        effective_brains: dict | None = None,
    ) -> str:
        cfg = self._effective_cfg(effective_brains, bot_id=scope.scope_id)
        if not cfg.get("memory_enabled") and not cfg.get("multi_brain_enabled"):
            return ""
        if not cfg.get("memory_retrieval_enabled", True):
            return ""

        bot_id = scope.scope_id
        paths = self._paths(bot_id)
        budget = max(100, int(budget_tokens or 800))
        hit_budget, chain_budget = split_recall_budget(budget, query, cfg)
        max_full_chains = max(1, int(cfg.get("memory_chain_max_full") or 2))
        lines = ["[相关记忆]"]
        used = estimate_tokens(lines[0])
        hit_used = 0
        chain_used = 0

        # NOTE: the current-session summary is injected once by the orchestrator
        # as an independent `[会话摘要]` block; do NOT duplicate it here.

        self.last_recall_debug = []
        mode = str(cfg.get("memory_retrieval_strategy") or "hybrid").strip().lower()
        if mode == "fts":
            hits = search_memory(paths, query, limit=8)
        else:
            from .hybrid import search_memory_hybrid

            min_score = float(cfg.get("memory_recall_min_score") or 0.0)
            reranker = self._reranker(cfg)
            use_rerank = reranker.available
            recall_limit = int(cfg.get("rerank_top_k") or 5) if use_rerank else 8
            hits = search_memory_hybrid(
                paths,
                query,
                limit=recall_limit,
                min_score=min_score,
                embedding_port=self._embedding_port(cfg),
                vector_index=self._vector_index(cfg),
                reranker=reranker,
                rerank_enabled=use_rerank,
                rerank_candidate_pool=int(cfg.get("rerank_candidate_pool") or 20),
                rerank_top_k=int(cfg.get("rerank_top_k") or 5),
                cfg=cfg,
            )

        topic_keys: set[str] = set()
        atom_by_hit_id: dict[str, dict] = {}
        topic_hit_rank: dict[str, int] = {}
        for rank, hit in enumerate(hits):
            atom = get_atom_by_id(paths, str(hit.get("id") or ""))
            if not atom:
                continue
            atom_by_hit_id[str(hit.get("id") or "")] = atom
            enriched = enrich_atom(atom)
            topic_key = str(enriched.get("topic_key") or "")
            if topic_key:
                topic_keys.add(topic_key)
                topic_hit_rank.setdefault(topic_key, rank)

        chain_map = atoms_for_topic_keys(paths, {k for k in topic_keys if k})
        eligible_full_topics = sorted(
            (
                tk
                for tk, atoms in chain_map.items()
                if should_use_full_evolution_chain(query, atoms)
            ),
            key=lambda tk: topic_hit_rank.get(tk, 999),
        )
        full_chain_topics = set(eligible_full_topics[:max_full_chains])
        chain_atom_ids: set[str] = set()
        shown_atom_ids: set[str] = set()

        for topic_key in chain_map:
            for atom in chain_map[topic_key]:
                chain_atom_ids.add(str(atom.get("id") or ""))

        from .memory_scoring import is_superseded
        from .store_l1 import increment_hit_count

        # Phase 1 — direct hits (fact recall first, within hit_budget).
        for hit in hits:
            hit_id = str(hit.get("id") or "")
            atom = atom_by_hit_id.get(hit_id)
            if not atom:
                continue
            enriched = enrich_atom(atom)
            if is_superseded(enriched):
                continue
            topic_key = str(enriched.get("topic_key") or "")
            if topic_key in full_chain_topics:
                continue
            layer = hit.get("layer") or "L1"
            record_type = hit.get("type") or "memory"
            snippet = hit.get("snippet") or hit.get("body") or ""
            block = f"- [{layer}·{record_type}] {snippet[:200]}"
            est = estimate_tokens(block)
            if hit_used + est > hit_budget:
                break
            lines.append(block)
            hit_used += est
            used += est
            shown_atom_ids.add(hit_id)
            self.last_recall_debug.append(
                {
                    "id": hit.get("id"),
                    "layer": layer,
                    "type": record_type,
                    "hybrid_score": round(float(hit.get("hybrid_score", 0.0)), 5),
                    "semantic_score": round(float(hit.get("semantic_score", 0.0)), 5),
                }
            )

        # Phase 2 — topic chains (compact or full, within chain_budget).
        max_events = max_chain_events_for_budget(chain_budget - chain_used)
        for topic_key in sorted(chain_map):
            chain_atoms = chain_map[topic_key]
            use_full = topic_key in full_chain_topics
            if use_full:
                block = format_topic_chain_block(topic_key, chain_atoms, max_events=max_events)
            else:
                latest_id = str(sorted(
                    [enrich_atom(dict(a)) for a in chain_atoms],
                    key=lambda a: int(a.get("seq") or 0),
                )[-1].get("id") or "")
                if latest_id and latest_id in shown_atom_ids:
                    continue
                block = format_topic_current_snapshot(topic_key, chain_atoms)
            if not block:
                continue
            est = estimate_tokens(block)
            if chain_used + est > chain_budget:
                if use_full:
                    block = format_topic_current_snapshot(topic_key, chain_atoms)
                    est = estimate_tokens(block)
                    if not block or chain_used + est > chain_budget:
                        continue
                else:
                    continue
            lines.append(block)
            chain_used += est
            used += est
            debug_type = "preference_evolution" if use_full else "preference_current"
            self.last_recall_debug.append(
                {
                    "id": f"chain:{topic_key}",
                    "layer": "L1",
                    "type": debug_type,
                    "hybrid_score": 1.0,
                    "semantic_score": 0.0,
                }
            )

        if cross_session:
            sessions = load_sessions_index(self.sessions_index_path)
            for item in list_session_summaries(self.history_dir, bot_id, sessions, limit=2):
                if item.get("session_id") == session_id:
                    continue
                block = f"- [历史会话·{item.get('title', '')}] {item.get('summary', '')[:250]}"
                est = estimate_tokens(block)
                if used + est > budget:
                    break
                lines.append(block)
                used += est

        if l0_deep_recall and session_id:
            for ev in list_recent_evidence(paths, session_id, limit=2):
                msgs = ev.get("messages") or []
                for m in msgs:
                    block = f"- [原文·{m.get('role', '')}] {(m.get('content') or '')[:180]}"
                    est = estimate_tokens(block)
                    if used + est > budget:
                        break
                    lines.append(block)
                    used += est

        if len(lines) <= 1:
            return ""
        for atom_id in shown_atom_ids:
            try:
                increment_hit_count(paths, atom_id)
            except Exception:  # noqa: BLE001
                pass
        return "\n".join(fit_lines_to_budget(lines, budget))

    def after_turn(
        self,
        scope: MemoryScope,
        session_id: str,
        messages: list[dict],
        *,
        profile: dict | None = None,
        effective_brains: dict | None = None,
    ) -> None:
        bot_id = scope.scope_id
        cfg = self._effective_cfg(effective_brains, bot_id=bot_id)
        if not cfg.get("memory_write_enabled") and not cfg.get("multi_brain_enabled"):
            return
        paths = self._paths(bot_id)
        save_turn_evidence(paths, session_id=session_id, messages=messages)

        if len(messages) < 2:
            return
        user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        asst_msg = next((m for m in reversed(messages) if m.get("role") == "assistant"), None)
        if not user_msg or not asst_msg:
            return

        embed_port = self._embedding_port(cfg)

        if cfg.get("l1_extract_every_turn", True):
            from ..brains.runtime_status import mark_job_failed, mark_job_running, mark_job_success

            model = str((profile or {}).get("model") or "")
            dedupe_threshold = float(cfg.get("memory_dedupe_threshold") or 0.92)
            extract_mode = str(cfg.get("l1_extract_mode") or "hybrid")
            max_atoms = int(cfg.get("l1_extract_max_atoms") or 5)
            topic_cluster_cfg = {
                "topic_cluster_enabled": bool(cfg.get("topic_cluster_enabled", True)),
                "topic_cluster_threshold": float(cfg.get("topic_cluster_threshold") or 0.85),
                "embedding_provider": str(cfg.get("embedding_provider") or "off"),
            }
            warnings: list[str] = []

            def _on_warning(msg: str) -> None:
                warnings.append(msg)

            mark_job_running(bot_id, "l1_extraction", model=model)
            try:
                created = extract_atoms(
                    paths,
                    session_id=session_id,
                    user_message=str(user_msg.get("content") or ""),
                    assistant_message=str(asst_msg.get("content") or ""),
                    mode=extract_mode,
                    profile=profile,
                    embedding_port=embed_port,
                    dedupe_threshold=dedupe_threshold,
                    max_atoms=max_atoms,
                    on_warning=_on_warning,
                    topic_cluster_cfg=topic_cluster_cfg,
                )
                mark_job_success(
                    bot_id,
                    "l1_extraction",
                    model=model,
                    created_count=len(created),
                    warning="; ".join(warnings),
                )
            except Exception as exc:  # noqa: BLE001
                mark_job_failed(bot_id, "l1_extraction", str(exc), model=model)

        turn_count = sum(1 for m in messages if m.get("role") == "user")
        l2_every = int(cfg.get("l2_update_every_n_turns") or 5)
        if turn_count > 0 and turn_count % max(l2_every, 1) == 0:
            self._update_l2_summary(session_id, messages)

        if cfg.get("l3_profile_enabled", True):
            try:
                from .profile_aggregator import refresh_persona_profile

                l3_every = int(cfg.get("l3_update_every_n_atoms") or 5)
                refresh_persona_profile(
                    self.souls_root, bot_id, l3_update_every_n_atoms=l3_every
                )
            except Exception:  # noqa: BLE001
                pass

        if cfg.get("memory_consolidation_enabled"):
            from ..brains.runtime_status import mark_job_failed, mark_job_running, mark_job_success
            from .consolidation import maybe_run_consolidation

            mark_job_running(bot_id, "consolidation")
            try:
                stats = maybe_run_consolidation(
                    paths,
                    souls_root=self.souls_root,
                    bot_id=bot_id,
                    cfg=cfg,
                    embedding_port=embed_port,
                    summary_profile=profile,
                )
                mark_job_success(
                    bot_id,
                    "consolidation",
                    stats=stats or {"skipped": True},
                )
            except Exception as exc:  # noqa: BLE001
                mark_job_failed(bot_id, "consolidation", str(exc))

    def _update_l2_summary(self, session_id: str, messages: list[dict]) -> None:
        recent = messages[-10:]
        lines = ["## 会话进展（自动摘要）", ""]
        for m in recent:
            role = m.get("role", "")
            content = str(m.get("content") or "")[:200]
            lines.append(f"- **{role}**: {content}")
        write_session_summary(self.history_dir, session_id, "\n".join(lines))

    def compact_for_api(
        self,
        api_messages: list[dict],
        *,
        session_id: str,
        bot_id: str,
        max_context: int,
        profile: dict | None = None,
        effective_brains: dict | None = None,
    ) -> tuple[list[dict], int, float]:
        cfg = self._effective_cfg(effective_brains, bot_id=bot_id)
        paths = self._paths(bot_id)
        tier3_pct = int(cfg.get("compaction_tier3_pct") or 95)
        protection = int(cfg.get("protection_zone_tokens") or 8000)
        summary_max = int(cfg.get("summary_max_length") or 2000)

        summary = refresh_running_summary_if_needed(
            profile,
            self.history_dir,
            session_id,
            api_messages,
            max_context=max_context,
            tier3_pct=tier3_pct,
            protection_zone_tokens=protection,
            summary_max_length=summary_max,
            bot_id=bot_id,
        )

        result = compact_messages(
            api_messages,
            session_id=session_id,
            max_context=max_context,
            cache_dir=paths.replacement_cache_dir,
            tier1_pct=int(cfg.get("compaction_tier1_pct") or 60),
            tier2_pct=int(cfg.get("compaction_tier2_pct") or 80),
            tier3_pct=tier3_pct,
            protection_zone_tokens=protection,
            running_summary=summary,
        )
        return result.messages, result.tier, result.ratio

    def on_compress(self, scope: MemoryScope, session_id: str, messages: list[dict]) -> CompressResult:
        self._update_l2_summary(session_id, messages)
        return CompressResult(summary=read_session_summary(self.history_dir, session_id), extracted_count=0)

    def rebuild_bot_index(self, bot_id: str) -> None:
        paths = self._paths(bot_id)
        sessions = load_sessions_index(self.sessions_index_path)
        l2_items = list_session_summaries(self.history_dir, bot_id, sessions, limit=20)
        cfg = self._cfg()
        embed_port = self._embedding_port(cfg)
        rebuild_index(paths, extra_l2=l2_items, embedding_port=embed_port)
        try:
            from .topic_registry import rebuild_topic_centroids

            rebuild_topic_centroids(paths, embedding_port=embed_port)
        except Exception:  # noqa: BLE001
            pass
        if cfg.get("l3_profile_enabled", True):
            try:
                from .profile_aggregator import refresh_persona_profile

                refresh_persona_profile(self.souls_root, bot_id, force=True)
            except Exception:  # noqa: BLE001
                pass
