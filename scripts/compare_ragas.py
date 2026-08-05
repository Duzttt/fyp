"""Compare two RAGAS evaluation CSVs side by side.

Usage:
    python scripts/compare_ragas.py baseline.csv optimized.csv
"""
from __future__ import annotations

import csv
import math
import sys
from typing import Dict, List


def load_scores(path: str) -> Dict[str, List[float]]:
    metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    scores = {m: [] for m in metrics}
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for m in metrics:
                try:
                    v = float(row.get(m, "") or "")
                    if not math.isnan(v):
                        scores[m].append(v)
                except (ValueError, TypeError):
                    pass
    return scores


def main():
    if len(sys.argv) < 3:
        print("Usage: python compare_ragas.py <baseline.csv> <optimized.csv>")
        sys.exit(1)

    baseline = load_scores(sys.argv[1])
    optimized = load_scores(sys.argv[2])

    metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]

    print(f"\n{'='*65}")
    print(f"  RAGAS Comparison: {sys.argv[1]}  vs  {sys.argv[2]}")
    print(f"{'='*65}")
    print(f"  {'Metric':<22s} {'Baseline':>10s} {'Optimized':>10s} {'Δ':>10s} {'Δ%':>8s}")
    print(f"  {'-'*60}")

    for m in metrics:
        b_vals = baseline.get(m, [])
        o_vals = optimized.get(m, [])
        b_avg = sum(b_vals) / len(b_vals) if b_vals else 0
        o_avg = sum(o_vals) / len(o_vals) if o_vals else 0
        delta = o_avg - b_avg
        pct = (delta / b_avg * 100) if b_avg > 0 else 0
        sign = "+" if delta > 0 else ""
        color = "\033[32m" if delta > 0 else "\033[31m" if delta < 0 else ""
        reset = "\033[0m" if color else ""
        print(
            f"  {m:<22s} {b_avg:>10.4f} {o_avg:>10.4f} {color}{sign}{delta:>9.4f}{reset} {color}{sign}{pct:>6.1f}%{reset}"
        )

    print(f"  {'-'*60}")
    print(f"  Baseline questions: {len(baseline.get('faithfulness', []))}")
    print(f"  Optimized questions: {len(optimized.get('faithfulness', []))}")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
