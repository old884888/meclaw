"""L1 atomic memory extraction from conversation turns."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

from .indexer import index_atom
from .memory_dedupe import find_near_duplicate_atom
from .paths import BotMemoryPaths
from .store_l1 import (
    VALID_POLARITIES,
    VALID_TYPES,
    list_atoms,
    read_atom_file,
    resolve_supersedes_hint,
    write_atom,
)
from .topic_metadata import assign_topic_key, extract_reason, infer_polarity

logger = logging.getLogger(__name__)

_PREFERENCE_HINTS = re.compile(r"喜欢|偏好|希望|不要|别|永远|always|prefer|don't", re.IGNORECASE)
_TODO_HINTS = re.compile(r"需要|待办|下一步|记得|todo|TODO|要实现", re.IGNORECASE)
_CONSTRAINT_HINTS = re.compile(r"必须|不能|禁止|要求|constraint|must not", re.IGNORECASE)

_DEDUPE_SCAN = 50
DEFAULT_MAX_ATOMS = 5
L1_EXTRACT_MODES = frozenset({"heuristic", "llm", "hybrid"})

STRUCTURED_EXTRACT_PROMPT = """Extract 0-{max_atoms} atomic memories from the dialogue below.
Return ONLY a JSON array. Each object MUST include "type" and "content".
Optional fields: subject, predicate, object, topic_key, polarity (positive|negative|switch),
confidence (0-1), reason, supersedes_hint (prior atom id, or short prior content to replace).

Types: fact | preference | constraint | todo

Example:
[{{"type":"preference","content":"User now drinks Americano only","topic_key":"drink","polarity":"switch","reason":"healthier","supersedes_hint":"latte"}}]

User:
{user_message}

Assistant:
{assistant_message}"""


def _norm(text: str) -> str:
    return " ".join((text or "").split()).lower()


def normalize_extract_mode(mode: str | None) -> str:
    name = str(mode or "hybrid").strip().lower()
    return name if name in L1_EXTRACT_MODES else "hybrid"


def normalize_extract_atom(raw: object) -> dict[str, Any] | None:
    """Validate and normalize one structured extraction atom."""
    if not isinstance(raw, dict):
        return None
    content = str(raw.get("content") or "").strip()
    if not content:
        return None
    atom_type = str(raw.get("type") or "fact").strip().lower()
    if atom_type not in VALID_TYPES:
        atom_type = "fact"
    polarity = str(raw.get("polarity") or "").strip().lower()
    if polarity and polarity not in VALID_POLARITIES:
        polarity = ""
    try:
        confidence = float(raw.get("confidence") if raw.get("confidence") is not None else 0.85)
    except (TypeError, ValueError):
        confidence = 0.85
    confidence = max(0.0, min(1.0, confidence))
    topic_key = str(raw.get("topic_key") or "").strip()
    reason = str(raw.get("reason") or "").strip()
    subject = str(raw.get("subject") or "").strip()
    predicate = str(raw.get("predicate") or "").strip()
    obj = str(raw.get("object") or "").strip()
    hint = raw.get("supersedes_hint")
    if hint is None and raw.get("supersedes_id"):
        hint = raw.get("supersedes_id")
    if hint is None and raw.get("supersedes_content"):
        hint = raw.get("supersedes_content")
    return {
        "type": atom_type,
        "content": content[:500],
        "topic_key": topic_key,
        "polarity": polarity,
        "confidence": confidence,
        "reason": reason,
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "supersedes_hint": hint,
    }


def parse_extraction_json(raw_text: str) -> tuple[list[dict[str, Any]], str | None]:
    """Parse LLM output into validated atoms. Returns (atoms, error_message)."""
    text = (raw_text or "").strip()
    if not text:
        return [], "empty response"
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        return [], "no JSON array found"
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        return [], f"invalid JSON: {exc}"
    if not isinstance(payload, list):
        return [], "JSON root is not an array"
    atoms: list[dict[str, Any]] = []
    for item in payload:
        normalized = normalize_extract_atom(item)
        if normalized:
            atoms.append(normalized)
    if not atoms:
        return [], "no valid atoms in array"
    return atoms, None


def build_structured_extract_prompt(
    user_message: str,
    assistant_message: str,
    *,
    max_atoms: int = DEFAULT_MAX_ATOMS,
) -> str:
    limit = max(1, min(10, int(max_atoms or DEFAULT_MAX_ATOMS)))
    return STRUCTURED_EXTRACT_PROMPT.format(
        max_atoms=limit,
        user_message=(user_message or "")[:800],
        assistant_message=(assistant_message or "")[:800],
    )


def _is_duplicate_atom(paths: BotMemoryPaths, content: str) -> bool:
    target = _norm(content)
    if not target:
        return True
    for atom in list_atoms(paths)[:_DEDUPE_SCAN]:
        if _norm(str(atom.get("content") or "")) == target:
            return True
    return False


def _apply_atom_budget(atoms: list[dict[str, Any]], max_atoms: int) -> tuple[list[dict[str, Any]], bool]:
    limit = max(1, int(max_atoms or DEFAULT_MAX_ATOMS))
    if len(atoms) <= limit:
        return atoms, False
    ranked = sorted(atoms, key=lambda a: float(a.get("confidence") or 0.0), reverse=True)
    return ranked[:limit], True


def _maybe_write_atom(
    paths: BotMemoryPaths,
    *,
    atom_type: str,
    content: str,
    session_id: str,
    confidence: float,
    topic_key: str = "",
    polarity: str = "",
    reason: str = "",
    subject: str = "",
    predicate: str = "",
    object_: str = "",
    supersedes_hint: Any = None,
    embedding_port=None,
    dedupe_threshold: float = 0.92,
    topic_cluster_cfg: dict | None = None,
) -> dict[str, Any] | None:
    body = (content or "").strip()
    if not body or _is_duplicate_atom(paths, body):
        return None
    cluster_cfg = topic_cluster_cfg or {}
    topic = assign_topic_key(
        body,
        explicit_key=topic_key,
        paths=paths,
        embedding_port=embedding_port,
        cfg=cluster_cfg,
    )
    pol = polarity if polarity in VALID_POLARITIES else infer_polarity(body)
    reason_text = (reason or extract_reason(body)).strip()
    prior_id = resolve_supersedes_hint(
        paths,
        supersedes_hint,
        topic_key=topic,
        embedding_port=embedding_port,
    )
    if prior_id and pol not in VALID_POLARITIES:
        pol = "switch"
    dup = find_near_duplicate_atom(
        paths,
        content=body,
        topic_key=topic,
        embedding_port=embedding_port,
        threshold=dedupe_threshold,
    )
    if dup:
        return dup
    path = write_atom(
        paths,
        atom_type=atom_type,
        content=body,
        session_id=session_id,
        confidence=confidence,
        resolved_topic=topic,
        polarity=pol,
        reason=reason_text,
        subject=subject,
        predicate=predicate,
        object_=object_,
        supersedes_id=prior_id,
        embedding_port=embedding_port,
        topic_cluster_cfg=cluster_cfg,
    )
    item = read_atom_file(path)
    if item:
        index_atom(paths, item, embedding_port=embedding_port)
    return item


def _write_atoms_from_specs(
    paths: BotMemoryPaths,
    specs: list[dict[str, Any]],
    *,
    session_id: str,
    embedding_port=None,
    dedupe_threshold: float = 0.92,
    max_atoms: int = DEFAULT_MAX_ATOMS,
    on_warning: Callable[[str], None] | None = None,
    topic_cluster_cfg: dict | None = None,
) -> list[dict[str, Any]]:
    trimmed, truncated = _apply_atom_budget(specs, max_atoms)
    if truncated:
        msg = f"L1 extraction truncated to {len(trimmed)} atoms (budget={max_atoms})"
        logger.warning(msg)
        if on_warning:
            on_warning(msg)
    created: list[dict[str, Any]] = []
    for spec in trimmed:
        atom = _maybe_write_atom(
            paths,
            atom_type=str(spec.get("type") or "fact"),
            content=str(spec.get("content") or ""),
            session_id=session_id,
            confidence=float(spec.get("confidence") or 0.85),
            topic_key=str(spec.get("topic_key") or ""),
            polarity=str(spec.get("polarity") or ""),
            reason=str(spec.get("reason") or ""),
            subject=str(spec.get("subject") or ""),
            predicate=str(spec.get("predicate") or ""),
            object_=str(spec.get("object") or ""),
            supersedes_hint=spec.get("supersedes_hint"),
            embedding_port=embedding_port,
            dedupe_threshold=dedupe_threshold,
            topic_cluster_cfg=topic_cluster_cfg,
        )
        if atom:
            created.append(atom)
    return created


def _turn_has_memorable_content(user_message: str) -> bool:
    return len((user_message or "").strip()) >= 8


def extract_atoms_heuristic(
    paths: BotMemoryPaths,
    *,
    session_id: str,
    user_message: str,
    assistant_message: str,
    embedding_port=None,
    dedupe_threshold: float = 0.92,
    max_atoms: int = DEFAULT_MAX_ATOMS,
    on_warning: Callable[[str], None] | None = None,
    topic_cluster_cfg: dict | None = None,
) -> list[dict[str, Any]]:
    """Zero-LLM extraction; picks salient user statements."""
    del assistant_message  # heuristic path only inspects user text
    if not _turn_has_memorable_content(user_message):
        return []

    user = (user_message or "").strip()
    content = user[:500]
    atom_type = "fact"
    if _PREFERENCE_HINTS.search(user):
        atom_type = "preference"
    elif _TODO_HINTS.search(user):
        atom_type = "todo"
    elif _CONSTRAINT_HINTS.search(user):
        atom_type = "constraint"

    specs = [{"type": atom_type, "content": content, "confidence": 0.7}]
    return _write_atoms_from_specs(
        paths,
        specs,
        session_id=session_id,
        embedding_port=embedding_port,
        dedupe_threshold=dedupe_threshold,
        max_atoms=max_atoms,
        on_warning=on_warning,
        topic_cluster_cfg=topic_cluster_cfg,
    )


def extract_atoms_llm(
    profile: dict,
    paths: BotMemoryPaths,
    *,
    session_id: str,
    user_message: str,
    assistant_message: str,
    embedding_port=None,
    dedupe_threshold: float = 0.92,
    max_atoms: int = DEFAULT_MAX_ATOMS,
    on_warning: Callable[[str], None] | None = None,
    topic_cluster_cfg: dict | None = None,
) -> list[dict[str, Any]]:
    """Structured LLM extraction; falls back to heuristic on failure."""
    fallback_kwargs = {
        "paths": paths,
        "session_id": session_id,
        "user_message": user_message,
        "assistant_message": assistant_message,
        "embedding_port": embedding_port,
        "dedupe_threshold": dedupe_threshold,
        "max_atoms": max_atoms,
        "on_warning": on_warning,
        "topic_cluster_cfg": topic_cluster_cfg,
    }

    def _fallback(reason: str) -> list[dict[str, Any]]:
        msg = f"L1 structured extraction fallback to heuristic: {reason}"
        logger.warning(msg)
        if on_warning:
            on_warning(msg)
        return extract_atoms_heuristic(**fallback_kwargs)

    if not profile or not profile.get("api_key"):
        return _fallback("extraction profile unavailable")

    try:
        from ...adapters import providers

        prompt = build_structured_extract_prompt(
            user_message,
            assistant_message,
            max_atoms=max_atoms,
        )
        raw = providers.chat_once(
            profile,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            timeout=30,
        )
        atoms, err = parse_extraction_json(raw)
        if err:
            return _fallback(err)
        created = _write_atoms_from_specs(
            paths,
            atoms,
            session_id=session_id,
            embedding_port=embedding_port,
            dedupe_threshold=dedupe_threshold,
            max_atoms=max_atoms,
            on_warning=on_warning,
            topic_cluster_cfg=topic_cluster_cfg,
        )
        if created:
            return created
        return _fallback("no atoms written after structured parse")
    except Exception as exc:  # noqa: BLE001
        return _fallback(str(exc))


def extract_atoms(
    paths: BotMemoryPaths,
    *,
    session_id: str,
    user_message: str,
    assistant_message: str,
    mode: str = "hybrid",
    profile: dict | None = None,
    embedding_port=None,
    dedupe_threshold: float = 0.92,
    max_atoms: int = DEFAULT_MAX_ATOMS,
    on_warning: Callable[[str], None] | None = None,
    topic_cluster_cfg: dict | None = None,
) -> list[dict[str, Any]]:
    """Unified L1 extraction entry respecting configured mode."""
    extract_mode = normalize_extract_mode(mode)
    common = {
        "paths": paths,
        "session_id": session_id,
        "user_message": user_message,
        "assistant_message": assistant_message,
        "embedding_port": embedding_port,
        "dedupe_threshold": dedupe_threshold,
        "max_atoms": max_atoms,
        "on_warning": on_warning,
        "topic_cluster_cfg": topic_cluster_cfg,
    }
    if extract_mode == "heuristic":
        return extract_atoms_heuristic(**common)
    if extract_mode == "llm":
        return extract_atoms_llm(profile or {}, **common)
    # hybrid: LLM when profile + memorable content, else heuristic
    if profile and profile.get("api_key") and _turn_has_memorable_content(user_message):
        return extract_atoms_llm(profile, **common)
    return extract_atoms_heuristic(**common)
