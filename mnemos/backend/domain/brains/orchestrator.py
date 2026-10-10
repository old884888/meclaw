"""Multi-brain orchestrator — assembles cache-friendly API messages.

Assembly order (cache-matching physical constraint):
  stable system → semi_stable system → conversation history → dynamic tail

Dynamic blocks (memory, cognitive, summary) are merged and prefixed onto the
last user message so the stable prefix stays byte-stable across turns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..memory.memory_brain import MemoryBrain
from ..memory.protocol import MemoryScope
from ..memory.store_l2 import read_session_summary
from .budgets import estimate_tokens
from .cognitive_brain import build_cognitive_block
from .context_assembler import assemble_api_messages, join_blocks
from .persona_brain import build_persona_block
from .router import RouteDecision, route_intent


@dataclass
class TurnPrepareResult:
    api_messages: list[dict[str, Any]]
    brain_trace: dict[str, Any] = field(default_factory=dict)
    route: RouteDecision | None = None


class MultiBrainOrchestrator:
    def __init__(
        self,
        *,
        souls_root: Path,
        history_dir: Path,
        sessions_index_path: Path,
        config_getter,
    ) -> None:
        self.souls_root = souls_root
        self.history_dir = history_dir
        self.sessions_index_path = sessions_index_path
        self.config_getter = config_getter
        self.memory = MemoryBrain(souls_root, history_dir, sessions_index_path, config_getter)

    def _cfg(self) -> dict:
        return self.config_getter() or {}

    def _brains_cfg(self) -> dict:
        return dict(self._cfg().get("brains") or {})

    def prepare_turn(
        self,
        *,
        bot_id: str,
        session_id: str,
        system_base: str,
        history_messages: list[dict],
        user_query: str,
        max_context: int,
        profile: dict | None = None,
        effective_brains: dict | None = None,
    ) -> TurnPrepareResult:
        cfg = self._cfg()
        brains = dict(effective_brains or self._brains_cfg())
        route = route_intent(
            user_query,
            cognitive_enabled=bool(brains.get("cognitive_enabled", True)),
        )

        trace: dict[str, Any] = {
            "activated": ["executor"],
            "tokens": {
                "system": 0,
                "persona": 0,
                "memory": 0,
                "cognitive": 0,
                "session_summary": 0,
            },
            "compact_tier": 0,
            "context_ratio": 0.0,
            "memory": {
                "recall_count": 0,
                "cross_session": bool(route.cross_session),
                "l0_deep_recall": bool(route.l0_deep_recall),
            },
            "models": {},
            "warnings": [],
        }

        # --- Layer A: stable system (base + persona) ---
        # soul + constraints live in `system_base` (always present). The persona
        # (right) brain only contributes the aggregated L3 user-profile excerpt,
        # which is also stable per-bot, so it is merged into the stable system
        # block to maximise prefix cache reuse.
        stable_parts: list[str] = [system_base]
        trace["tokens"]["system"] = estimate_tokens(system_base)

        if brains.get("persona_enabled", True):
            # Persona brain governs identity (soul, in system_base); mark it
            # activated whenever enabled, regardless of whether an L3 profile
            # excerpt exists yet.
            trace["activated"].append("persona")
            persona_budget = int(brains.get("persona_token_budget") or cfg.get("persona_token_budget") or 400)
            persona_block = build_persona_block(self.souls_root, bot_id, budget_tokens=persona_budget)
            if persona_block:
                stable_parts.append(persona_block)
                trace["tokens"]["persona"] = estimate_tokens(persona_block)

        stable_system = join_blocks(stable_parts)

        # --- Layer C: dynamic blocks (memory, cognitive, summary) ---
        # These change every turn and must NOT be inserted as early system
        # messages; they are injected at the tail (user prefix) by assembler.
        dynamic_blocks: list[str] = []

        session_summary = read_session_summary(self.history_dir, session_id)
        memory_block = ""
        if brains.get("memory_enabled", True) and (
            brains.get("memory_retrieval_enabled", cfg.get("memory_retrieval_enabled", True)) or cfg.get("multi_brain_enabled")
        ):
            scope = MemoryScope(kind="bot", scope_id=bot_id)
            memory_block = self.memory.before_chat(
                scope,
                user_query,
                session_summary,
                int(brains.get("memory_token_budget") or cfg.get("memory_token_budget") or 800),
                session_id=session_id,
                cross_session=route.cross_session,
                l0_deep_recall=route.l0_deep_recall,
                effective_brains=brains,
            )
            if memory_block:
                dynamic_blocks.append(memory_block)
                trace["activated"].append("memory")
                trace["tokens"]["memory"] = estimate_tokens(memory_block)
                recall_lines = [ln for ln in memory_block.splitlines() if ln.strip().startswith("-")]
                trace["memory"]["recall_count"] = max(0, len(recall_lines))
                recall_debug = list(getattr(self.memory, "last_recall_debug", []) or [])
                if recall_debug:
                    trace["memory"]["recall"] = recall_debug
                    top_scores = [d.get("hybrid_score", 0.0) for d in recall_debug]
                    trace["memory"]["top_score"] = max(top_scores) if top_scores else 0.0

        if route.cognitive and brains.get("cognitive_enabled", True):
            cog_budget = int(brains.get("cognitive_token_budget") or cfg.get("cognitive_token_budget") or 300)
            cog_block = build_cognitive_block(user_query, session_summary, budget_tokens=cog_budget)
            if cog_block:
                dynamic_blocks.append(cog_block)
                trace["activated"].append("cognitive")
                trace["tokens"]["cognitive"] = estimate_tokens(cog_block)

        if cfg.get("skill_recall_enabled") or brains.get("skill_recall_enabled"):
            from ..skills.recall import recall_skills_block

            skill_block = recall_skills_block(
                self.souls_root,
                bot_id,
                user_query,
                cfg={**cfg, **brains},
                embedding_port=self.memory._embedding_port(cfg),
            )
            if skill_block:
                dynamic_blocks.append(skill_block)
                trace["activated"].append("learner")
                trace["tokens"]["skill"] = estimate_tokens(skill_block)

        if session_summary:
            summary_block = f"[会话摘要]\n{session_summary[:600]}"
            dynamic_blocks.append(summary_block)
            trace["tokens"]["session_summary"] = estimate_tokens(summary_block)

        # --- History messages ---
        history_msgs = [
            {"role": m["role"], "content": m.get("content", "")}
            for m in history_messages
            if m.get("role") in ("user", "assistant")
        ]

        # --- Assemble with cache-discipline order ---
        api_messages = assemble_api_messages(
            stable_system=stable_system,
            semi_stable_blocks=[],   # reserved: group roster / project overview
            dynamic_blocks=dynamic_blocks,
            history_messages=history_msgs,
        )

        compacted, tier, ratio = self.memory.compact_for_api(
            api_messages,
            session_id=session_id,
            bot_id=bot_id,
            max_context=max_context,
            profile=profile,
            effective_brains=brains,
        )
        trace["compact_tier"] = tier
        trace["context_ratio"] = round(ratio, 3)
        if profile:
            trace["models"]["summary"] = str(profile.get("model") or "")
            trace["models"]["background"] = str(profile.get("model") or "")

        return TurnPrepareResult(api_messages=compacted, brain_trace=trace, route=route)
