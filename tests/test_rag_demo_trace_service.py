import requests

import pytest


def _install_happy_path_mocks(monkeypatch: pytest.MonkeyPatch, trace_service):
    captured = {"source_filter": None, "generate_called": False}

    class FakeEmbeddingService:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def embed_query(self, query: str):
            return [0.1, 0.2, 0.3]

    class FakeVectorStore:
        chunks = [
            {
                "text": "Retrieval augmented generation uses retrieved context.",
                "source": "lecture-a.pdf",
                "page": 1,
            },
            {
                "text": "Dense retrieval compares vector embeddings.",
                "source": "lecture-b.pdf",
                "page": 2,
            },
        ]

        def search_with_metadata(self, query_embedding, top_k: int):
            return [
                {
                    "text": "Retrieval augmented generation uses retrieved context.",
                    "source": "lecture-a.pdf",
                    "page": 1,
                    "distance": 0.2,
                },
                {
                    "text": "Dense retrieval compares vector embeddings.",
                    "source": "lecture-b.pdf",
                    "page": 2,
                    "distance": 0.8,
                },
            ][:top_k]

    monkeypatch.setattr(
        trace_service,
        "load_runtime_embedding_settings",
        lambda: {"model_id": "test-embedding", "embedding_dim": 3},
    )
    monkeypatch.setattr(
        trace_service,
        "load_runtime_llm_settings",
        lambda: {
            "provider": "local_llm",
            "model": "test-llm",
            "api_key": None,
            "base_url": "http://localhost:8080",
        },
    )
    monkeypatch.setattr(
        trace_service.EmbeddingService,
        "__init__",
        lambda self, model_name: setattr(self, "model_name", model_name),
    )
    monkeypatch.setattr(
        trace_service.EmbeddingService,
        "embed_query",
        lambda self, query: [0.1, 0.2, 0.3],
    )
    monkeypatch.setattr(
        trace_service.VectorStore,
        "get_cached",
        lambda index_path, embedding_dim: FakeVectorStore(),
    )

    def fake_retrieve_with_faiss(
        query, top_k=5, source_filter=None, stage_timings=None, rerank_details=None
    ):
        captured["source_filter"] = source_filter
        if stage_timings is not None:
            stage_timings.append({"stage": "bm25_dense_fusion", "duration_ms": 1})
            stage_timings.append({"stage": "rerank", "duration_ms": 3})
        if rerank_details is not None:
            rerank_details["enabled"] = True
            rerank_details["model"] = "cross-encoder/test"
            rerank_details["device"] = "cpu"
            rerank_details["candidates_before"] = [
                {
                    "chunk_index": 0,
                    "source": "lecture-a.pdf",
                    "page": 1,
                    "text": "Retrieval augmented generation uses retrieved context.",
                    "fusion_score": 0.9,
                }
            ]
            rerank_details["candidates_after"] = [
                {
                    "chunk_index": 0,
                    "source": "lecture-a.pdf",
                    "page": 1,
                    "text": "Retrieval augmented generation uses retrieved context.",
                    "rerank_score": 0.95,
                    "fusion_score": 0.9,
                }
            ]
        return [
            {
                "text": "Retrieval augmented generation uses retrieved context.",
                "source": "lecture-a.pdf",
                "page": 1,
                "distance": 0.2,
                "score": 0.9,
            }
        ]

    def fake_generate(
        query,
        context,
        model=None,
        temperature=0.7,
        timeout_seconds=60,
        return_log=False,
        return_thinking=False,
    ):
        captured["generate_called"] = True
        return "RAG answers by grounding generation in retrieved context."

    monkeypatch.setattr(trace_service, "retrieve_with_faiss", fake_retrieve_with_faiss)
    monkeypatch.setattr(
        trace_service,
        "build_context_from_sources",
        lambda sources: "[S1] lecture-a.pdf\nRetrieval augmented generation uses retrieved context.",
    )
    monkeypatch.setattr(trace_service, "generate", fake_generate)

    return captured


def test_build_rag_demo_trace_returns_ordered_english_stages(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    _install_happy_path_mocks(monkeypatch, trace_service)

    trace = trace_service.build_rag_demo_trace(
        query="What is RAG?",
        source_filter=None,
        top_k=3,
        include_answer=True,
    )

    stage_ids = [stage["id"] for stage in trace["stages"]]
    assert stage_ids == [
        "user_question",
        "query_processing",
        "embedding_generation",
        "bm25_retrieval",
        "dense_retrieval",
        "hybrid_ranking",
        "cross_encoder_rerank",
        "context_building",
        "llm_generation",
        "final_answer",
    ]
    assert trace["query"] == "What is RAG?"
    assert trace["retrieved_chunks"][0]["source"] == "lecture-a.pdf"
    assert trace["context_preview"].startswith("[S1]")
    assert trace["answer"].startswith("RAG answers")
    assert all(stage["title"] for stage in trace["stages"])
    assert all(stage["summary"] for stage in trace["stages"])


def test_build_rag_demo_trace_skips_generation_when_include_answer_false(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    captured = _install_happy_path_mocks(monkeypatch, trace_service)

    trace = trace_service.build_rag_demo_trace(
        query="Explain dense retrieval",
        source_filter=None,
        top_k=2,
        include_answer=False,
    )

    llm_stage = next(
        stage for stage in trace["stages"] if stage["id"] == "llm_generation"
    )
    final_stage = next(
        stage for stage in trace["stages"] if stage["id"] == "final_answer"
    )
    assert llm_stage["status"] == "skipped"
    assert final_stage["status"] == "skipped"
    assert trace["answer"] == ""
    assert captured["generate_called"] is False


def test_build_rag_demo_trace_passes_source_filter_to_hybrid_retrieval(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    captured = _install_happy_path_mocks(monkeypatch, trace_service)

    trace_service.build_rag_demo_trace(
        query="Explain RAG",
        source_filter=["lecture-a.pdf"],
        top_k=4,
        include_answer=False,
    )

    assert captured["source_filter"] == ["lecture-a.pdf"]


def test_build_rag_demo_trace_preserves_retrieval_when_llm_times_out(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    _install_happy_path_mocks(monkeypatch, trace_service)

    def timeout_generate(*args, **kwargs):
        raise requests.exceptions.Timeout("model timed out")

    monkeypatch.setattr(trace_service, "generate", timeout_generate)

    trace = trace_service.build_rag_demo_trace(
        query="Explain RAG",
        source_filter=None,
        top_k=3,
        include_answer=True,
    )

    llm_stage = next(
        stage for stage in trace["stages"] if stage["id"] == "llm_generation"
    )
    final_stage = next(
        stage for stage in trace["stages"] if stage["id"] == "final_answer"
    )
    assert llm_stage["status"] == "failed"
    assert "timed out" in llm_stage["summary"].lower()
    assert final_stage["status"] == "skipped"
    assert trace["retrieved_chunks"]
    assert trace["answer"] == ""


def test_build_rag_demo_trace_includes_rerank_stage(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    _install_happy_path_mocks(monkeypatch, trace_service)

    trace = trace_service.build_rag_demo_trace(
        query="Explain RAG",
        source_filter=None,
        top_k=3,
        include_answer=False,
    )

    stage_ids = [stage["id"] for stage in trace["stages"]]
    assert "cross_encoder_rerank" in stage_ids

    rerank_stage = next(
        stage for stage in trace["stages"] if stage["id"] == "cross_encoder_rerank"
    )
    assert rerank_stage["status"] == "completed"
    assert rerank_stage["duration_ms"] == 3
    assert rerank_stage["technical"]["model"] == "cross-encoder/test"
    assert rerank_stage["technical"]["device"] == "cpu"
    assert rerank_stage["technical"]["candidates_considered"] == 1
    assert len(rerank_stage["results"]) == 1
    assert rerank_stage["results"][0]["score"] == 0.95
    assert rerank_stage["results"][0]["source"] == "lecture-a.pdf"


def test_build_rag_demo_trace_rerank_skipped_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    _install_happy_path_mocks(monkeypatch, trace_service)

    def fake_retrieve_without_rerank(
        query, top_k=5, source_filter=None, stage_timings=None, rerank_details=None
    ):
        return [
            {
                "text": "Retrieval augmented generation uses retrieved context.",
                "source": "lecture-a.pdf",
                "page": 1,
                "distance": 0.2,
                "score": 0.9,
            }
        ]

    monkeypatch.setattr(
        trace_service, "retrieve_with_faiss", fake_retrieve_without_rerank
    )

    trace = trace_service.build_rag_demo_trace(
        query="Explain RAG",
        source_filter=None,
        top_k=3,
        include_answer=False,
    )

    rerank_stage = next(
        stage for stage in trace["stages"] if stage["id"] == "cross_encoder_rerank"
    )
    assert rerank_stage["status"] == "skipped"
    assert rerank_stage["technical"]["enabled"] is False
    assert rerank_stage["results"] == []


class TestScoreFromDistance:
    """FAISS IndexFlatIP 'distance' is cosine similarity: higher = more relevant."""

    def test_score_increases_with_similarity(self):
        from app.services.rag_demo_trace import _score_from_distance

        assert _score_from_distance(0.9, 0.9) == 1.0  # most relevant
        assert _score_from_distance(0.45, 0.9) == 0.5
        assert _score_from_distance(0.0, 0.9) == 0.0

    def test_scores_are_monotonic_in_similarity(self):
        from app.services.rag_demo_trace import _score_from_distance

        distances = [0.6639, 0.7301, 0.9181]  # real FAISS cosine similarities
        max_distance = max(distances)
        scores = [_score_from_distance(d, max_distance) for d in distances]
        assert scores == sorted(scores)  # higher similarity -> higher score

    def test_negative_similarity_clamped_to_zero(self):
        from app.services.rag_demo_trace import _score_from_distance

        assert _score_from_distance(-0.5, 0.9) == 0.0

    def test_invalid_distance_falls_back_to_max(self):
        from app.services.rag_demo_trace import _score_from_distance

        assert _score_from_distance("n/a", 0.9) == 1.0


def test_dense_stage_scores_follow_similarity(monkeypatch: pytest.MonkeyPatch):
    """Dense stage rank #1 must no longer show score 0 for the top hit."""
    from app.services import rag_demo_trace as trace_service

    _install_happy_path_mocks(monkeypatch, trace_service)

    trace = trace_service.build_rag_demo_trace(
        query="What is RAG?", include_answer=False
    )

    dense_stage = next(
        stage for stage in trace["stages"] if stage["id"] == "dense_retrieval"
    )
    scores = [result["score"] for result in dense_stage["results"]]
    # FakeVectorStore distances: rank1=0.2 (lower similarity), rank2=0.8 (higher).
    assert scores[0] == 0.25
    assert scores[1] == 1.0
    assert scores[0] < scores[1]
