"""
Reranker model benchmark script.

Evaluates multiple cross-encoder reranker models on the same retrieval candidates
and compares quality (Recall, MRR, NDCG) and performance (latency, throughput).

Models evaluated:
  1. cross-encoder/ms-marco-MiniLM-L6-v2  (default, 22.7M params)
  2. BAAI/bge-reranker-base                (278M params)
  3. BAAI/bge-reranker-v2-m3               (568M params)
  4. jina-ai/jina-reranker-v2              (278M params)
  5. Qwen/Qwen3-Reranker-0.6B             (0.6B params)

Usage:
    python scripts/evaluate_rerankers.py
    python scripts/evaluate_rerankers.py --models bge-reranker-v2-m3 ms-marco-MiniLM-L6-v2
    python scripts/evaluate_rerankers.py --device cuda --skip-large
    python scripts/evaluate_rerankers.py --json --output evaluation/results/reranker_results.json
    python scripts/evaluate_rerankers.py --candidate-top-k 50 --eval-top-k 10
"""

import argparse
import json
import os
import sys
import time
from typing import List

sys.path.insert(0, ".")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
import django  # noqa: E402

django.setup()

from evaluation.reranker_evaluator import (  # noqa: E402
    CrossEncoderAdapter,
    JinaRerankerAdapter,
    Qwen3RerankerAdapter,
    RerankerEvaluator,
    generate_comparison_table,
)


# Known model aliases for --models flag
MODEL_ALIASES = {
    "ms-marco": "cross-encoder/ms-marco-MiniLM-L6-v2",
    "ms-marco-MiniLM-L6-v2": "cross-encoder/ms-marco-MiniLM-L6-v2",
    "bge-reranker-base": "BAAI/bge-reranker-base",
    "bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
    "jina-reranker-v2": "jinaai/jina-reranker-v2-base-multilingual",
    "qwen3-reranker": "Qwen/Qwen3-Reranker-0.6B",
}

DEFAULT_BENCHMARK = "data/evaluation/retrieval_benchmark.jsonl"


def _resolve_model(name: str) -> str:
    """Resolve a model alias to its full HuggingFace model ID."""
    return MODEL_ALIASES.get(name, name)


def _build_adapters(model_names: List[str], device: str, skip_large: bool) -> List:
    """Build reranker adapters from model name list."""
    from evaluation.reranker_evaluator import BaseRerankerAdapter

    adapters: List[BaseRerankerAdapter] = []

    model_configs = {
        "cross-encoder/ms-marco-MiniLM-L6-v2": {
            "cls": CrossEncoderAdapter,
            "params": "22.7M",
            "desc": "Default cross-encoder, fast and lightweight",
        },
        "BAAI/bge-reranker-base": {
            "cls": CrossEncoderAdapter,
            "params": "278M",
            "desc": "BGE reranker base, multilingual support",
        },
        "BAAI/bge-reranker-v2-m3": {
            "cls": CrossEncoderAdapter,
            "params": "568M",
            "desc": "BGE reranker v2 M3, best multilingual performance",
        },
        "jinaai/jina-reranker-v2-base-multilingual": {
            "cls": JinaRerankerAdapter,
            "params": "278M",
            "desc": "Jina reranker v2, multilingual with fine-grained relevance",
        },
        "Qwen/Qwen3-Reranker-0.6B": {
            "cls": Qwen3RerankerAdapter,
            "params": "0.6B",
            "desc": "Qwen3 reranker, instruction-aware (0.6B variant)",
        },
    }

    for name in model_names:
        model_id = _resolve_model(name)

        # Skip large models if requested
        if skip_large and "qwen3" in model_id.lower():
            print(f"Skipping large model: {model_id}", file=sys.stderr)
            continue

        cfg = model_configs.get(model_id)
        if cfg is None:
            print(f"Unknown model: {name} (resolved to {model_id})", file=sys.stderr)
            print(f"Known models: {', '.join(model_configs.keys())}", file=sys.stderr)
            continue

        adapter = cfg["cls"](
            model_id=model_id,
            device=device,
            parameters=cfg["params"],
            description=cfg["desc"],
        )
        adapters.append(adapter)

    return adapters


def _print_summary_table(results, json_output=False):
    """Print the comparison table or JSON."""
    if json_output:
        payload = {
            "results": [r.to_dict() for r in results],
            "comparison": {
                "best_mrr": (
                    max(results, key=lambda x: x.mrr).model_info.name
                    if results
                    else None
                ),
                "best_latency_p95": (
                    min(results, key=lambda x: x.latency.p95_ms).model_info.name
                    if results
                    else None
                ),
            },
        }
        print(json.dumps(payload, indent=2))
    else:
        print(generate_comparison_table(results))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--benchmark",
        default=DEFAULT_BENCHMARK,
        help=f"Path to benchmark JSONL (default: {DEFAULT_BENCHMARK})",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=[
            "cross-encoder/ms-marco-MiniLM-L6-v2",
            "BAAI/bge-reranker-base",
            "BAAI/bge-reranker-v2-m3",
            "jinaai/jina-reranker-v2-base-multilingual",
        ],
        help="Model IDs or aliases to evaluate",
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cpu", "cuda", "mps"],
        help="Device for model inference (default: auto)",
    )
    parser.add_argument(
        "--candidate-top-k",
        type=int,
        default=30,
        help="Number of candidates to retrieve before reranking (default: 30)",
    )
    parser.add_argument(
        "--eval-top-k",
        type=int,
        default=10,
        help="Top-k cutoff for evaluation metrics (default: 10)",
    )
    parser.add_argument(
        "--skip-large",
        action="store_true",
        help="Skip models larger than 1B parameters (e.g., Qwen3-Reranker-4B)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output machine-readable JSON",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save JSON results to file",
    )
    args = parser.parse_args()

    print("=" * 60, file=sys.stderr)
    print("RERANKER MODEL BENCHMARK", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Benchmark:  {args.benchmark}", file=sys.stderr)
    print(f"Models:     {len(args.models)}", file=sys.stderr)
    print(f"Device:     {args.device}", file=sys.stderr)
    print(f"Cand top_k: {args.candidate_top_k}", file=sys.stderr)
    print(f"Eval top_k: {args.eval_top_k}", file=sys.stderr)
    print(f"Skip large: {args.skip_large}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    adapters = _build_adapters(args.models, args.device, args.skip_large)
    if not adapters:
        print("No valid models to evaluate.", file=sys.stderr)
        sys.exit(1)

    evaluator = RerankerEvaluator(
        benchmark_path=args.benchmark,
        candidate_top_k=args.candidate_top_k,
        eval_top_k=args.eval_top_k,
        device=args.device,
        skip_large=args.skip_large,
    )

    started = time.perf_counter()
    results = evaluator.run(adapters)
    elapsed = time.perf_counter() - started

    print(f"\nTotal benchmark time: {elapsed:.1f}s", file=sys.stderr)

    _print_summary_table(results, json_output=args.json_output)

    # Save to file if requested
    if args.output and results:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "benchmark": args.benchmark,
                    "candidate_top_k": args.candidate_top_k,
                    "eval_top_k": args.eval_top_k,
                    "device": args.device,
                    "elapsed_seconds": round(elapsed, 2),
                    "results": [r.to_dict() for r in results],
                },
                f,
                indent=2,
            )
        print(f"\nResults saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
