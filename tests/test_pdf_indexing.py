import numpy as np
import pytest

from app.services.pdf_indexing import PDFIndexingError, index_pdf_file


class _DummyEmbeddingService:
    def __init__(self, model_name="dummy-model"):
        self.model_name = model_name

    def embed_texts(self, texts):
        return np.array(
            [
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
            ]
        )


class _DummyIndex:
    def __init__(self, d, ntotal=0):
        self.d = d
        self.ntotal = ntotal


class _DummyVectorStore:
    def __init__(self, index_path, embedding_dim=384):
        self.index_path = index_path
        self.embedding_dim = embedding_dim
        self.index = _DummyIndex(d=embedding_dim, ntotal=0)
        self.chunks = []

    def clear(self):
        self.index.ntotal = 0
        self.chunks = []

    def add_embeddings(self, embeddings, chunks):
        self.index.ntotal += len(chunks)
        self.chunks.extend(chunks)

    def save(self):
        return None

    def get_total_chunks(self):
        return len(self.chunks)


def test_index_pdf_file_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.pdf_indexing.read_pdf_text", lambda _: "mock text")
    monkeypatch.setattr(
        "app.services.pdf_indexing.split_text_into_chunks",
        lambda text, chunk_size=500: ["chunk-1", "chunk-2"],
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.EmbeddingService",
        _DummyEmbeddingService,
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.VectorStore",
        _DummyVectorStore,
    )

    result = index_pdf_file("dummy.pdf", chunk_size=500)

    assert result["chunks_created"] == 2
    assert result["total_chunks_in_index"] == 2
    assert result["total_chars"] == len("mock text")


def test_index_pdf_file_strips_pdf_path(monkeypatch: pytest.MonkeyPatch):
    received = {"path": None}

    def _fake_read_pdf_text(path: str) -> str:
        received["path"] = path
        return "mock text"

    monkeypatch.setattr("app.services.pdf_indexing.read_pdf_text", _fake_read_pdf_text)
    monkeypatch.setattr(
        "app.services.pdf_indexing.split_text_into_chunks",
        lambda text, chunk_size=500: ["chunk-1", "chunk-2"],
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.EmbeddingService",
        _DummyEmbeddingService,
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.VectorStore",
        _DummyVectorStore,
    )

    index_pdf_file("  dummy.pdf  ", chunk_size=500)

    assert received["path"] == "dummy.pdf"


def test_index_pdf_file_raises_on_empty_chunks(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.pdf_indexing.read_pdf_text", lambda _: "mock text")
    monkeypatch.setattr(
        "app.services.pdf_indexing.split_text_into_chunks",
        lambda text, chunk_size=500: [],
    )

    with pytest.raises(PDFIndexingError, match="No chunks created from text"):
        index_pdf_file("dummy.pdf", chunk_size=500)


def test_index_pdf_file_raises_on_dimension_mismatch(
    monkeypatch: pytest.MonkeyPatch,
):
    class _MismatchVectorStore(_DummyVectorStore):
        def __init__(self, index_path, embedding_dim=384):
            super().__init__(index_path=index_path, embedding_dim=embedding_dim)
            self.index = _DummyIndex(d=999, ntotal=1)

    monkeypatch.setattr("app.services.pdf_indexing.read_pdf_text", lambda _: "mock text")
    monkeypatch.setattr(
        "app.services.pdf_indexing.split_text_into_chunks",
        lambda text, chunk_size=500: ["chunk-1", "chunk-2"],
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.EmbeddingService",
        _DummyEmbeddingService,
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.VectorStore",
        _MismatchVectorStore,
    )

    with pytest.raises(PDFIndexingError, match="Embedding dimension mismatch"):
        index_pdf_file("dummy.pdf", chunk_size=500)
