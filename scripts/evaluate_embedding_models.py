"""
Embedding Model Evaluation Script

Evaluates 4 embedding models against the retrieval benchmark:
- BAAI/bge-m3
- jinaai/jina-embeddings-v3
- BAAI/bge-large-en-v1.5
- intfloat/e5-large-v2

Usage:
    python scripts/evaluate_embedding_models.py
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.retrieval_evaluator import RetrievalEvaluator, AggregateMetrics
from retrieval.dense_retriever import DenseRetriever


# Configuration
MODELS = [
    "BAAI/bge-m3",
    "jinaai/jina-embeddings-v3",
    "BAAI/bge-large-en-v1.5",
    "intfloat/e5-large-v2",
]

CHUNKS_PATH = PROJECT_ROOT / "data" / "faiss_index" / "chunks.npy"
BENCHMARK_PATH = PROJECT_ROOT / "data" / "evaluation" / "retrieval_benchmark.jsonl"
REPORT_DIR = PROJECT_ROOT / "data" / "evaluation"
REPORT_PATH = REPORT_DIR / "embedding_model_comparison_report.txt"


def load_chunks(chunks_path: Path) -> List[Dict[str, Any]]:
    """
    Load document chunks from chunks.npy file.

    Args:
        chunks_path: Path to chunks.npy file

    Returns:
        List of document dictionaries with 'id' and 'text' keys
    """
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunks file not found: {chunks_path}")

    loaded_chunks = np.load(chunks_path, allow_pickle=True).tolist()
    if not isinstance(loaded_chunks, list):
        loaded_chunks = [loaded_chunks]

    documents = []
    for idx, chunk in enumerate(loaded_chunks):
        if isinstance(chunk, dict):
            text = str(chunk.get("text", ""))
            source = str(chunk.get("source", "unknown"))
            page = chunk.get("page")
        elif isinstance(chunk, str):
            text = chunk
            source = "unknown"
            page = None
        else:
            text = str(chunk)
            source = "unknown"
            page = None

        if text.strip():
            documents.append({
                "id": f"chunk_{idx}",
                "text": text.strip(),
                "source": source,
                "page": page,
            })

    return documents


def evaluate_model(
    model_name: str,
    documents: List[Dict[str, Any]],
    benchmark_queries: List[Dict[str, Any]],
    top_k: int = 10,
) -> Dict[str, Any]:
    """
    Evaluate a single embedding model.

    Args:
        model_name: HuggingFace model name
        documents: List of document chunks
        benchmark_queries: List of benchmark queries
        top_k: Number of results to retrieve

    Returns:
        Dictionary with model metrics
    """
    print(f"\n{'=' * 60}")
    print(f"Evaluating model: {model_name}")
    print(f"{'=' * 60}")

    start_time = time.time()

    try:
        # Create DenseRetriever with the specified model
        print(f"Loading model and building FAISS index...")
        retriever = DenseRetriever(
            documents=documents,
            model_name=model_name,
        )
        print(f"Index built with {retriever.get_document_count()} documents")

        # Create evaluator
        evaluator = RetrievalEvaluator(test_queries=benchmark_queries)

        # Run evaluation
        print(f"Running evaluation with {len(benchmark_queries)} queries...")
        aggregate, results = evaluator.evaluate(retriever, top_k=top_k)

        elapsed = time.time() - start_time

        # Store metrics
        metrics = aggregate.to_dict()
        metrics["model_name"] = model_name
        metrics["elapsed_seconds"] = round(elapsed, 2)

        print(f"Completed in {elapsed:.2f}s")
        print(f"  Recall@5: {metrics['recall_at_5']:.4f}")
        print(f"  MRR: {metrics['mrr']:.4f}")
        print(f"  NDCG@5: {metrics['ndcg_at_5']:.4f}")
        print(f"  p95 latency: {metrics['p95_latency_ms']:.2f}ms")

        return metrics

    except Exception as e:
        print(f"Error evaluating {model_name}: {e}")
        return {
            "model_name": model_name,
            "error": str(e),
            "num_queries": 0,
        }


def generate_comparison_table(all_metrics: List[Dict[str, Any]]) -> str:
    """
    Generate a side-by-side comparison table.

    Args:
        all_metrics: List of metric dictionaries for each model

    Returns:
        Formatted comparison table string
    """
    lines = []
    lines.append("=" * 80)
    lines.append("EMBEDDING MODEL COMPARISON TABLE")
    lines.append("=" * 80)
    lines.append("")

    # Header
    header = f"{'Metric':<20}"
    for m in all_metrics:
        model_short = m["model_name"].split("/")[-1][:15]
        header += f"{model_short:>18}"
    lines.append(header)
    lines.append("-" * 80)

    # Metrics to compare
    metric_keys = [
        ("recall_at_1", "Recall@1"),
        ("recall_at_3", "Recall@3"),
        ("recall_at_5", "Recall@5"),
        ("recall_at_10", "Recall@10"),
        ("precision_at_1", "Precision@1"),
        ("precision_at_5", "Precision@5"),
        ("mrr", "MRR"),
        ("ndcg_at_5", "NDCG@5"),
        ("ndcg_at_10", "NCDG@10"),
        ("p95_latency_ms", "p95 Latency (ms)"),
    ]

    for key, label in metric_keys:
        row = f"{label:<20}"
        values = [m.get(key, 0) for m in all_metrics]
        for val in values:
            if key == "p95_latency_ms":
                row += f"{val:>17.2f}ms"
            else:
                row += f"{val:>18.4f}"
        lines.append(row)

    lines.append("-" * 80)

    # Find best model for key metrics
    best_models = {}
    for key in ["recall_at_5", "mrr", "ndcg_at_5"]:
        valid_metrics = [m for m in all_metrics if "error" not in m]
        if valid_metrics:
            best = max(valid_metrics, key=lambda x: x.get(key, 0))
            best_models[key] = best["model_name"].split("/")[-1]

    lines.append("")
    lines.append("BEST MODEL BY METRIC:")
    for key, label in [("recall_at_5", "Recall@5"), ("mrr", "MRR"), ("ndcg_at_5", "NDCG@5")]:
        if key in best_models:
            lines.append(f"  {label}: {best_models[key]}")

    return "\n".join(lines)


def generate_report(
    all_metrics: List[Dict[str, Any]],
    comparison_table: str,
) -> str:
    """
    Generate the full evaluation report.

    Args:
        all_metrics: List of metric dictionaries for each model
        comparison_table: Formatted comparison table

    Returns:
        Full report string
    """
    lines = []
    lines.append("=" * 80)
    lines.append("EMBEDDING MODEL EVALUATION REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Number of models evaluated: {len(all_metrics)}")
    lines.append(f"Benchmark queries: {BENCHMARK_PATH.name}")
    lines.append("")

    # Per-model details
    lines.append("=" * 80)
    lines.append("PER-MODEL METRICS")
    lines.append("=" * 80)

    for metrics in all_metrics:
        lines.append("")
        lines.append(f"Model: {metrics['model_name']}")
        lines.append("-" * 40)
        if "error" in metrics:
            lines.append(f"  ERROR: {metrics['error']}")
        else:
            lines.append(f"  Queries evaluated: {metrics['num_queries']}")
            lines.append(f"  Recall@1:     {metrics.get('recall_at_1', 0):.4f}")
            lines.append(f"  Recall@3:     {metrics.get('recall_at_3', 0):.4f}")
            lines.append(f"  Recall@5:     {metrics.get('recall_at_5', 0):.4f}")
            lines.append(f"  Recall@10:    {metrics.get('recall_at_10', 0):.4f}")
            lines.append(f"  Precision@1:  {metrics.get('precision_at_1', 0):.4f}")
            lines.append(f"  Precision@5:  {metrics.get('precision_at_5', 0):.4f}")
            lines.append(f"  MRR:          {metrics.get('mrr', 0):.4f}")
            lines.append(f"  NDCG@5:       {metrics.get('ndcg_at_5', 0):.4f}")
            lines.append(f"  NDCG@10:      {metrics.get('ndcg_at_10', 0):.4f}")
            lines.append(f"  p95 Latency:  {metrics.get('p95_latency_ms', 0):.2f}ms")
            lines.append(f"  Total Time:   {metrics.get('elapsed_seconds', 0):.2f}s")

    lines.append("")
    lines.append(comparison_table)

    # Best model recommendation
    lines.append("")
    lines.append("=" * 80)
    lines.append("BEST MODEL RECOMMENDATION")
    lines.append("=" * 80)
    lines.append("")

    valid_metrics = [m for m in all_metrics if "error" not in m]
    if valid_metrics:
        # Recommend based on Recall@5 (primary metric for retrieval)
        best_by_recall = max(valid_metrics, key=lambda x: x.get("recall_at_5", 0))
        best_by_mrr = max(valid_metrics, key=lambda x: x.get("mrr", 0))
        best_by_ndcg = max(valid_metrics, key=lambda x: x.get("ndcg_at_5", 0))

        lines.append("Based on the evaluation results:")
        lines.append(f"  - Best Recall@5:  {best_by_recall['model_name']}")
        lines.append(f"  - Best MRR:       {best_by_mrr['model_name']}")
        lines.append(f"  - Best NDCG@5:    {best_by_ndcg['model_name']}")

        # Overall recommendation (Recall@5 as primary metric)
        lines.append("")
        lines.append(f"RECOMMENDED MODEL: {best_by_recall['model_name']}")
        lines.append(f"  Reason: Highest Recall@5 ({best_by_recall.get('recall_at_5', 0):.4f})")
        lines.append(f"  This model retrieves the most relevant documents in the top 5 results.")
    else:
        lines.append("No valid model results to recommend.")

    lines.append("")
    lines.append("=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)

    return "\n".join(lines)


def main():
    """Main evaluation function."""
    print("=" * 60)
    print("Embedding Model Evaluation Script")
    print("=" * 60)

    # Check if chunks file exists
    if not CHUNKS_PATH.exists():
        print(f"Error: Chunks file not found at {CHUNKS_PATH}")
        print("Please ensure the FAISS index has been built first.")
        sys.exit(1)

    # Check if benchmark file exists
    if not BENCHMARK_PATH.exists():
        print(f"Error: Benchmark file not found at {BENCHMARK_PATH}")
        sys.exit(1)

    # Load chunks
    print(f"\nLoading chunks from {CHUNKS_PATH}...")
    documents = load_chunks(CHUNKS_PATH)
    print(f"Loaded {len(documents)} document chunks")

    # Load benchmark queries
    print(f"Loading benchmark from {BENCHMARK_PATH}...")
    benchmark_queries = RetrievalEvaluator.load_benchmark(BENCHMARK_PATH)
    print(f"Loaded {len(benchmark_queries)} benchmark queries")

    # Evaluate each model
    all_metrics = []
    for model_name in MODELS:
        try:
            metrics = evaluate_model(
                model_name=model_name,
                documents=documents,
                benchmark_queries=benchmark_queries,
                top_k=10,
            )
            all_metrics.append(metrics)
        except Exception as e:
            print(f"Failed to evaluate {model_name}: {e}")
            all_metrics.append({
                "model_name": model_name,
                "error": str(e),
                "num_queries": 0,
            })

    # Generate comparison table
    comparison_table = generate_comparison_table(all_metrics)

    # Generate full report
    report = generate_report(all_metrics, comparison_table)

    # Save report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\nReport saved to: {REPORT_PATH}")

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)
    print(f"Evaluated {len(all_metrics)} models")
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
