from typing import Any, Dict, List

import numpy as np

from app.services.rag_pipeline import RAGPipeline
from app.services.vector_store import VectorStore


class _FakeEmbeddingService:
    def __init__(self):
        self.model_name = "fake"

    def embed_query(self, query: str) -> np.ndarray:
        return np.array([1.0, 0.0], dtype="float32")


class _FakeVectorStore:
    def search_with_metadata(self, query_embedding: np.ndarray, top_k: int = 3):
        return [
            {
                "index": 0,
                "rank": 1,
                "text": "Agents are autonomous systems.",
                "source": "lecture1.pdf",
                "page": 7,
                "distance": 0.1234,
            }
        ]


def test_vector_store_returns_grounded_metadata(tmp_path):
    store = VectorStore(index_path=str(tmp_path), embedding_dim=2)
    embeddings = np.array(
        [
            [1.0, 0.0],
            [0.0, 1.0],
        ],
        dtype="float32",
    )
    chunks: List[Dict[str, Any]] = [
        {"text": "chunk a", "source": "a.pdf", "page": 1},
        {"text": "chunk b", "source": "b.pdf", "page": 2},
    ]
    store.add_embeddings(embeddings, chunks)
    store.save()

    results = store.search_with_metadata(np.array([1.0, 0.0], dtype="float32"), top_k=2)

    assert len(results) == 2
    assert results[0]["source"] == "a.pdf"
    assert results[0]["page"] == 1
    assert "text" in results[0]
    assert "distance" in results[0]


def test_rag_pipeline_query_returns_structured_sources(monkeypatch):
    rag = RAGPipeline(
        embedding_service=_FakeEmbeddingService(),
        vector_store=_FakeVectorStore(),
        api_key="dummy-key",
        provider="gemini",
    )
    monkeypatch.setattr(rag, "_generate_gemini", lambda prompt: "Grounded answer [S1]")

    result = rag.query("What is an agent?", top_k=3)

    assert result["answer"] == "Grounded answer [S1]"
    assert isinstance(result["sources"], list)
    assert result["sources"][0]["source"] == "lecture1.pdf"
    assert result["sources"][0]["page"] == 7
