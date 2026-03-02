import pytest


class TestPDFLoader:
    def test_pdf_loader_can_be_instantiated(self):
        from app.services.pdf_loader import PDFLoader

        loader = PDFLoader(documents_path="data/documents")
        assert loader is not None
        assert loader.documents_path == "data/documents"


class TestTextChunker:
    def test_chunker_can_be_instantiated(self):
        from app.services.chunker import TextChunker

        chunker = TextChunker(chunk_size=400, chunk_overlap=50)
        assert chunker is not None
        assert chunker.chunk_size == 400
        assert chunker.chunk_overlap == 50

    def test_chunk_text_returns_list(self):
        from app.services.chunker import TextChunker

        chunker = TextChunker(chunk_size=400, chunk_overlap=50)
        text = "This is a test text. It has multiple sentences. Let's see if chunking works properly."
        chunks = chunker.chunk_text(text)
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_chunk_text_empty_returns_empty_list(self):
        from app.services.chunker import TextChunker

        chunker = TextChunker(chunk_size=400, chunk_overlap=50)
        chunks = chunker.chunk_text("")
        assert chunks == []


class TestEmbeddingService:
    def test_embedding_service_can_be_instantiated(self):
        from app.services.embedding import EmbeddingService

        service = EmbeddingService(model_name="sentence-transformers/all-MiniLM-L6-v2")
        assert service is not None
        assert service.model_name == "sentence-transformers/all-MiniLM-L6-v2"


class TestVectorStore:
    def test_vector_store_can_be_instantiated(self):
        from app.services.vector_store import VectorStore

        store = VectorStore(index_path="data/faiss_index", embedding_dim=384)
        assert store is not None
        assert store.embedding_dim == 384


class TestRAGPipeline:
    def test_rag_pipeline_can_be_instantiated(self):
        from app.services.embedding import EmbeddingService
        from app.services.rag_pipeline import RAGPipeline
        from app.services.vector_store import VectorStore

        embedding_service = EmbeddingService()
        vector_store = VectorStore(index_path="data/faiss_index", embedding_dim=384)
        rag = RAGPipeline(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )
        assert rag is not None
