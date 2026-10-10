"""Reporting helpers for PersonaMem benchmark runs."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from common import CaseResult


def _rate(items: list[CaseResult], attr: str) -> float | None:
    subset = [r for r in items if getattr(r, attr) is not None]
    if not subset:
        return None
    hits = sum(1 for r in subset if getattr(r, attr))
    return round(hits / len(subset), 4)


def summarize_results(results: list[CaseResult]) -> dict[str, Any]:
    total = len(results)
    scored = [r for r in results if not r.error]

    by_type: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "correct": 0, "storage_n": 0, "storage_hit": 0, "retrieval_n": 0, "retrieval_hit": 0}
    )
    for item in results:
        bucket = by_type[item.question_type]
        bucket["n"] += 1
        if item.is_correct:
            bucket["correct"] += 1
        if item.storage_hit is not None:
            bucket["storage_n"] += 1
            if item.storage_hit:
                bucket["storage_hit"] += 1
        if item.retrieval_hit is not None:
            bucket["retrieval_n"] += 1
            if item.retrieval_hit:
                bucket["retrieval_hit"] += 1

    type_summary = {}
    for qtype, bucket in sorted(by_type.items()):
        type_summary[qtype] = {
            "n": bucket["n"],
            "accuracy": round(bucket["correct"] / bucket["n"], 4) if bucket["n"] else None,
            "storage_hit_rate": round(bucket["storage_hit"] / bucket["storage_n"], 4) if bucket["storage_n"] else None,
            "retrieval_hit_rate": round(bucket["retrieval_hit"] / bucket["retrieval_n"], 4)
            if bucket["retrieval_n"]
            else None,
        }

    correct = sum(1 for r in scored if r.is_correct)
    return {
        "n": total,
        "scored_n": len(scored),
        "accuracy": round(correct / len(scored), 4) if scored else None,
        "storage_hit_rate": _rate(results, "storage_hit"),
        "retrieval_hit_rate": _rate(results, "retrieval_hit"),
        "recall_hit_rate": _rate(results, "retrieval_hit"),
        "avg_recall_count": round(sum(r.recall_count for r in results) / total, 2) if total else 0,
        "errors": sum(1 for r in results if r.error),
        "by_question_type": type_summary,
        "results": [asdict(r) for r in results],
    }


def _pct(val: float | None, *, unavailable: str = "n/a (no keywords)") -> str:
    if val is None:
        return unavailable
    return f"{val * 100:.1f}%"


def print_summary(payload: dict[str, Any]) -> None:
    print("=== PersonaMem Benchmark Summary ===")
    suite = payload.get("suite", "")
    mode = payload.get("mode", "")
    strategy = payload.get("full_context_strategy", "")
    meta = f"suite={suite} mode={mode}"
    if mode == "full_context" and strategy:
        meta += f" strategy={strategy}"
    print(meta)
    print(f"cases: {payload.get('n')}  scored: {payload.get('scored_n')}  errors: {payload.get('errors')}")
    acc = payload.get("accuracy")
    storage = payload.get("storage_hit_rate")
    retrieval = payload.get("retrieval_hit_rate")
    if acc is not None:
        print(f"accuracy: {acc * 100:.1f}%")
    print(f"storage_hit_rate: {_pct(storage)}")
    print(f"retrieval_hit_rate: {_pct(retrieval)}")
    print(f"avg_recall_count: {payload.get('avg_recall_count')}")
    by_type = payload.get("by_question_type") or {}
    if by_type:
        print("-- by question_type --")
        for qtype, stats in by_type.items():
            acc_s = stats.get("accuracy")
            storage_s = stats.get("storage_hit_rate")
            retrieval_s = stats.get("retrieval_hit_rate")
            print(
                f"  {qtype}: n={stats.get('n')} acc={_pct(acc_s, unavailable='n/a')} "
                f"storage={_pct(storage_s)} retrieval={_pct(retrieval_s)}"
            )


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
