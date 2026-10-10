"""Replay conversations into MNEMOS memory layers for benchmark evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from common import McqCase, default_benchmark_config, sanitize_fts_query

if TYPE_CHECKING:
    from backend.domain.memory.memory_brain import MemoryBrain

BOT_ID = "bench_bot"


def _memory_brain_cls():
    from backend.domain.memory.memory_brain import MemoryBrain

    return MemoryBrain


def _memory_scope():
    from backend.domain.memory.protocol import MemoryScope

    return MemoryScope


def _search_memory():
    from backend.domain.memory.indexer import search_memory

    return search_memory


def _ensure_layout():
    from backend.domain.memory.paths import ensure_bot_memory_layout

    return ensure_bot_memory_layout


def _pair_turns(messages: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    idx = 0
    while idx < len(messages) - 1:
        user = messages[idx]
        assistant = messages[idx + 1]
        if user.get("role") == "user" and assistant.get("role") == "assistant":
            pairs.append((user, assistant))
            idx += 2
            continue
        idx += 1
    return pairs


def replay_case(
    brain: MemoryBrain,
    case: McqCase,
    *,
    session_id: str,
    profile: dict | None,
    extract_mode: str = "heuristic",
    effective_brains: dict | None = None,
) -> int:
    """Write L0/L1 evidence by replaying conversation turns. Returns turn count."""
    MemoryScope = _memory_scope()
    scope = MemoryScope(kind="bot", scope_id=BOT_ID)
    accumulated: list[dict[str, Any]] = []
    turns = 0
    for user_msg, assistant_msg in _pair_turns(case.conversation):
        accumulated.append({"role": "user", "content": str(user_msg.get("content") or "")})
        accumulated.append({"role": "assistant", "content": str(assistant_msg.get("content") or "")})
        if extract_mode == "llm" and profile and profile.get("api_key"):
            brain.after_turn(
                scope,
                session_id,
                list(accumulated),
                profile=profile,
                effective_brains=effective_brains,
            )
        else:
            brain.after_turn(
                scope,
                session_id,
                list(accumulated),
                profile=None,
                effective_brains=effective_brains,
            )
        turns += 1
    return turns


def build_memory_block(
    brain: MemoryBrain,
    *,
    query: str,
    session_id: str,
    budget: int = 1200,
    cross_session: bool = False,
    effective_brains: dict | None = None,
) -> str:
    MemoryScope = _memory_scope()
    scope = MemoryScope(kind="bot", scope_id=BOT_ID)
    return brain.before_chat(
        scope,
        query,
        "",
        budget,
        session_id=session_id,
        cross_session=cross_session,
        effective_brains=effective_brains,
    )


def build_baseline_context(messages: list[dict[str, Any]], *, max_messages: int = 8) -> str:
    tail = messages[-max_messages:] if max_messages > 0 else messages
    lines = ["[Recent conversation]"]
    for msg in tail:
        role = msg.get("role", "")
        content = str(msg.get("content") or "")[:500]
        if content:
            lines.append(f"- {role}: {content}")
    return "\n".join(lines)


def build_full_context(messages: list[dict[str, Any]], *, max_chars: int = 24000) -> str:
    lines = ["[Full conversation history]"]
    used = 0
    for msg in messages:
        role = msg.get("role", "")
        content = str(msg.get("content") or "")
        if not content:
            continue
        block = f"- {role}: {content}"
        if used + len(block) > max_chars:
            remaining = max_chars - used
            if remaining > 80:
                lines.append(block[:remaining])
            break
        lines.append(block)
        used += len(block)
    return "\n".join(lines)


def build_rag_messages_context(messages: list[dict[str, Any]], query: str, *, max_messages: int = 8) -> str:
    """Retrieve top-k relevant raw conversation messages using local hybrid similarity."""
    from backend.domain.memory.hybrid import _text_to_vector, _cosine

    q_vec = _text_to_vector(query)
    scored: list[tuple[float, dict[str, Any]]] = []
    for msg in messages:
        content = str(msg.get("content") or "")
        if not content or msg.get("role") == "system":
            continue
        sv = _text_to_vector(content)
        scored.append((_cosine(q_vec, sv), msg))
    scored.sort(key=lambda x: -x[0])
    top = [m for _, m in scored[:max_messages]]
    top.sort(key=lambda m: messages.index(m) if m in messages else 0)
    lines = ["[Relevant conversation messages]"]
    for msg in top:
        role = msg.get("role", "")
        content = str(msg.get("content") or "")[:500]
        if content:
            lines.append(f"- {role}: {content}")
    return "\n".join(lines)


def check_recall_metrics(
    souls_root: Path,
    query: str,
    keywords: list[str],
    *,
    memory_block: str = "",
) -> tuple[bool | None, bool | None]:
    """Return (storage_hit, retrieval_hit). Returns None when no reference keywords available."""
    if not keywords:
        return None, None

    ensure_bot_memory_layout = _ensure_layout()
    search_memory = _search_memory()
    list_atoms = _list_atoms()
    paths = ensure_bot_memory_layout(souls_root, BOT_ID)

    atom_bodies = [str(a.get("content") or "") for a in list_atoms(paths)]
    storage_hit = any(
        kw.lower() in body.lower() for body in atom_bodies for kw in keywords if kw.strip()
    )

    haystacks: list[str] = [memory_block.lower()]
    search_queries = [query, *keywords]
    seen: set[str] = set()
    for raw_q in search_queries:
        safe_q = sanitize_fts_query(raw_q)
        if not safe_q or safe_q in seen:
            continue
        seen.add(safe_q)
        try:
            for hit in search_memory(paths, safe_q, limit=8):
                haystacks.append(str(hit.get("snippet") or "").lower())
                haystacks.append(str(hit.get("body") or "").lower())
        except Exception:  # noqa: BLE001
            continue
    haystacks.extend(body.lower() for body in atom_bodies)
    joined = "\n".join(haystacks)
    retrieval_hit = any(kw.lower() in joined for kw in keywords if kw.strip())
    return storage_hit, retrieval_hit


def _list_atoms():
    from backend.domain.memory.store_l1 import list_atoms

    return list_atoms


def rebuild_bot_index(souls_root: Path, cfg: dict | None = None) -> None:
    from backend.domain.memory.embedding.factory import create_embedding_port
    from backend.domain.memory.indexer import rebuild_index

    paths = _ensure_layout()(souls_root, BOT_ID)
    port = create_embedding_port(cfg or {"embedding_provider": "off"})
    rebuild_index(paths, embedding_port=port)


def create_memory_brain(
    souls_root: Path,
    history_dir: Path,
    *,
    cfg: dict[str, Any] | None = None,
) -> MemoryBrain:
    sessions_index = history_dir / "sessions.json"
    state = {"cfg": cfg or default_benchmark_config()}

    def _getter() -> dict[str, Any]:
        return state["cfg"]

    MemoryBrain = _memory_brain_cls()
    return MemoryBrain(souls_root, history_dir, sessions_index, _getter)
