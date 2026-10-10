"""Side-by-side comparison of two PersonaMem benchmark reports.

Usage:
    py -3 meclaw2/tests/benchmark/personamem/compare_reports.py <reportA.json> <reportB.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _pct(x) -> str:
    return f"{x * 100:.1f}%" if isinstance(x, (int, float)) else "n/a"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: compare_reports.py <A.json> <B.json>")
    a, b = _load(sys.argv[1]), _load(sys.argv[2])
    la, lb = Path(sys.argv[1]).stem, Path(sys.argv[2]).stem

    print(f"\n{'metric':<48}{la:>16}{lb:>16}{'delta':>10}")
    print("-" * 90)

    aa, ba = a.get("accuracy") or 0.0, b.get("accuracy") or 0.0
    print(f"{'OVERALL accuracy':<48}{_pct(aa):>16}{_pct(ba):>16}{(ba-aa)*100:>+9.1f}")
    print(
        f"{'avg_recall_count':<48}"
        f"{a.get('avg_recall_count', 0):>16.2f}{b.get('avg_recall_count', 0):>16.2f}"
        f"{(b.get('avg_recall_count',0)-a.get('avg_recall_count',0)):>+9.2f}"
    )
    print("-" * 90)

    types = sorted(set(a.get("by_question_type", {})) | set(b.get("by_question_type", {})))
    for t in types:
        ta = (a.get("by_question_type", {}).get(t) or {})
        tb = (b.get("by_question_type", {}).get(t) or {})
        acc_a = ta.get("accuracy") or 0.0
        acc_b = tb.get("accuracy") or 0.0
        n = ta.get("n") or tb.get("n") or 0
        label = f"{t} (n={n})"
        print(f"{label:<48}{_pct(acc_a):>16}{_pct(acc_b):>16}{(acc_b-acc_a)*100:>+9.1f}")
    print()


if __name__ == "__main__":
    main()
