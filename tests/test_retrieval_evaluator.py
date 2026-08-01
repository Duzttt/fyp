"""Tests for the retrieval evaluator and benchmark dataset format."""

import json
import time as time_module

import pytest

from evaluation.retrieval_evaluator import (
    RetrievalEvaluator,
    RetrievalEvaluatorError,
)


class _FakeRetriever:
    def __init__(self, results_by_query):
        self.results_by_query = results_by_query

    def retrieve(self, query, top_k=10):
        return [
            {"id": doc_id} for doc_id in self.results_by_query.get(query, [])[:top_k]
        ]


class TestBenchmarkLoading:
    def test_load_benchmark_jsonl(self, tmp_path):
        path = tmp_path / "benchmark.jsonl"
        path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "id": "q001",
                            "query": "What is the contract net protocol?",
                            "relevant_chunk_ids": ["chunk_60", "chunk_61"],
                            "ground_truth": "gt1",
                        }
                    ),
                    json.dumps(
                        {
                            "id": "q002",
                            "query": "What is a blackboard system?",
                            "relevant_chunk_ids": ["chunk_72"],
                            "ground_truth": "gt2",
                        }
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )

        queries = RetrievalEvaluator.load_benchmark(str(path))
        assert len(queries) == 2
        assert queries[0]["id"] == "q001"
        assert queries[0]["relevant_chunk_ids"] == ["chunk_60", "chunk_61"]
        assert queries[1]["ground_truth"] == "gt2"

    def test_load_benchmark_empty_file(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        assert RetrievalEvaluator.load_benchmark(str(path)) == []


class TestRelevantChunkIds:
    def test_uses_relevant_chunk_ids_field(self):
        queries = [
            {
                "id": "q1",
                "query": "What is the contract net protocol?",
                "relevant_chunk_ids": ["chunk_60", "chunk_61"],
            }
        ]
        evaluator = RetrievalEvaluator(queries)
        retriever = _FakeRetriever(
            {"What is the contract net protocol?": ["chunk_60", "chunk_61", "chunk_1"]}
        )

        aggregate, results = evaluator.evaluate(retriever, top_k=5)
        assert aggregate.num_queries == 1
        assert aggregate.avg_recall_at_5 == 1.0
        assert results[0].reciprocal_rank == 1.0

    def test_expected_doc_ids_still_supported(self):
        queries = [{"id": "q1", "query": "q", "expected_doc_ids": ["doc1"]}]
        evaluator = RetrievalEvaluator(queries)
        retriever = _FakeRetriever({"q": ["doc1"]})

        aggregate, _ = evaluator.evaluate(retriever, top_k=5)
        assert aggregate.mrr == 1.0


class TestMetrics:
    def test_recall_mrr_ndcg_at_rank(self):
        queries = [{"id": "q1", "query": "q", "relevant_chunk_ids": ["chunk_2"]}]
        evaluator = RetrievalEvaluator(queries)
        # The relevant chunk sits at position 3.
        retriever = _FakeRetriever({"q": ["chunk_0", "chunk_1", "chunk_2"]})

        aggregate, results = evaluator.evaluate(retriever, top_k=10)
        assert results[0].reciprocal_rank == pytest.approx(1 / 3)
        assert results[0].recall_at_1 == 0.0
        assert results[0].recall_at_5 == 1.0
        assert results[0].recall_at_10 == 1.0
        assert 0 < results[0].ndcg_at_5 <= 1
        assert 0 < aggregate.mrr <= 1

    def test_skips_queries_without_relevant_docs(self):
        queries = [
            {"id": "q1", "query": "a", "relevant_chunk_ids": ["chunk_0"]},
            {"id": "q2", "query": "b", "relevant_chunk_ids": []},
        ]
        evaluator = RetrievalEvaluator(queries)
        retriever = _FakeRetriever({"a": ["chunk_0"], "b": ["chunk_5"]})

        aggregate, results = evaluator.evaluate(retriever, top_k=5)
        assert aggregate.num_queries == 1
        assert len(results) == 1

    def test_no_queries_raises(self):
        evaluator = RetrievalEvaluator([])
        with pytest.raises(RetrievalEvaluatorError):
            evaluator.evaluate(_FakeRetriever({}), top_k=5)


class TestLatency:
    def test_p95_latency_computed(self):
        queries = [
            {"id": f"q{i}", "query": f"q{i}", "relevant_chunk_ids": [f"chunk_{i}"]}
            for i in range(10)
        ]
        evaluator = RetrievalEvaluator(queries)

        class SlowRetriever:
            def retrieve(self, query, top_k=10):
                time_module.sleep(0.005)
                return [{"id": query}]

        aggregate, results = evaluator.evaluate(SlowRetriever(), top_k=5)
        assert aggregate.num_queries == 10
        assert aggregate.p95_latency_ms > 0
        assert all(r.latency_ms > 0 for r in results)
        # p95 (the largest of 10 samples) must be >= the median sample.
        latencies = sorted(r.latency_ms for r in results)
        assert aggregate.p95_latency_ms >= latencies[4]
        assert "p95_latency_ms" in aggregate.to_dict()

    def test_per_query_latency_in_dict(self):
        queries = [{"id": "q1", "query": "q", "relevant_chunk_ids": ["chunk_0"]}]
        evaluator = RetrievalEvaluator(queries)
        retriever = _FakeRetriever({"q": ["chunk_0"]})

        _, results = evaluator.evaluate(retriever, top_k=5)
        assert "latency_ms" in results[0].to_dict()
