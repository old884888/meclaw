"""Smoke tests for PersonaMem-lite benchmark (no LLM, no server)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_SCRIPT = Path(__file__).resolve().parent / "benchmark" / "personamem" / "eval_mcq.py"


def _run(args: list[str]) -> dict:
    py = sys.executable
    proc = subprocess.run(
        [py, str(EVAL_SCRIPT), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    assert "PersonaMem Benchmark Summary" in proc.stdout
    return {"stdout": proc.stdout}


def test_lite_dry_run_recall() -> None:
    """Lite suite has recall_keywords — storage and retrieval rates must be numeric."""
    out = _run(["--suite", "lite", "--mode", "memory", "--dry-run"])
    assert "cases: 10" in out["stdout"]
    assert "storage_hit_rate: 100.0%" in out["stdout"]
    assert "retrieval_hit_rate: 100.0%" in out["stdout"]
    assert "avg_recall_count" in out["stdout"]


def test_mini_dry_run() -> None:
    out = _run(["--suite", "mini", "--mode", "memory", "--dry-run"])
    assert "cases: 2" in out["stdout"]


def test_lite_rag_messages_mode() -> None:
    """rag_messages mode works on lite suite."""
    out = _run(["--suite", "lite", "--mode", "rag_messages", "--dry-run"])
    assert "cases: 10" in out["stdout"]
    assert "avg_recall_count" in out["stdout"]


def test_lite_baseline_mode() -> None:
    out = _run(["--suite", "lite", "--mode", "baseline", "--dry-run"])
    assert "cases: 10" in out["stdout"]


def test_lite_full_context_strategy_tail() -> None:
    out = _run(["--suite", "lite", "--mode", "full_context", "--full-context-strategy", "tail", "--dry-run"])
    assert "cases: 10" in out["stdout"]
    assert "strategy=tail" in out["stdout"]


def test_report_includes_suite_mode() -> None:
    """Summary header always includes suite and mode."""
    out = _run(["--suite", "lite", "--mode", "memory", "--dry-run"])
    assert "suite=lite mode=memory" in out["stdout"]


if __name__ == "__main__":
    test_lite_dry_run_recall()
    test_mini_dry_run()
    test_lite_rag_messages_mode()
    test_lite_baseline_mode()
    test_lite_full_context_strategy_tail()
    test_report_includes_suite_mode()
    print("personamem benchmark smoke OK")
