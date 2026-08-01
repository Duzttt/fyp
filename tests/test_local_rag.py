import os

import django
from unittest.mock import Mock

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

from app.services.local_rag import retrieve_with_faiss  # noqa: E402


class TestLocalRagHybrid:
    def test_retrieve_with_faiss_uses_hybrid_service_when_available(self, monkeypatch):
        fake_results = [
            {
                "text": "result 1",
                "source": "a.pdf",
                "page": 1,
                "score": 0.95,
                "cosine_similarity": 0.85,
            },
            {
                "text": "result 2",
                "source": "a.pdf",
                "page": 2,
                "score": 0.80,
                "cosine_similarity": 0.70,
            },
        ]

        class FakeHybridService:
            @staticmethod
            def get_instance():
                return FakeHybridService()

            def search(self, query, top_k=5, candidate_top_k=None):
                return fake_results

        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService",
            FakeHybridService,
        )

        results = retrieve_with_faiss("test query", top_k=5, reranker_enabled=False)
        assert len(results) == 2
        assert results[0]["text"] == "result 1"
        assert results[0]["score"] == 0.95

    def test_retrieve_with_faiss_falls_back_to_dense_when_hybrid_unavailable(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService",
            type("HS", (), {"get_instance": staticmethod(lambda: None)}),
        )

        monkeypatch.setattr(
            "app.services.local_rag.load_runtime_embedding_settings",
            lambda: {"model_id": "test", "embedding_dim": 384},
        )

        class FakeVectorStore:
            chunks = [{"text": "dense result", "source": "b.pdf", "page": 1}]
            search_with_metadata = classmethod(
                lambda cls, *a, **kw: [
                    {
                        "text": "dense result",
                        "source": "b.pdf",
                        "page": 1,
                        "distance": 0.85,
                    }
                ]
            )

            @classmethod
            def get_cached(cls, **kw):
                return FakeVectorStore()

        monkeypatch.setattr(
            "app.services.local_rag.VectorStore",
            FakeVectorStore,
        )

        mock_embed = Mock()
        mock_embed.embed_query.return_value = [0.1] * 384
        monkeypatch.setattr(
            "app.services.local_rag.EmbeddingService",
            lambda **kw: mock_embed,
        )

        results = retrieve_with_faiss(
            "test query", top_k=5, similarity_threshold=0.0, reranker_enabled=False
        )
        assert len(results) == 1
        assert results[0]["text"] == "dense result"


class TestRelevanceFiltering:
    """Hybrid results must not be filtered by the Dense cosine threshold by
    default; filtering only happens when an explicit final-score threshold
    (`minimum_relevance_score`) is provided."""

    def test_hybrid_results_not_filtered_by_dense_threshold(self, monkeypatch):
        fake_results = [
            {
                "text": "low cosine",
                "source": "a.pdf",
                "page": 1,
                "score": 0.9,
                "cosine_similarity": 0.30,
            },
        ]

        class FakeHybridService:
            @staticmethod
            def get_instance():
                return FakeHybridService()

            def search(self, query, top_k=5, candidate_top_k=None):
                return fake_results

        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService", FakeHybridService
        )

        # No threshold argument: a BM25-only hit with cosine 0.30 must survive.
        results = retrieve_with_faiss("test query", top_k=5, reranker_enabled=False)
        assert len(results) == 1
        assert results[0]["text"] == "low cosine"

    def test_explicit_cosine_threshold_ignored_for_hybrid(self, monkeypatch):
        fake_results = [
            {
                "text": "low cosine",
                "source": "a.pdf",
                "page": 1,
                "score": 0.9,
                "cosine_similarity": 0.30,
            },
        ]

        class FakeHybridService:
            @staticmethod
            def get_instance():
                return FakeHybridService()

            def search(self, query, top_k=5, candidate_top_k=None):
                return fake_results

        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService", FakeHybridService
        )

        # Even an explicit cosine threshold must not drop hybrid candidates.
        results = retrieve_with_faiss(
            "test query", top_k=5, similarity_threshold=0.6, reranker_enabled=False
        )
        assert len(results) == 1

    def test_minimum_relevance_score_filters_reranked_results(self, monkeypatch):
        fake_results = [
            {
                "text": "high",
                "source": "a.pdf",
                "page": 1,
                "score": 0.9,
                "rerank_score": 0.85,
            },
            {
                "text": "low",
                "source": "a.pdf",
                "page": 2,
                "score": 0.7,
                "rerank_score": 0.40,
            },
        ]

        class FakeHybridService:
            @staticmethod
            def get_instance():
                return FakeHybridService()

            def search(self, query, top_k=5, candidate_top_k=None):
                return fake_results

        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService", FakeHybridService
        )

        results = retrieve_with_faiss(
            "test query",
            top_k=5,
            minimum_relevance_score=0.5,
            reranker_enabled=False,
        )
        assert len(results) == 1
        assert results[0]["text"] == "high"

    def test_minimum_relevance_score_falls_back_to_fusion_score(self, monkeypatch):
        """Without rerank_score, the fusion score is used for the final cutoff."""
        fake_results = [
            {"text": "high", "source": "a.pdf", "page": 1, "score": 0.8},
            {"text": "low", "source": "a.pdf", "page": 2, "score": 0.2},
        ]

        class FakeHybridService:
            @staticmethod
            def get_instance():
                return FakeHybridService()

            def search(self, query, top_k=5, candidate_top_k=None):
                return fake_results

        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService", FakeHybridService
        )

        results = retrieve_with_faiss(
            "test query",
            top_k=5,
            minimum_relevance_score=0.5,
            reranker_enabled=False,
        )
        assert len(results) == 1
        assert results[0]["text"] == "high"

    def test_keeps_all_results_without_threshold(self, monkeypatch):
        fake_results = [
            {
                "text": "a",
                "source": "x.pdf",
                "page": 1,
                "score": 0.9,
                "cosine_similarity": 0.9,
            },
            {
                "text": "b",
                "source": "x.pdf",
                "page": 2,
                "score": 0.8,
                "cosine_similarity": 0.8,
            },
        ]

        class FakeHybridService:
            @staticmethod
            def get_instance():
                return FakeHybridService()

            def search(self, query, top_k=5, candidate_top_k=None):
                return fake_results

        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService", FakeHybridService
        )

        results = retrieve_with_faiss("test query", top_k=5, reranker_enabled=False)
        assert len(results) == 2

    def test_returns_empty_when_all_below_minimum_relevance(self, monkeypatch):
        fake_results = [
            {
                "text": "low",
                "source": "a.pdf",
                "page": 1,
                "score": 0.5,
                "rerank_score": 0.2,
            },
        ]

        class FakeHybridService:
            @staticmethod
            def get_instance():
                return FakeHybridService()

            def search(self, query, top_k=5, candidate_top_k=None):
                return fake_results

        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService", FakeHybridService
        )

        results = retrieve_with_faiss(
            "test query",
            top_k=5,
            minimum_relevance_score=0.6,
            reranker_enabled=False,
        )
        assert len(results) == 0

    def test_source_filter_still_applies(self, monkeypatch):
        fake_results = [
            {
                "text": "match",
                "source": "a.pdf",
                "page": 1,
                "score": 0.9,
                "cosine_similarity": 0.85,
            },
            {
                "text": "no match",
                "source": "b.pdf",
                "page": 1,
                "score": 0.9,
                "cosine_similarity": 0.85,
            },
            {
                "text": "low",
                "source": "a.pdf",
                "page": 2,
                "score": 0.5,
                "cosine_similarity": 0.3,
            },
        ]

        class FakeHybridService:
            @staticmethod
            def get_instance():
                return FakeHybridService()

            def search(self, query, top_k=5, candidate_top_k=None):
                return fake_results

        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService", FakeHybridService
        )

        results = retrieve_with_faiss(
            "test query",
            top_k=5,
            source_filter=["a.pdf"],
            reranker_enabled=False,
        )
        assert len(results) == 2
        assert {r["text"] for r in results} == {"match", "low"}

    def test_dense_fallback_honors_explicit_threshold(self, monkeypatch):
        """The cosine threshold still applies on the pure-dense fallback path."""
        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService",
            type("HS", (), {"get_instance": staticmethod(lambda: None)}),
        )

        monkeypatch.setattr(
            "app.services.local_rag.load_runtime_embedding_settings",
            lambda: {"model_id": "test", "embedding_dim": 384},
        )

        class FakeVectorStore:
            chunks = [{"text": "dense result", "source": "b.pdf", "page": 1}]

            @classmethod
            def get_cached(cls, **kw):
                return FakeVectorStore()

            @classmethod
            def search_with_metadata(cls, *a, **kw):
                return [
                    {
                        "text": "dense result",
                        "source": "b.pdf",
                        "page": 1,
                        "distance": 0.30,
                    }
                ]

        monkeypatch.setattr(
            "app.services.local_rag.VectorStore",
            FakeVectorStore,
        )

        mock_embed = Mock()
        mock_embed.embed_query.return_value = [0.1] * 384
        monkeypatch.setattr(
            "app.services.local_rag.EmbeddingService",
            lambda **kw: mock_embed,
        )

        results = retrieve_with_faiss(
            "test query", top_k=5, similarity_threshold=0.6, reranker_enabled=False
        )
        assert len(results) == 0

    def test_dense_fallback_threshold_zero_disables_filtering(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService",
            type("HS", (), {"get_instance": staticmethod(lambda: None)}),
        )

        monkeypatch.setattr(
            "app.services.local_rag.load_runtime_embedding_settings",
            lambda: {"model_id": "test", "embedding_dim": 384},
        )

        class FakeVectorStore:
            chunks = [{"text": "dense result", "source": "b.pdf", "page": 1}]

            @classmethod
            def get_cached(cls, **kw):
                return FakeVectorStore()

            @classmethod
            def search_with_metadata(cls, *a, **kw):
                return [
                    {
                        "text": "dense result",
                        "source": "b.pdf",
                        "page": 1,
                        "distance": 0.30,
                    }
                ]

        monkeypatch.setattr(
            "app.services.local_rag.VectorStore",
            FakeVectorStore,
        )

        mock_embed = Mock()
        mock_embed.embed_query.return_value = [0.1] * 384
        monkeypatch.setattr(
            "app.services.local_rag.EmbeddingService",
            lambda **kw: mock_embed,
        )

        results = retrieve_with_faiss(
            "test query", top_k=5, similarity_threshold=0.0, reranker_enabled=False
        )
        assert len(results) == 1


class TestRerankAndDiversity:
    """Task 4: rerank precedence, per-source caps, graceful degradation,
    score-field preservation and stage observability."""

    def _patch_hybrid(self, monkeypatch, fake_results):
        class FakeHybridService:
            @staticmethod
            def get_instance():
                return FakeHybridService()

            def search(self, query, top_k=5, candidate_top_k=None):
                return list(fake_results)

        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService", FakeHybridService
        )

    def test_reranker_ranking_precedes_rrf_ranking(self, monkeypatch):
        """After reranking, order must follow rerank_score, not the RRF score."""
        fake_results = [
            {
                "text": "a",
                "source": "x.pdf",
                "page": 1,
                "score": 0.9,
                "fusion_score": 0.9,
                "bm25_score": 5.0,
                "dense_score": 0.9,
                "chunk_index": 0,
            },
            {
                "text": "b",
                "source": "y.pdf",
                "page": 1,
                "score": 0.7,
                "fusion_score": 0.7,
                "bm25_score": 4.0,
                "dense_score": 0.7,
                "chunk_index": 1,
            },
        ]
        self._patch_hybrid(monkeypatch, fake_results)

        class FakeReranker:
            @staticmethod
            def get_instance(model_name):
                return FakeReranker()

            def rerank(self, query, candidates):
                candidates[0]["rerank_score"] = 0.3  # "a" low
                candidates[1]["rerank_score"] = 0.9  # "b" high
                candidates.sort(key=lambda c: c["rerank_score"], reverse=True)
                return candidates

        monkeypatch.setattr(
            "app.services.cross_encoder_reranker.CrossEncoderReranker", FakeReranker
        )

        results = retrieve_with_faiss("test query", top_k=5)
        assert results[0]["text"] == "b"
        assert results[0]["rerank_score"] == 0.9
        # All score fields must be preserved through reranking.
        assert results[0]["fusion_score"] == 0.7
        assert results[0]["bm25_score"] == 4.0
        assert results[0]["dense_score"] == 0.7
        assert results[1]["text"] == "a"

    def test_max_chunks_per_source_enforced_with_relaxation(self, monkeypatch):
        """At most 2 chunks per source; the cap is relaxed only when no other
        source has candidates left."""
        fake_results = [
            {
                "text": f"c{i}",
                "source": "a.pdf",
                "page": 1,
                "score": 0.9 - i * 0.4,
                "fusion_score": 0.9 - i * 0.4,
                "chunk_index": i,
            }
            for i in range(3)
        ] + [
            {
                "text": f"d{i}",
                "source": "b.pdf",
                "page": 1,
                "score": 0.7 - i * 0.01,
                "fusion_score": 0.7 - i * 0.01,
                "chunk_index": 10 + i,
            }
            for i in range(2)
        ]
        self._patch_hybrid(monkeypatch, fake_results)

        results = retrieve_with_faiss("test query", top_k=5, reranker_enabled=False)
        assert len(results) == 5
        from collections import Counter

        counts = Counter(r["source"] for r in results)
        assert counts["b.pdf"] == 2  # cap honoured for the secondary source
        assert counts["a.pdf"] == 3  # relaxed once b.pdf was exhausted

    def test_returns_fewer_results_when_candidates_insufficient(self, monkeypatch):
        """With too few candidates the system must return fewer results, not fail."""
        fake_results = [
            {
                "text": "only one",
                "source": "x.pdf",
                "page": 1,
                "score": 0.9,
                "fusion_score": 0.9,
                "chunk_index": 0,
            }
        ]
        self._patch_hybrid(monkeypatch, fake_results)

        results = retrieve_with_faiss("test query", top_k=5, reranker_enabled=False)
        assert len(results) == 1
        assert results[0]["text"] == "only one"

    def test_stage_timings_recorded(self, monkeypatch):
        fake_results = [
            {
                "text": "doc",
                "source": "x.pdf",
                "page": 1,
                "score": 0.9,
                "fusion_score": 0.9,
                "chunk_index": 0,
            }
        ]
        self._patch_hybrid(monkeypatch, fake_results)

        timings: list = []
        retrieve_with_faiss(
            "test query", top_k=5, reranker_enabled=False, stage_timings=timings
        )

        stages = {t["stage"] for t in timings}
        assert "bm25_dense_fusion" in stages
        assert "mmr_diversity" in stages
        assert all(isinstance(t["duration_ms"], int) for t in timings)
