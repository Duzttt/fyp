"""
Performance benchmark for retrieval systems.

This script provides comprehensive benchmarking for:
- BM25 retrieval
- Dense retrieval
- Hybrid retrieval (RRF and Weighted)

It measures:
- Latency (average, p50, p95, p99)
- Recall @k
- Precision @k
- MRR (Mean Reciprocal Rank)
- NDCG @k
"""

import argparse
import json
import os
import statistics
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Test data - Chinese lecture notes about machine learning
TEST_DOCUMENTS = [
    {
        "id": "doc1",
        "text": "机器学习（Machine Learning）是人工智能的核心领域，它研究如何使计算机系统能够从数据中学习并改进性能。机器学习算法通过分析训练数据来构建模型，然后使用这些模型进行预测或决策。",
    },
    {
        "id": "doc2",
        "text": "监督学习（Supervised Learning）是机器学习的一种主要类型。在监督学习中，我们使用带有标签的训练数据来训练模型。常见的监督学习任务包括分类（如垃圾邮件检测）和回归（如房价预测）。",
    },
    {
        "id": "doc3",
        "text": "无监督学习（Unsupervised Learning）处理没有标签的数据。算法需要自己发现数据中的模式和结构。聚类分析是无监督学习的典型应用，例如客户分群或异常检测。",
    },
    {
        "id": "doc4",
        "text": "深度学习（Deep Learning）是机器学习的一个子领域，它使用多层神经网络来学习数据的层次化表示。深度学习在图像识别、语音识别和自然语言处理等领域取得了突破性进展。",
    },
    {
        "id": "doc5",
        "text": "卷积神经网络（CNN）是一种专门用于处理网格状数据（如图像）的深度学习模型。CNN 通过卷积层、池化层和全连接层的组合来自动学习图像的层次化特征。",
    },
    {
        "id": "doc6",
        "text": "循环神经网络（RNN）是另一种深度学习模型，特别适合处理序列数据。RNN 通过记忆单元来捕捉序列中的时间依赖关系，广泛应用于机器翻译、语音识别等任务。",
    },
    {
        "id": "doc7",
        "text": "强化学习（Reinforcement Learning）是一种通过试错来学习的学习范式。智能体（Agent）通过与环境交互，根据奖励信号来优化其行为策略，以最大化累积奖励。",
    },
    {
        "id": "doc8",
        "text": "自然语言处理（NLP）是人工智能和语言学交叉的领域，研究如何让计算机理解、解释和生成人类语言。NLP 应用包括机器翻译、情感分析、问答系统等。",
    },
    {
        "id": "doc9",
        "text": "计算机视觉（Computer Vision）研究如何让计算机从图像或视频中提取信息和理解内容。应用包括人脸识别、自动驾驶、医学影像分析等。",
    },
    {
        "id": "doc10",
        "text": "迁移学习（Transfer Learning）是一种将在一个任务上学到的知识应用到相关任务上的技术。迁移学习可以显著减少新任务所需的训练数据和计算资源。",
    },
    {
        "id": "doc11",
        "text": "注意力机制（Attention Mechanism）是一种让模型学习关注输入中重要部分的技术。Transformer 模型基于自注意力机制，在 NLP 领域取得了巨大成功。",
    },
    {
        "id": "doc12",
        "text": "生成对抗网络（GAN）由生成器和判别器两个网络组成，通过对抗训练来学习数据的分布。GAN 可以生成逼真的图像、音频和文本内容。",
    },
]

TEST_QUERIES = [
    {
        "id": "q1",
        "query": "什么是机器学习",
        "relevant_docs": ["doc1"],
    },
    {
        "id": "q2",
        "query": "监督学习和无监督学习的区别",
        "relevant_docs": ["doc2", "doc3"],
    },
    {
        "id": "q3",
        "query": "深度学习神经网络",
        "relevant_docs": ["doc4", "doc5", "doc6"],
    },
    {
        "id": "q4",
        "query": "自然语言处理应用",
        "relevant_docs": ["doc8"],
    },
    {
        "id": "q5",
        "query": "强化学习智能体",
        "relevant_docs": ["doc7"],
    },
    {
        "id": "q6",
        "query": "卷积神经网络图像处理",
        "relevant_docs": ["doc5"],
    },
    {
        "id": "q7",
        "query": "注意力机制 Transformer",
        "relevant_docs": ["doc11"],
    },
    {
        "id": "q8",
        "query": "生成对抗网络 GAN",
        "relevant_docs": ["doc12"],
    },
]


@dataclass
class BenchmarkResult:
    """Stores benchmark results for a retriever."""

    retriever_name: str
    num_documents: int
    num_queries: int

    # Latency metrics (in milliseconds)
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float

    # Retrieval metrics
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    precision_at_1: float
    precision_at_3: float
    precision_at_5: float
    precision_at_10: float
    mrr: float
    ndcg_at_5: float
    ndcg_at_10: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


def compute_ndcg(relevances: List[int], k: int) -> float:
    """Compute NDCG @k."""
    import math

    if not relevances or k <= 0:
        return 0.0

    k_relevances = relevances[:k]

    # Compute DCG
    dcg = sum((2**rel - 1) / math.log2(i + 2) for i, rel in enumerate(k_relevances))

    # Compute IDCG
    ideal_rels = sorted(relevances, reverse=True)[:k]
    idcg = sum((2**rel - 1) / math.log2(i + 2) for i, rel in enumerate(ideal_rels))

    return dcg / idcg if idcg > 0 else 0.0


def evaluate_retrieval(
    retriever: Any,
    queries: List[Dict[str, Any]],
    top_k: int = 10,
) -> Tuple[Dict[str, float], List[float]]:
    """
    Evaluate a retriever on a set of queries.

    Returns:
        (metrics_dict, latencies_list)
    """
    latencies: List[float] = []

    # Accumulators for metrics
    recall_sums = {1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0}
    precision_sums = {1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0}
    rr_sum = 0.0
    ndcg_5_sum = 0.0
    ndcg_10_sum = 0.0

    num_queries = 0

    for query_data in queries:
        query_id = query_data["id"]
        query_text = query_data["query"]
        relevant_docs = set(query_data["relevant_docs"])

        if not relevant_docs:
            continue

        # Perform retrieval with timing
        start_time = time.perf_counter()
        results = retriever.retrieve(query_text, top_k=top_k)
        end_time = time.perf_counter()

        latency_ms = (end_time - start_time) * 1000
        latencies.append(latency_ms)

        retrieved_ids = [doc.get("id") for doc in results if doc.get("id")]

        # Compute relevances
        relevances = [1 if doc_id in relevant_docs else 0 for doc_id in retrieved_ids]
        total_relevant = len(relevant_docs)

        # Recall @k and Precision @k
        for k in [1, 3, 5, 10]:
            k_relevances = relevances[:k]
            k_relevant_count = sum(k_relevances)

            recall = k_relevant_count / total_relevant
            precision = k_relevant_count / k if k > 0 else 0

            recall_sums[k] += recall
            precision_sums[k] += precision

        # Reciprocal Rank
        first_relevant_rank = None
        for rank, rel in enumerate(relevances, start=1):
            if rel == 1:
                first_relevant_rank = rank
                break

        rr = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
        rr_sum += rr

        # NDCG
        ndcg_5_sum += compute_ndcg(relevances, 5)
        ndcg_10_sum += compute_ndcg(relevances, 10)

        num_queries += 1

    # Average metrics
    metrics = {
        "recall_at_1": recall_sums[1] / num_queries if num_queries > 0 else 0,
        "recall_at_3": recall_sums[3] / num_queries if num_queries > 0 else 0,
        "recall_at_5": recall_sums[5] / num_queries if num_queries > 0 else 0,
        "recall_at_10": recall_sums[10] / num_queries if num_queries > 0 else 0,
        "precision_at_1": precision_sums[1] / num_queries if num_queries > 0 else 0,
        "precision_at_3": precision_sums[3] / num_queries if num_queries > 0 else 0,
        "precision_at_5": precision_sums[5] / num_queries if num_queries > 0 else 0,
        "precision_at_10": precision_sums[10] / num_queries if num_queries > 0 else 0,
        "mrr": rr_sum / num_queries if num_queries > 0 else 0,
        "ndcg_at_5": ndcg_5_sum / num_queries if num_queries > 0 else 0,
        "ndcg_at_10": ndcg_10_sum / num_queries if num_queries > 0 else 0,
    }

    return metrics, latencies


def compute_latency_stats(latencies: List[float]) -> Dict[str, float]:
    """Compute latency statistics."""
    if not latencies:
        return {
            "avg": 0,
            "p50": 0,
            "p95": 0,
            "p99": 0,
            "min": 0,
            "max": 0,
        }

    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)

    return {
        "avg": statistics.mean(latencies),
        "p50": sorted_latencies[int(n * 0.50)],
        "p95": sorted_latencies[int(n * 0.95)],
        "p99": sorted_latencies[int(n * 0.99)],
        "min": min(latencies),
        "max": max(latencies),
    }


def run_benchmark() -> Dict[str, BenchmarkResult]:
    """
    Run comprehensive benchmark on all retrievers.

    Returns:
        Dict mapping retriever name to benchmark result
    """
    print("=" * 60)
    print("RETRIEVAL SYSTEM BENCHMARK")
    print("=" * 60)
    print(f"\nDocuments: {len(TEST_DOCUMENTS)}")
    print(f"Queries: {len(TEST_QUERIES)}")
    print()

    results: Dict[str, BenchmarkResult] = {}

    # 1. Benchmark BM25
    print("Benchmarking BM25...")
    from retrieval.bm25_index import BM25Index

    bm25_retriever = BM25Index(TEST_DOCUMENTS)

    # Warm-up
    bm25_retriever.search("测试", top_k=5)

    metrics, latencies = evaluate_retrieval(bm25_retriever, TEST_QUERIES)
    latency_stats = compute_latency_stats(latencies)

    results["BM25"] = BenchmarkResult(
        retriever_name="BM25",
        num_documents=len(TEST_DOCUMENTS),
        num_queries=len(TEST_QUERIES),
        avg_latency_ms=latency_stats["avg"],
        p50_latency_ms=latency_stats["p50"],
        p95_latency_ms=latency_stats["p95"],
        p99_latency_ms=latency_stats["p99"],
        min_latency_ms=latency_stats["min"],
        max_latency_ms=latency_stats["max"],
        recall_at_1=metrics["recall_at_1"],
        recall_at_3=metrics["recall_at_3"],
        recall_at_5=metrics["recall_at_5"],
        recall_at_10=metrics["recall_at_10"],
        precision_at_1=metrics["precision_at_1"],
        precision_at_3=metrics["precision_at_3"],
        precision_at_5=metrics["precision_at_5"],
        precision_at_10=metrics["precision_at_10"],
        mrr=metrics["mrr"],
        ndcg_at_5=metrics["ndcg_at_5"],
        ndcg_at_10=metrics["ndcg_at_10"],
    )
    print(f"  Avg Latency: {latency_stats['avg']:.2f}ms")
    print(f"  Recall@5: {metrics['recall_at_5']:.4f}")
    print()

    # 2. Benchmark Dense Retriever
    print("Benchmarking Dense Retriever...")
    from retrieval.dense_retriever import DenseRetriever

    dense_retriever = DenseRetriever(TEST_DOCUMENTS)

    # Warm-up
    dense_retriever.search("测试", top_k=5)

    metrics, latencies = evaluate_retrieval(dense_retriever, TEST_QUERIES)
    latency_stats = compute_latency_stats(latencies)

    results["Dense"] = BenchmarkResult(
        retriever_name="Dense",
        num_documents=len(TEST_DOCUMENTS),
        num_queries=len(TEST_QUERIES),
        avg_latency_ms=latency_stats["avg"],
        p50_latency_ms=latency_stats["p50"],
        p95_latency_ms=latency_stats["p95"],
        p99_latency_ms=latency_stats["p99"],
        min_latency_ms=latency_stats["min"],
        max_latency_ms=latency_stats["max"],
        recall_at_1=metrics["recall_at_1"],
        recall_at_3=metrics["recall_at_3"],
        recall_at_5=metrics["recall_at_5"],
        recall_at_10=metrics["recall_at_10"],
        precision_at_1=metrics["precision_at_1"],
        precision_at_3=metrics["precision_at_3"],
        precision_at_5=metrics["precision_at_5"],
        precision_at_10=metrics["precision_at_10"],
        mrr=metrics["mrr"],
        ndcg_at_5=metrics["ndcg_at_5"],
        ndcg_at_10=metrics["ndcg_at_10"],
    )
    print(f"  Avg Latency: {latency_stats['avg']:.2f}ms")
    print(f"  Recall@5: {metrics['recall_at_5']:.4f}")
    print()

    # 3. Benchmark Hybrid (RRF)
    print("Benchmarking Hybrid (RRF)...")
    from retrieval.hybrid_retriever import FusionMethod, HybridRetriever

    hybrid_rrf_retriever = HybridRetriever(
        TEST_DOCUMENTS, fusion_method=FusionMethod.RRF
    )

    # Warm-up
    hybrid_rrf_retriever.retrieve("测试", top_k=5)

    metrics, latencies = evaluate_retrieval(hybrid_rrf_retriever, TEST_QUERIES)
    latency_stats = compute_latency_stats(latencies)

    results["Hybrid_RRF"] = BenchmarkResult(
        retriever_name="Hybrid_RRF",
        num_documents=len(TEST_DOCUMENTS),
        num_queries=len(TEST_QUERIES),
        avg_latency_ms=latency_stats["avg"],
        p50_latency_ms=latency_stats["p50"],
        p95_latency_ms=latency_stats["p95"],
        p99_latency_ms=latency_stats["p99"],
        min_latency_ms=latency_stats["min"],
        max_latency_ms=latency_stats["max"],
        recall_at_1=metrics["recall_at_1"],
        recall_at_3=metrics["recall_at_3"],
        recall_at_5=metrics["recall_at_5"],
        recall_at_10=metrics["recall_at_10"],
        precision_at_1=metrics["precision_at_1"],
        precision_at_3=metrics["precision_at_3"],
        precision_at_5=metrics["precision_at_5"],
        precision_at_10=metrics["precision_at_10"],
        mrr=metrics["mrr"],
        ndcg_at_5=metrics["ndcg_at_5"],
        ndcg_at_10=metrics["ndcg_at_10"],
    )
    print(f"  Avg Latency: {latency_stats['avg']:.2f}ms")
    print(f"  Recall@5: {metrics['recall_at_5']:.4f}")
    print()

    # 4. Benchmark Hybrid (Weighted)
    print("Benchmarking Hybrid (Weighted)...")
    hybrid_weighted_retriever = HybridRetriever(
        TEST_DOCUMENTS, fusion_method=FusionMethod.WEIGHTED
    )

    # Warm-up
    hybrid_weighted_retriever.retrieve("测试", top_k=5)

    metrics, latencies = evaluate_retrieval(hybrid_weighted_retriever, TEST_QUERIES)
    latency_stats = compute_latency_stats(latencies)

    results["Hybrid_Weighted"] = BenchmarkResult(
        retriever_name="Hybrid_Weighted",
        num_documents=len(TEST_DOCUMENTS),
        num_queries=len(TEST_QUERIES),
        avg_latency_ms=latency_stats["avg"],
        p50_latency_ms=latency_stats["p50"],
        p95_latency_ms=latency_stats["p95"],
        p99_latency_ms=latency_stats["p99"],
        min_latency_ms=latency_stats["min"],
        max_latency_ms=latency_stats["max"],
        recall_at_1=metrics["recall_at_1"],
        recall_at_3=metrics["recall_at_3"],
        recall_at_5=metrics["recall_at_5"],
        recall_at_10=metrics["recall_at_10"],
        precision_at_1=metrics["precision_at_1"],
        precision_at_3=metrics["precision_at_3"],
        precision_at_5=metrics["precision_at_5"],
        precision_at_10=metrics["precision_at_10"],
        mrr=metrics["mrr"],
        ndcg_at_5=metrics["ndcg_at_5"],
        ndcg_at_10=metrics["ndcg_at_10"],
    )
    print(f"  Avg Latency: {latency_stats['avg']:.2f}ms")
    print(f"  Recall@5: {metrics['recall_at_5']:.4f}")
    print()

    return results


def print_comparison_table(results: Dict[str, BenchmarkResult]) -> None:
    """Print a comparison table of all retrievers."""
    print("\n" + "=" * 100)
    print("BENCHMARK COMPARISON TABLE")
    print("=" * 100)

    # Header
    header = f"{'Retriever':<18} {'Latency(ms)':<14} {'Recall@1':<10} {'Recall@3':<10} {'Recall@5':<10} {'Recall@10':<11} {'MRR':<8} {'NDCG@5':<8}"
    print(header)
    print("-" * 100)

    # Rows
    for name, result in results.items():
        row = (
            f"{name:<18} "
            f"{result.avg_latency_ms:<14.2f} "
            f"{result.recall_at_1:<10.4f} "
            f"{result.recall_at_3:<10.4f} "
            f"{result.recall_at_5:<10.4f} "
            f"{result.recall_at_10:<11.4f} "
            f"{result.mrr:<8.4f} "
            f"{result.ndcg_at_5:<8.4f}"
        )
        print(row)

    print("-" * 100)


def save_results(results: Dict[str, BenchmarkResult], output_path: str) -> None:
    """Save benchmark results to JSON file."""
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    data = {
        "timestamp": datetime.now().isoformat(),
        "results": {name: result.to_dict() for name, result in results.items()},
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_path}")


def generate_report(results: Dict[str, BenchmarkResult]) -> str:
    """Generate a text report from benchmark results."""
    lines = [
        "=" * 60,
        "RETRIEVAL SYSTEM BENCHMARK REPORT",
        "=" * 60,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "SUMMARY",
        "-" * 40,
    ]

    # Find best performers
    best_recall_5 = max(results.items(), key=lambda x: x[1].recall_at_5)
    fastest = min(results.items(), key=lambda x: x[1].avg_latency_ms)
    best_mrr = max(results.items(), key=lambda x: x[1].mrr)

    lines.append(f"Best Recall@5: {best_recall_5[0]} ({best_recall_5[1].recall_at_5:.4f})")
    lines.append(f"Fastest: {fastest[0]} ({fastest[1].avg_latency_ms:.2f}ms)")
    lines.append(f"Best MRR: {best_mrr[0]} ({best_mrr[1].mrr:.4f})")
    lines.append("")

    # Detailed results
    lines.append("DETAILED RESULTS")
    lines.append("-" * 40)

    for name, result in results.items():
        lines.append(f"\n{name}:")
        lines.append(f"  Latency:")
        lines.append(f"    Average: {result.avg_latency_ms:.2f}ms")
        lines.append(f"    P95: {result.p95_latency_ms:.2f}ms")
        lines.append(f"    P99: {result.p99_latency_ms:.2f}ms")
        lines.append(f"  Retrieval Metrics:")
        lines.append(f"    Recall@1: {result.recall_at_1:.4f}")
        lines.append(f"    Recall@5: {result.recall_at_5:.4f}")
        lines.append(f"    Recall@10: {result.recall_at_10:.4f}")
        lines.append(f"    Precision@5: {result.precision_at_5:.4f}")
        lines.append(f"    MRR: {result.mrr:.4f}")
        lines.append(f"    NDCG@5: {result.ndcg_at_5:.4f}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run retrieval system benchmark")
    parser.add_argument(
        "--output",
        type=str,
        default="data/benchmark_results.json",
        help="Output path for results JSON",
    )
    parser.add_argument(
        "--report",
        type=str,
        default="data/benchmark_report.txt",
        help="Output path for text report",
    )

    args = parser.parse_args()

    # Run benchmark
    results = run_benchmark()

    # Print comparison table
    print_comparison_table(results)

    # Save results
    save_results(results, args.output)

    # Generate and save report
    report = generate_report(results)
    print(report)

    with open(args.report, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport saved to: {args.report}")


if __name__ == "__main__":
    main()
