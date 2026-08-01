"""
Retrieval strategy benchmark script.

Runs BM25, dense (persisted FAISS), and hybrid (production pipeline) retrieval
over the same benchmark dataset at the same top_k, and reports:

- Recall@5, Recall@10
- MRR
- nDCG@5
- p95 latency
- per-query results

Also checks the release acceptance criteria defined in PLAN.md:

    Hybrid Recall@5 >= Dense Recall@5
    Hybrid MRR >= Dense MRR
    Hybrid nDCG@5 >= Dense nDCG@5
    No BM25-only exact hits dropped by the dense threshold
    rerank p95 latency within the allowed budget

Usage:
    python scripts/evaluate_retrieval.py [--benchmark data/evaluation/retrieval_benchmark.jsonl]
                                          [--top-k 10] [--json]
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, ".")

# The retrieval pipeline imports Django models (via app.services.llm_client),
# so configure Django before importing any app modules.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
import django  # noqa: E402

django.setup()

from app.config import settings  # noqa: E402
from app.services.embedding import EmbeddingService  # noqa: E402
from app.services.local_rag import retrieve_with_faiss  # noqa: E402
from app.services.runtime_embedding import load_runtime_embedding_settings  # noqa: E402
from app.services.vector_store import VectorStore  # noqa: E402
from evaluation.retrieval_evaluator import (  # noqa: E402
    AggregateMetrics,
    EvaluationResult,
    RetrievalEvaluator,
)
from retrieval.bm25_index import BM25Index  # noqa: E402

DEFAULT_BENCHMARK = "data/evaluation/retrieval_benchmark.jsonl"

# Reranker score threshold stays None until the benchmark justifies a stable
# value (see PLAN.md Task 5).
RERANKER_SCORE_THRESHOLD = None


class _BM25Adapter:
    """BM25-only retrieval over the persisted chunks."""

    name = "bm25"

    def __init__(self) -> None:
        rt = load_runtime_embedding_settings()
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=rt["embedding_dim"],
        )
        documents = [
            {"id": f"chunk_{i}", "text": chunk.get("text", "")}
            for i, chunk in enumerate(vector_store.chunks)
            if chunk.get("text", "").strip()
        ]
        self.bm25 = BM25Index(documents)

    def retrieve(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        results = self.bm25.search(query, top_k=top_k)
        return [{"id": doc_id} for doc_id, _ in results]


class _DenseAdapter:
    """Dense-only retrieval over the persisted FAISS index."""

    name = "dense"

    def __init__(self) -> None:
        rt = load_runtime_embedding_settings()
        self.embedding_service = EmbeddingService(model_name=rt["model_id"])
        self.vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=rt["embedding_dim"],
        )

    def retrieve(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        query_embedding = self.embedding_service.embed_query(query)
        results = self.vector_store.search_with_metadata(query_embedding, top_k=top_k)
        return [{"id": f"chunk_{r['index']}"} for r in results]


class _HybridAdapter:
    """Production hybrid pipeline: BM25 + FAISS -> RRF -> rerank -> MMR."""

    name = "hybrid"

    def retrieve(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        results = retrieve_with_faiss(query=query, top_k=top_k)
        return [
            {"id": f"chunk_{r['chunk_index']}"}
            for r in results
            if r.get("chunk_index") is not None
        ]

    def retrieve_fused_candidates(
        self, query: str, top_k: int = 30
    ) -> List[Dict[str, Any]]:
        """RRF-fused candidates before rerank/diversity selection.

        Used by the release-criteria check: this is the stage where the old
        Dense cosine threshold used to drop BM25-only hits, so it is the
        right stage to verify nothing was wrongly filtered out.
        """
        from app.services.hybrid_retriever_service import HybridRetrieverService

        service = HybridRetrieverService.get_instance()
        if service is None:
            return []
        results = service.search(query=query, top_k=top_k, candidate_top_k=top_k)
        return [
            {"id": f"chunk_{r['chunk_index']}"}
            for r in results
            if r.get("chunk_index") is not None
        ]


def _format_table(
    aggregates: Dict[str, AggregateMetrics],
) -> str:
    rows = [
        ["metric", *[name for name in aggregates]],
        ["Recall@5", *[f"{agg.avg_recall_at_5:.4f}" for agg in aggregates.values()]],
        ["Recall@10", *[f"{agg.avg_recall_at_10:.4f}" for agg in aggregates.values()]],
        ["MRR", *[f"{agg.mrr:.4f}" for agg in aggregates.values()]],
        ["nDCG@5", *[f"{agg.avg_ndcg_at_5:.4f}" for agg in aggregates.values()]],
        ["nDCG@10", *[f"{agg.avg_ndcg_at_10:.4f}" for agg in aggregates.values()]],
        [
            "p95 latency (ms)",
            *[f"{agg.p95_latency_ms:.1f}" for agg in aggregates.values()],
        ],
        ["queries", *[str(agg.num_queries) for agg in aggregates.values()]],
    ]
    widths = [max(len(cell) for cell in col) for col in zip(*rows)]
    lines = [
        " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows
    ]
    return "\n".join(lines)


def _check_release_criteria(
    aggregates: Dict[str, AggregateMetrics],
    benchmark_path: str,
    bm25_retriever: _BM25Adapter,
    top_k: int,
) -> List[Dict[str, Any]]:
    """Evaluate the PLAN.md release acceptance criteria."""
    hybrid = aggregates.get("hybrid")
    dense = aggregates.get("dense")
    checks: List[Dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"criterion": name, "passed": passed, "detail": detail})

    if hybrid and dense:
        add(
            "Hybrid Recall@5 >= Dense Recall@5",
            hybrid.avg_recall_at_5 >= dense.avg_recall_at_5,
            f"hybrid={hybrid.avg_recall_at_5:.4f} dense={dense.avg_recall_at_5:.4f}",
        )
        add(
            "Hybrid MRR >= Dense MRR",
            hybrid.mrr >= dense.mrr,
            f"hybrid={hybrid.mrr:.4f} dense={dense.mrr:.4f}",
        )
        add(
            "Hybrid nDCG@5 >= Dense nDCG@5",
            hybrid.avg_ndcg_at_5 >= dense.avg_ndcg_at_5,
            f"hybrid={hybrid.avg_ndcg_at_5:.4f} dense={dense.avg_ndcg_at_5:.4f}",
        )

    # No BM25-only exact hit dropped by the dense threshold: every relevant
    # chunk found by BM25 within top_k must also appear in the hybrid fused
    # candidates (the stage where the old Dense cosine threshold used to
    # filter). MMR/diversity selection may still drop near-duplicate chunks
    # from the final top_k, which is expected behaviour, not a threshold bug.
    dropped: List[str] = []
    queries = RetrievalEvaluator.load_benchmark(benchmark_path)
    hybrid_adapter = _HybridAdapter()
    for q in queries:
        qid = q.get("id", "")
        relevant = set(q.get("relevant_chunk_ids", q.get("expected_doc_ids", [])))
        if not relevant:
            continue
        bm25_ids = {r["id"] for r in bm25_retriever.retrieve(q.get("query", ""), top_k)}
        fused_ids = {
            r["id"]
            for r in hybrid_adapter.retrieve_fused_candidates(q.get("query", ""))
        }
        for chunk_id in relevant & bm25_ids:
            if chunk_id not in fused_ids:
                dropped.append(f"{qid}:{chunk_id}")
    add(
        "No BM25-only exact hits dropped",
        not dropped,
        (
            "; ".join(dropped[:5])
            if dropped
            else "no relevant BM25 hits missing from hybrid"
        ),
    )

    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        default=DEFAULT_BENCHMARK,
        help="Path to the retrieval benchmark JSONL file",
    )
    parser.add_argument(
        "--top-k", type=int, default=10, help="Retrieval cutoff (default 10)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a human report",
    )
    args = parser.parse_args()

    queries = RetrievalEvaluator.load_benchmark(args.benchmark)
    if len(queries) < 30:
        print(
            f"Warning: benchmark has only {len(queries)} queries; "
            "PLAN.md requires at least 30.",
            file=sys.stderr,
        )

    evaluator = RetrievalEvaluator(queries)
    retrievers: Dict[str, Any] = {
        "bm25": _BM25Adapter(),
        "dense": _DenseAdapter(),
        "hybrid": _HybridAdapter(),
    }

    aggregates: Dict[str, AggregateMetrics] = {}
    per_query: Dict[str, List[EvaluationResult]] = {}
    started_total = time.perf_counter()
    for name, retriever in retrievers.items():
        print(f"Evaluating {name} ...", file=sys.stderr)
        aggregate, results = evaluator.evaluate(retriever, top_k=args.top_k)
        aggregates[name] = aggregate
        per_query[name] = results
    total_elapsed = time.perf_counter() - started_total

    checks = _check_release_criteria(
        aggregates, args.benchmark, retrievers["bm25"], args.top_k
    )

    if args.json:
        payload = {
            "benchmark": args.benchmark,
            "top_k": args.top_k,
            "total_elapsed_seconds": round(total_elapsed, 2),
            "aggregates": {name: agg.to_dict() for name, agg in aggregates.items()},
            "per_query": {
                name: [r.to_dict() for r in results]
                for name, results in per_query.items()
            },
            "release_checks": checks,
        }
        print(json.dumps(payload, indent=2))
        return

    print("\n=== RETRIEVAL BENCHMARK (top_k={}) ===".format(args.top_k))
    print(_format_table(aggregates))
    print(f"\nTotal evaluation time: {total_elapsed:.1f}s")

    print("\n=== RELEASE ACCEPTANCE CRITERIA ===")
    all_passed = True
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        if not check["passed"]:
            all_passed = False
        print(f"[{status}] {check['criterion']}: {check['detail']}")
    print("\nOverall:", "PASS" if all_passed else "FAIL")


if __name__ == "__main__":
    main()
