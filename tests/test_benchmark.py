"""Tests for the retrieval benchmark scripts' evaluation logic."""

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[1]

BENCHMARK_PATHS = [
    (ROOT / "scripts" / "benchmark.py", "scripts"),
    (ROOT / "tests" / "benchmark.py", "tests"),
]


@pytest.fixture(scope="module", params=BENCHMARK_PATHS, ids=["scripts", "tests"])
def benchmark_module(request: pytest.FixtureRequest) -> Any:
    """Load the benchmark script as a module so its functions can be tested."""
    path, name = request.param
    spec = importlib.util.spec_from_file_location(f"benchmark_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SearchOnlyRetriever:
    """Retriever exposing only the BM25/dense `search()` API."""

    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: str, top_k: int = 10) -> List[Any]:
        self.calls += 1
        return [("doc1", 0.9), ("doc2", 0.5)]


class RetrieveOnlyRetriever:
    """Retriever exposing only the hybrid `retrieve()` API."""

    def retrieve(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        return [{"id": "doc1", "text": "a"}, {"id": "doc2", "text": "b"}]


QUERY = {"id": "q1", "query": "machine learning", "relevant_docs": ["doc1"]}


def test_evaluate_retrieval_supports_search_only_retrievers(
    benchmark_module: Any,
) -> None:
    retriever = SearchOnlyRetriever()

    metrics, latencies = benchmark_module.evaluate_retrieval(
        retriever, [QUERY], top_k=10
    )

    assert retriever.calls == 1
    assert metrics["recall_at_1"] == 1.0
    assert metrics["recall_at_5"] == 1.0
    assert metrics["mrr"] == 1.0
    assert len(latencies) == 1


def test_evaluate_retrieval_supports_retrieve_only_retrievers(
    benchmark_module: Any,
) -> None:
    metrics, latencies = benchmark_module.evaluate_retrieval(
        RetrieveOnlyRetriever(), [QUERY], top_k=10
    )

    assert metrics["recall_at_1"] == 1.0
    assert metrics["recall_at_5"] == 1.0
    assert metrics["mrr"] == 1.0
    assert len(latencies) == 1
