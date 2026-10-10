"""Shared types and helpers for PersonaMem-style MNEMOS benchmarks."""

from __future__ import annotations

import ast
import csv
import json
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DATA_DIR = Path(__file__).resolve().parent / "data"

OPTION_LETTER_RE = re.compile(r"\b([A-D])\b", re.IGNORECASE)


def sanitize_fts_query(query: str) -> str:
    """Strip characters that break SQLite FTS5 MATCH syntax."""
    from backend.domain.memory.indexer import sanitize_fts_query as _sanitize

    return _sanitize(query)


@dataclass
class McqCase:
    case_id: str
    question_type: str
    conversation: list[dict[str, Any]]
    question: str
    options: list[str]
    correct: str
    recall_keywords: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseResult:
    case_id: str
    question_type: str
    mode: str
    predicted: str
    correct: str
    is_correct: bool
    storage_hit: bool | None
    retrieval_hit: bool | None
    recall_count: int
    memory_block_chars: int
    error: str = ""
    raw_output: str = ""
    prompt_chars: int = 0
    suite: str = ""
    strategy: str = ""


def normalize_option_letter(value: str) -> str:
    text = (value or "").strip().upper()
    if len(text) == 1 and text in "ABCD":
        return text
    match = OPTION_LETTER_RE.search(text)
    return match.group(1).upper() if match else text[:1].upper()


def format_options(options: Iterable[str]) -> list[str]:
    out: list[str] = []
    letters = "ABCD"
    for idx, raw in enumerate(options):
        text = str(raw or "").strip()
        if not text:
            continue
        letter = letters[idx] if idx < len(letters) else chr(ord("A") + idx)
        if re.match(r"^[A-D][\).:\s]", text, re.IGNORECASE):
            out.append(text)
        else:
            out.append(f"{letter}) {text}")
    return out


def parse_options_field(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return format_options(parsed)
    except json.JSONDecodeError:
        pass
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return format_options(parsed)
    except (SyntaxError, ValueError):
        pass
    if "|" in text:
        return format_options(part.strip() for part in text.split("|") if part.strip())
    return format_options([text])


def parse_predicted_letter(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    match = OPTION_LETTER_RE.search(text)
    return match.group(1).upper() if match else ""


def load_json_cases(path: Path) -> list[McqCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("cases") if isinstance(payload, dict) else payload
    cases: list[McqCase] = []
    for item in items or []:
        cases.append(
            McqCase(
                case_id=str(item.get("id") or item.get("case_id") or ""),
                question_type=str(item.get("question_type") or "general"),
                conversation=list(item.get("conversation") or []),
                question=str(item.get("question") or item.get("user_question_or_message") or ""),
                options=format_options(item.get("options") or []),
                correct=normalize_option_letter(str(item.get("correct") or item.get("correct_answer") or "")),
                recall_keywords=[str(x) for x in (item.get("recall_keywords") or []) if str(x).strip()],
                metadata=dict(item.get("metadata") or {}),
            )
        )
    return cases


def load_shared_contexts(path: Path) -> dict[str, list[dict[str, Any]]]:
    mapping: dict[str, list[dict[str, Any]]] = {}
    if not path.exists():
        return mapping
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if isinstance(row, list):
            mapping[f"line_{len(mapping)}"] = row
            continue
        if isinstance(row, dict):
            # PersonaMem official format: {"<shared_context_id>": [messages...]}
            if not any(k in row for k in ("shared_context_id", "context", "messages", "conversation")):
                for key, messages in row.items():
                    if isinstance(messages, list):
                        mapping[str(key)] = messages
                continue
        key = str(
            row.get("shared_context_id")
            or row.get("id")
            or row.get("context_id")
            or f"ctx_{len(mapping)}"
        )
        messages = row.get("context") or row.get("messages") or row.get("conversation") or []
        if isinstance(messages, list):
            mapping[key] = messages
    return mapping


def load_official_cases(
    questions_csv: Path,
    contexts_jsonl: Path,
    *,
    limit: int | None = None,
) -> list[McqCase]:
    contexts = load_shared_contexts(contexts_jsonl)
    cases: list[McqCase] = []
    with questions_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ctx_id = str(row.get("shared_context_id") or "")
            messages = list(contexts.get(ctx_id) or [])
            end_idx_raw = row.get("end_index_in_shared_context") or row.get("end_index") or len(messages)
            try:
                end_idx = int(end_idx_raw)
            except (TypeError, ValueError):
                end_idx = len(messages)
            conversation = messages[: max(0, end_idx)]
            correct_raw = str(row.get("correct_answer") or "")
            correct = normalize_option_letter(correct_raw)
            if correct not in "ABCD" and correct_raw:
                options_preview = parse_options_field(str(row.get("all_options") or ""))
                for opt in options_preview:
                    if correct_raw.strip() in opt or opt.endswith(correct_raw.strip()):
                        correct = normalize_option_letter(opt)
                        break
            cases.append(
                McqCase(
                    case_id=str(row.get("question_id") or row.get("persona_id") or f"q_{len(cases)}"),
                    question_type=str(row.get("question_type") or "official"),
                    conversation=conversation,
                    question=str(row.get("user_question_or_message") or row.get("question") or ""),
                    options=parse_options_field(str(row.get("all_options") or "")),
                    correct=correct,
                    recall_keywords=[],
                    metadata={
                        "persona_id": row.get("persona_id"),
                        "shared_context_id": ctx_id,
                        "distance_to_ref_in_tokens": row.get("distance_to_ref_in_tokens"),
                        "context_length_in_tokens": row.get("context_length_in_tokens"),
                    },
                )
            )
            if limit and len(cases) >= limit:
                break
    return cases


def make_temp_workspace(prefix: str = "personamem_") -> tuple[Path, Path, Path]:
    tmp = Path(tempfile.mkdtemp(prefix=prefix))
    souls = tmp / "souls"
    history = tmp / "history"
    souls.mkdir(parents=True)
    history.mkdir(parents=True)
    (history / "sessions.json").write_text("[]", encoding="utf-8")
    bot_dir = souls / "bench_bot"
    bot_dir.mkdir(parents=True)
    (bot_dir / "soul.md").write_text("You are a helpful assistant.", encoding="utf-8")
    return tmp, souls, history


def cleanup_workspace(tmp: Path) -> None:
    shutil.rmtree(tmp, ignore_errors=True)


def default_benchmark_config(**overrides: Any) -> dict[str, Any]:
    cfg = {
        "multi_brain_enabled": True,
        "memory_enabled": True,
        "memory_retrieval_enabled": True,
        "memory_write_enabled": True,
        "memory_token_budget": 1200,
        "l1_extract_every_turn": True,
        "memory_retrieval_strategy": "hybrid",
    }
    cfg.update(overrides)
    return cfg
