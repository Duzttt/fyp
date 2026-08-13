"""RAGAS V2 Evaluation CLI - Uses RAGAS v0.4.x API.

Evaluate the RAG pipeline on a JSONL dataset of {question, ground_truth}.

Usage:
    python scripts/ragas_v2_eval.py evaluate \\
        --dataset eval_baseline.jsonl \\
        --out results/ragas_v2_result.csv \\
        --judge-base-url http://localhost:8080/v1 \\
        --judge-model deepseek/deepseek-v4-flash \\
        --judge-api-key local \\
        --top-k 5
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _setup_django() -> None:
    """Set up Django environment (lazy, only when running as a script)."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
    import django

    django.setup()


def cmd_evaluate(args: argparse.Namespace) -> None:
    """Run RAGAS evaluation on a JSONL dataset."""
    _setup_django()

    from app.services.ragas_v2 import RAGASEvaluatorV2

    evaluator = RAGASEvaluatorV2(
        judge_base_url=args.judge_base_url,
        judge_model=args.judge_model,
        judge_api_key=args.judge_api_key,
    )

    print(f"Dataset: {args.dataset}")
    print(f"Judge: {args.judge_base_url} / {args.judge_model}")
    print(f"Top-K: {args.top_k}")

    result = evaluator.evaluate(
        dataset_path=args.dataset,
        top_k=args.top_k,
        ragas_timeout=args.timeout,
        ragas_max_workers=args.max_workers,
    )

    report = RAGASEvaluatorV2.format_report(result)
    print(report)
    print(f"\nCSV saved to: {result['csv_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="RAGAS V2 Evaluation CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    evl = sub.add_parser("evaluate", help="RAGAS evaluation on JSONL dataset")
    evl.add_argument("--dataset", required=True, help="JSONL dataset path")
    evl.add_argument("--out", required=True, help="Output CSV path")
    evl.add_argument("--judge-base-url", help="Judge LLM base URL (default: auto)")
    evl.add_argument("--judge-model", help="Judge model name (default: auto)")
    evl.add_argument("--judge-api-key", default=None, help="Judge API key")
    evl.add_argument(
        "--top-k", type=int, default=5, help="Number of chunks to retrieve"
    )
    evl.add_argument(
        "--timeout", type=int, default=300, help="RAGAS timeout in seconds"
    )
    evl.add_argument(
        "--max-workers",
        type=int,
        default=2,
        help="Max concurrent workers (keep low for rate limits)",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        cmd_evaluate(args)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
