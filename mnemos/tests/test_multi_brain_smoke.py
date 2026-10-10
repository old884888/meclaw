"""Unit smoke tests for multi-brain (no server, no LLM)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.brains.budgets import truncate_to_budget
from backend.domain.brains.orchestrator import MultiBrainOrchestrator
from backend.domain.brains.router import route_intent
from backend.domain.memory.compaction import compact_messages, tier1_snip
from backend.domain.memory.memory_brain import MemoryBrain
from backend.domain.memory.paths import ensure_bot_memory_layout
from backend.domain.memory.protocol import MemoryScope
from backend.domain.memory.store_l1 import write_atom
from backend.storage.config_store import brains_config_for_bot, normalize_bot, normalize_config
from backend.storage.history_store import save_sessions_index


def test_router_activation_matrix() -> None:
    d1 = route_intent("你好")
    assert d1.cognitive is False
    assert d1.cross_session is False

    d2 = route_intent("继续上次的方案")
    assert d2.cross_session is True

    d3 = route_intent("请给出实现步骤")
    assert d3.cognitive is True


def test_orchestrator_message_order() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        souls = root / "souls"
        history = root / "history"
        history.mkdir(parents=True)
        souls.mkdir(parents=True)
        bot_id = "b_test"
        (souls / bot_id).mkdir()
        (souls / bot_id / "soul.md").write_text("你是测试助手", encoding="utf-8")
        ensure_bot_memory_layout(souls, bot_id)
        save_sessions_index(history / "sessions.json", [], backup=False)

        cfg = normalize_config({"multi_brain_enabled": True})
        orch = MultiBrainOrchestrator(
            souls_root=souls,
            history_dir=history,
            sessions_index_path=history / "sessions.json",
            config_getter=lambda: cfg,
        )
        messages = [{"role": "user", "content": "hello", "id": "m1"}]
        result = orch.prepare_turn(
            bot_id=bot_id,
            session_id="s_test",
            system_base="base",
            history_messages=messages,
            user_query="hello",
            max_context=65536,
        )
        roles = [m["role"] for m in result.api_messages]
        assert roles[0] == "system"
        assert roles[-1] == "user"
        assert "persona" in result.brain_trace.get("activated", [])
        trace = result.brain_trace
        assert "tokens" in trace
        assert "memory" in trace
        assert "models" in trace
        assert "warnings" in trace
        assert isinstance(trace["tokens"].get("system"), int)
        assert trace["memory"].get("recall_count") is not None


def test_trace_schema_defaults() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        souls = root / "souls"
        history = root / "history"
        history.mkdir(parents=True)
        souls.mkdir(parents=True)
        bot_id = "b_trace"
        (souls / bot_id).mkdir()
        (souls / bot_id / "soul.md").write_text("test", encoding="utf-8")
        ensure_bot_memory_layout(souls, bot_id)
        save_sessions_index(history / "sessions.json", [], backup=False)
        cfg = normalize_config({"multi_brain_enabled": True})
        orch = MultiBrainOrchestrator(
            souls_root=souls,
            history_dir=history,
            sessions_index_path=history / "sessions.json",
            config_getter=lambda: cfg,
        )
        result = orch.prepare_turn(
            bot_id=bot_id,
            session_id="s_trace",
            system_base="base",
            history_messages=[{"role": "user", "content": "hi"}],
            user_query="hi",
            max_context=65536,
        )
        trace = result.brain_trace
        for key in ("activated", "tokens", "compact_tier", "context_ratio", "memory", "models", "warnings"):
            assert key in trace
        for tok_key in ("system", "persona", "memory", "cognitive", "session_summary"):
            assert tok_key in trace["tokens"]


def test_budget_truncation() -> None:
    long_text = "测" * 500
    out = truncate_to_budget(long_text, 50)
    assert len(out) < len(long_text)


def test_l0_write_and_l1_index() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        souls = root / "souls"
        history = root / "history"
        history.mkdir(parents=True)
        bot_id = "b_mem"
        paths = ensure_bot_memory_layout(souls, bot_id)
        save_sessions_index(history / "sessions.json", [], backup=False)
        cfg = normalize_config({"multi_brain_enabled": True, "memory_write_enabled": True})
        brain = MemoryBrain(souls, history, history / "sessions.json", lambda: cfg)
        scope = MemoryScope(kind="bot", scope_id=bot_id)
        msgs = [
            {"role": "user", "content": "我喜欢简洁回答"},
            {"role": "assistant", "content": "好的"},
        ]
        brain.after_turn(scope, "s_sess", msgs, profile=None)
        assert any(paths.l0_dir.glob("*.json"))
        write_atom(paths, atom_type="preference", content="用户喜欢简洁", session_id="s_sess")
        block = brain.before_chat(scope, "简洁", "", 800, session_id="s_sess")
        assert block == "" or "记忆" in block or "简洁" in block


def test_tier1_snip() -> None:
    long_content = "x" * 3000
    out = tier1_snip([{"role": "assistant", "content": long_content, "id": "a1"}])
    assert len(out[0]["content"]) < len(long_content)


def test_replacement_cache_monotonic() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp)
        msgs = [{"role": "assistant", "content": "y" * 600, "id": "fixed_id"}]
        high_ctx = 1000
        r1 = compact_messages(
            msgs,
            session_id="s1",
            max_context=high_ctx,
            cache_dir=cache_dir,
            tier1_pct=1,
            tier2_pct=1,
            protection_zone_tokens=0,
        )
        r2 = compact_messages(
            msgs,
            session_id="s1",
            max_context=high_ctx,
            cache_dir=cache_dir,
            tier1_pct=1,
            tier2_pct=1,
            protection_zone_tokens=0,
        )
        assert r1.messages[0]["content"] == r2.messages[0]["content"]


def test_brains_merge_bot_overrides() -> None:
    cfg = normalize_config(
        {
            "multi_brain_enabled": True,
            "brains": {"persona_enabled": True, "cognitive_enabled": True},
            "memory_token_budget": 800,
            "persona_token_budget": 400,
            "cognitive_token_budget": 300,
        }
    )
    bot = normalize_bot(
        {
            "id": "b_cfg",
            "name": "cfg",
            "profile_id": "",
            "model": "",
            "brains": {
                "persona_enabled": False,
                "memory_token_budget": 520,
            },
        }
    )
    merged = brains_config_for_bot(cfg, bot)
    assert merged["persona_enabled"] is False
    assert merged["memory_token_budget"] == 520
    assert merged["cognitive_enabled"] is True


def test_l1_uses_profile_model_when_available() -> None:
    from backend.adapters import providers

    called_model: dict[str, str] = {}
    original_chat_once = providers.chat_once

    def fake_chat_once(profile: dict, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        called_model["model"] = str(profile.get("model") or "")
        return '[{"type":"fact","content":"用户提到偏好"}]'

    providers.chat_once = fake_chat_once
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            souls = root / "souls"
            history = root / "history"
            history.mkdir(parents=True)
            bot_id = "b_mem_bg"
            save_sessions_index(history / "sessions.json", [], backup=False)
            cfg = normalize_config({"multi_brain_enabled": True, "memory_write_enabled": True, "l1_extract_every_turn": True})
            brain = MemoryBrain(souls, history, history / "sessions.json", lambda: cfg)
            scope = MemoryScope(kind="bot", scope_id=bot_id)
            msgs = [
                {"role": "user", "content": "我喜欢简洁回答"},
                {"role": "assistant", "content": "明白了"},
            ]
            brain.after_turn(scope, "s_bg", msgs, profile={"api_key": "k", "model": "gpt-4o-mini"})
            assert called_model.get("model") == "gpt-4o-mini"
    finally:
        providers.chat_once = original_chat_once


def test_post_turn_hooks_uses_extraction_profile() -> None:
    import asyncio
    import backend.main as app_main

    calls: dict[str, object] = {"roles": []}
    original_reload = app_main.ctx.reload_config
    original_orchestrator = app_main._orchestrator
    original_profile_for_bot = app_main._profile_for_bot

    class _MemoryStub:
        def after_turn(
            self,
            scope,  # noqa: ANN001
            session_id,  # noqa: ANN001
            messages,  # noqa: ANN001
            *,
            profile=None,  # noqa: ANN001
            effective_brains=None,  # noqa: ANN001
        ) -> None:
            calls["profile_model"] = (profile or {}).get("model")
            calls["effective"] = effective_brains

    class _OrchStub:
        memory = _MemoryStub()

    def _fake_profile_for_bot(bot: dict, role: str = "executor") -> dict:
        calls["roles"].append(role)
        return {"api_key": "k", "model": "gpt-4o-mini-bg"}

    try:
        app_main.ctx.reload_config = lambda: normalize_config({"multi_brain_enabled": True})
        app_main._orchestrator = lambda: _OrchStub()
        app_main._profile_for_bot = _fake_profile_for_bot
        bot = {"id": "b_bg", "brains": {"learner_enabled": False}}
        messages = [{"role": "user", "content": "u"}, {"role": "assistant", "content": "a"}]
        asyncio.run(app_main._post_turn_hooks("s_bg", bot, messages, "u", "a"))
        assert "extraction" in calls["roles"]
        assert calls.get("profile_model") == "gpt-4o-mini-bg"
        assert isinstance(calls.get("effective"), dict)
    finally:
        app_main.ctx.reload_config = original_reload
        app_main._orchestrator = original_orchestrator
        app_main._profile_for_bot = original_profile_for_bot


def test_tier3_heuristic_summary() -> None:
    from backend.domain.memory.tier3_summarizer import _heuristic_summary_merge, save_summary_meta, load_summary_meta
    from backend.domain.memory.store_l2 import write_session_summary, read_session_summary

    with tempfile.TemporaryDirectory() as tmp:
        history = Path(tmp)
        (history / "summaries").mkdir(parents=True)
        session_id = "s_t3"
        delta = [
            {"role": "user", "content": "继续优化记忆系统"},
            {"role": "assistant", "content": "好的，我会帮你完成"},
        ]
        merged = _heuristic_summary_merge("旧摘要", delta, 2000)
        assert "继续优化" in merged
        write_session_summary(history, session_id, merged)
        save_summary_meta(history, session_id, {"summarized_message_count": 2, "last_summary": merged[:100]})
        assert read_session_summary(history, session_id)
        assert load_summary_meta(history, session_id)["summarized_message_count"] == 2


def test_orchestrator_stable_prefix_no_dynamic_content() -> None:
    """Stable system must not contain query-derived memory / cognitive / summary text."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        souls = root / "souls"
        history = root / "history"
        history.mkdir(parents=True)
        bot_id = "b_cache"
        (souls / bot_id).mkdir(parents=True)
        (souls / bot_id / "soul.md").write_text("stable persona", encoding="utf-8")
        ensure_bot_memory_layout(souls, bot_id)
        # Write a session summary to trigger dynamic injection
        summary_dir = history / "summaries"
        summary_dir.mkdir(parents=True)
        (summary_dir / "s_cache_summary.md").write_text("这是会话摘要内容", encoding="utf-8")
        save_sessions_index(history / "sessions.json", [], backup=False)
        cfg = normalize_config({"multi_brain_enabled": True, "memory_retrieval_enabled": True})
        orch = MultiBrainOrchestrator(
            souls_root=souls,
            history_dir=history,
            sessions_index_path=history / "sessions.json",
            config_getter=lambda: cfg,
        )
        result = orch.prepare_turn(
            bot_id=bot_id,
            session_id="s_cache",
            system_base="base system",
            history_messages=[{"role": "user", "content": "用户问题"}],
            user_query="用户问题",
            max_context=65536,
        )
        msgs = result.api_messages
        # Stable layer: first system message must not contain the summary
        system_msgs = [m for m in msgs if m["role"] == "system"]
        assert system_msgs, "must have a system message"
        stable_content = system_msgs[0]["content"]
        assert "会话摘要" not in stable_content, "summary must not appear in stable system"
        # Dynamic content injected into last user message
        user_msgs = [m for m in msgs if m["role"] == "user"]
        assert user_msgs, "must have at least one user message"
        last_user = user_msgs[-1]["content"]
        assert "会话摘要" in last_user or "[Session context]" in last_user, \
            "dynamic content should appear in last user message"


def main() -> None:
    test_router_activation_matrix()
    test_orchestrator_message_order()
    test_trace_schema_defaults()
    test_budget_truncation()
    test_l0_write_and_l1_index()
    test_tier1_snip()
    test_replacement_cache_monotonic()
    test_brains_merge_bot_overrides()
    test_l1_uses_profile_model_when_available()
    test_post_turn_hooks_uses_extraction_profile()
    test_tier3_heuristic_summary()
    test_orchestrator_stable_prefix_no_dynamic_content()
    print("multi-brain smoke tests OK")


if __name__ == "__main__":
    main()
