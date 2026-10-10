"""PersonaMem-style MCQ benchmark for MNEMOS memory system.

Supports:
- Suite B: Chinese lite fixtures (`--suite lite`)
- Suite A: Official PersonaMem 32k subset (`--suite official`)
- Offline mini English smoke (`--suite mini`)

Modes:
- memory: replay conversation into L0/L1, answer using retrieval block only
- baseline: no memory write; use recent conversation tail only
- rag_messages: retrieve top-k relevant raw conversation messages (local similarity, no L1)
- full_context: PersonaMem-style long context in prompt (upper bound)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
MECLAW2_ROOT = BENCH_DIR.parents[1]
REPO_ROOT = MECLAW2_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BENCH_DIR) not in sys.path:
    sys.path.insert(1, str(BENCH_DIR))

from backend.adapters import providers
from backend.domain.brains.orchestrator import MultiBrainOrchestrator  # noqa: F401
from backend.storage.common import read_json
from backend.storage.config_store import normalize_profile

from common import (
    DATA_DIR,
    FIXTURES_DIR,
    CaseResult,
    McqCase,
    cleanup_workspace,
    default_benchmark_config,
    load_json_cases,
    load_official_cases,
    make_temp_workspace,
    parse_predicted_letter,
)
from replay_memory import (
    BOT_ID,
    build_baseline_context,
    build_full_context,
    build_memory_block,
    build_rag_messages_context,
    check_recall_metrics,
    create_memory_brain,
    rebuild_bot_index,
    replay_case,
)
from report import print_summary, summarize_results, write_report


def _resolve_profile(args: argparse.Namespace) -> dict | None:
    if args.dry_run:
        return None
    config_path = Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Config not found: {config_path}")
    cfg = read_json(config_path, {})
    profiles = cfg.get("api_profiles") or []
    if not profiles:
        if args.dry_run:
            return None
        raise SystemExit("No api_profiles in config")
    if args.profile_id:
        match = next((p for p in profiles if p.get("id") == args.profile_id), None)
        if not match:
            raise SystemExit(f"Profile not found: {args.profile_id}")
        return normalize_profile(match)
    enabled = next((p for p in profiles if p.get("enabled", True)), None)
    return normalize_profile(enabled or profiles[0])


def _load_cases(args: argparse.Namespace) -> list[McqCase]:
    if args.suite == "lite":
        return load_json_cases(FIXTURES_DIR / "lite_zh.json")[: args.limit or None]
    if args.suite == "mini":
        return load_json_cases(FIXTURES_DIR / "mini_en.json")[: args.limit or None]
    data_dir = Path(args.data_dir)
    questions = data_dir / "questions_32k.csv"
    contexts = data_dir / "shared_contexts_32k.jsonl"
    if not questions.exists() or not contexts.exists():
        raise SystemExit(
            "Official PersonaMem files missing. Run:\n"
            "  py -3 meclaw2/tests/benchmark/personamem/download_data.py"
        )
    return load_official_cases(questions, contexts, limit=args.limit)


def _chat_once_mcq(profile: dict, prompt: str) -> str:
    """Call the model for a single MCQ question. Handles thinking-style responses."""
    import requests as _req

    p = providers.normalize_profile(profile)
    endpoint = providers.build_endpoint(p)
    headers = providers.build_headers(p)
    payload = providers.build_payload(
        p,
        [{"role": "user", "content": prompt}],
        max_tokens=512,
        stream=False,
    )
    resp = _req.post(endpoint, headers=headers, json=payload, timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(providers.format_http_error(resp.status_code, resp.text))
    data = resp.json()
    if p.get("provider") == "anthropic":
        blocks = data.get("content") or []
        text = "".join((b.get("text") or "") for b in blocks if b.get("type") == "text")
        if not text:
            text = "".join((b.get("thinking") or "") for b in blocks if b.get("type") == "thinking")
        return text
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return msg.get("content") or ""


def _build_mcq_prompt(context_block: str, question: str, options: list[str]) -> str:
    option_text = "\n".join(options)
    return (
        "You are evaluating personalized assistant responses.\n"
        "Use ONLY the provided context about the user.\n\n"
        f"{context_block}\n\n"
        f"User question:\n{question}\n\n"
        "Choose the single best answer for this user.\n"
        "Reply with ONLY one letter: A, B, C, or D.\n\n"
        f"{option_text}"
    )


def _count_recall_lines(memory_block: str) -> int:
    if not memory_block:
        return 0
    return sum(1 for line in memory_block.splitlines() if line.strip().startswith("-"))


def evaluate_case(
    case: McqCase,
    *,
    mode: str,
    profile: dict | None,
    extract_mode: str,
    dry_run: bool,
    baseline_messages: int,
    full_context_chars: int,
    full_context_strategy: str,
    rag_messages: int,
    suite: str,
    cfg: dict,
) -> CaseResult:
    tmp, souls, history = make_temp_workspace(prefix=f"pm_{case.case_id}_")
    session_id = f"s_{case.case_id}"
    effective = {
        "memory_enabled": True,
        "memory_retrieval_enabled": True,
        "memory_write_enabled": mode == "memory",
        "memory_token_budget": cfg.get("memory_token_budget", 1200),
        "l1_extract_every_turn": True,
    }
    brain = create_memory_brain(souls, history, cfg=cfg)
    strategy = cfg.get("memory_retrieval_strategy", "hybrid") if mode == "memory" else mode

    try:
        if mode == "memory":
            replay_case(
                brain,
                case,
                session_id=session_id,
                profile=profile if extract_mode == "llm" else None,
                extract_mode=extract_mode,
                effective_brains=effective,
            )
            rebuild_bot_index(souls)
            context_block = build_memory_block(
                brain,
                query=case.question,
                session_id=session_id,
                budget=int(cfg.get("memory_token_budget", 1200)),
                effective_brains=effective,
            )
        elif mode == "baseline":
            context_block = build_baseline_context(case.conversation, max_messages=baseline_messages)
            strategy = f"tail_{baseline_messages}"
        elif mode == "rag_messages":
            context_block = build_rag_messages_context(case.conversation, case.question, max_messages=rag_messages)
            strategy = f"rag_{rag_messages}"
        elif mode == "full_context":
            if full_context_strategy == "tail":
                msgs = case.conversation[-full_context_chars // 80:] if full_context_chars else case.conversation
                context_block = build_full_context(msgs, max_chars=full_context_chars)
            else:
                context_block = build_full_context(case.conversation, max_chars=full_context_chars)
            strategy = f"fc_{full_context_strategy}"
        else:
            raise ValueError(f"Unknown mode: {mode}")

        storage_hit, retrieval_hit = check_recall_metrics(
            souls,
            case.question,
            case.recall_keywords,
            memory_block=context_block,
        )
        recall_count = _count_recall_lines(context_block)

        if dry_run or not profile or not profile.get("api_key"):
            return CaseResult(
                case_id=case.case_id,
                question_type=case.question_type,
                mode=mode,
                predicted="",
                correct=case.correct,
                is_correct=False,
                storage_hit=storage_hit,
                retrieval_hit=retrieval_hit,
                recall_count=recall_count,
                memory_block_chars=len(context_block),
                error="" if dry_run else "no_api_key",
                suite=suite,
                strategy=strategy,
            )

        prompt = _build_mcq_prompt(context_block, case.question, case.options)
        raw = _chat_once_mcq(profile, prompt)
        predicted = parse_predicted_letter(raw)
        return CaseResult(
            case_id=case.case_id,
            question_type=case.question_type,
            mode=mode,
            predicted=predicted,
            correct=case.correct,
            is_correct=predicted == case.correct,
            storage_hit=storage_hit,
            retrieval_hit=retrieval_hit,
            recall_count=recall_count,
            memory_block_chars=len(context_block),
            raw_output=raw[:500],
            prompt_chars=len(prompt),
            suite=suite,
            strategy=strategy,
        )
    except Exception as exc:  # noqa: BLE001
        return CaseResult(
            case_id=case.case_id,
            question_type=case.question_type,
            mode=mode,
            predicted="",
            correct=case.correct,
            is_correct=False,
            storage_hit=None,
            retrieval_hit=None,
            recall_count=0,
            memory_block_chars=0,
            error=str(exc),
            suite=suite,
            strategy=strategy,
        )
    finally:
        cleanup_workspace(tmp)


def run_benchmark(args: argparse.Namespace) -> dict:
    cases = _load_cases(args)
    if not cases:
        raise SystemExit("No benchmark cases loaded")
    profile = _resolve_profile(args)
    cfg = default_benchmark_config(
        memory_token_budget=args.memory_budget,
        memory_write_enabled=args.mode == "memory",
    )
    results = [
        evaluate_case(
            case,
            mode=args.mode,
            profile=profile,
            extract_mode=args.extract,
            dry_run=args.dry_run,
            baseline_messages=args.baseline_messages,
            full_context_chars=args.full_context_chars,
            full_context_strategy=args.full_context_strategy,
            rag_messages=args.rag_messages,
            suite=args.suite,
            cfg=cfg,
        )
        for case in cases
    ]
    payload = summarize_results(results)
    payload.update(
        {
            "suite": args.suite,
            "mode": args.mode,
            "extract": args.extract,
            "dry_run": args.dry_run,
            "bot_id": BOT_ID,
            "profile_id": args.profile_id or (profile or {}).get("id", ""),
            "full_context_strategy": args.full_context_strategy,
        }
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    default_config = MECLAW2_ROOT / "data" / "config.json"
    if not default_config.exists():
        default_config = Path(os.environ.get("MECLAW2_DATA_DIR", MECLAW2_ROOT / "data")) / "config.json"

    parser = argparse.ArgumentParser(description="MNEMOS PersonaMem MCQ benchmark")
    parser.add_argument("--suite", choices=("lite", "mini", "official"), default="lite")
    parser.add_argument("--mode", choices=("memory", "baseline", "rag_messages", "full_context"), default="memory")
    parser.add_argument("--extract", choices=("heuristic", "llm"), default="heuristic")
    parser.add_argument("--limit", type=int, default=0, help="Max cases (0 = all)")
    parser.add_argument("--config", type=Path, default=default_config)
    parser.add_argument("--profile-id", default="")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--memory-budget", type=int, default=1200)
    parser.add_argument("--baseline-messages", type=int, default=8)
    parser.add_argument("--rag-messages", type=int, default=8, help="Top-k messages for rag_messages mode")
    parser.add_argument("--full-context-chars", type=int, default=24000)
    parser.add_argument("--full-context-strategy", choices=("head", "tail"), default="head",
                        help="Truncation strategy for full_context mode (head=from start, tail=from end)")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM MCQ; report recall metrics only")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report path")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.limit <= 0:
        args.limit = None  # type: ignore[assignment]
    payload = run_benchmark(args)
    print_summary(payload)
    if args.output:
        write_report(args.output, payload)
        print(f"Report written: {args.output}")


if __name__ == "__main__":
    main()
