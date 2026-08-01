import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.config import settings
from app.services.embedding import EmbeddingService
from app.services.runtime_embedding import load_runtime_embedding_settings
from app.services.vector_store import VectorStore


def _get_hybrid_retriever_class():
    from retrieval.hybrid_retriever import FusionMethod, HybridRetriever

    return FusionMethod, HybridRetriever


logger = logging.getLogger("hybrid_retriever_service")


class HybridRetrieverServiceError(Exception):
    pass


class HybridRetrieverService:
    _instance: Optional["HybridRetrieverService"] = None
    _initialized: bool = False
    _lock: threading.Lock = threading.Lock()

    def __init__(self, retriever: Any, model_name: str) -> None:
        self._retriever = retriever
        self._model_name = model_name

    @classmethod
    def get_instance(cls) -> Optional["HybridRetrieverService"]:
        if cls._instance is not None:
            return cls._instance

        try:
            FusionMethod, HybridRetriever = _get_hybrid_retriever_class()
        except Exception:
            return None

        with cls._lock:
            if cls._instance is not None:
                return cls._instance
            if cls._initialized:
                return cls._instance

            try:
                rt = load_runtime_embedding_settings()
                vector_store = VectorStore.get_cached(
                    index_path=settings.FAISS_INDEX_PATH,
                    embedding_dim=rt["embedding_dim"],
                )

                documents = _build_document_list(vector_store.chunks)
                if not documents:
                    logger.warning("No documents available for hybrid retrieval")
                    cls._initialized = True
                    return None

                # The dense side of the hybrid retriever is backed by the
                # persisted FAISS index via a search provider: no second
                # embedding pass over all chunks and no duplicate FAISS index.
                embedding_service = EmbeddingService(model_name=rt["model_id"])
                dense_provider = _make_dense_search_provider(
                    embedding_service, vector_store
                )

                retriever = HybridRetriever(
                    documents=documents,
                    model_name=rt["model_id"],
                    fusion_method=FusionMethod.RRF,
                    dense_search_provider=dense_provider,
                )

                cls._instance = cls(retriever, rt["model_id"])
                cls._initialized = True
                logger.info(
                    "HybridRetrieverService initialized with %d documents",
                    len(documents),
                )
                return cls._instance

            except Exception as exc:
                logger.error("Failed to initialize hybrid retriever: %s", exc)
                cls._initialized = True
                return None

    @classmethod
    def refresh(cls) -> None:
        with cls._lock:
            cls._instance = None
            cls._initialized = False
        logger.info("HybridRetrieverService cache cleared, will rebuild on next query")

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._instance = None
            cls._initialized = False

    def search(
        self,
        query: str,
        top_k: int = 5,
        candidate_top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        hybrid_results = self._retriever.retrieve(
            query=query, top_k=top_k, candidate_top_k=candidate_top_k
        )
        return [
            {
                "text": r.get("text", ""),
                "source": r.get("source", "unknown"),
                "page": r.get("metadata", {}).get("page"),
                "score": r.get("score", 0.0),
                "cosine_similarity": r.get("cosine_similarity", 0.0),
            }
            for r in hybrid_results
        ]

    def get_document_count(self) -> int:
        return self._retriever.get_document_count()


def _make_dense_search_provider(
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
) -> Callable[[str, int], List[Tuple[str, float]]]:
    """
    Build a dense-search provider backed by the persisted FAISS index.

    The provider encodes the query with the shared EmbeddingService, searches
    the persisted VectorStore, and maps FAISS chunk indices to `chunk_<index>`
    IDs so they can be fused with BM25 candidates by document ID.
    """

    def provider(query: str, top_k: int) -> List[Tuple[str, float]]:
        query_embedding = embedding_service.embed_query(query)
        results = vector_store.search_with_metadata(query_embedding, top_k=top_k)
        return [
            (f"chunk_{result['index']}", float(result["distance"]))
            for result in results
        ]

    return provider


def _build_document_list(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    documents = []
    for i, chunk in enumerate(chunks):
        text = chunk.get("text", "")
        if not text.strip():
            continue
        documents.append(
            {
                "id": f"chunk_{i}",
                "text": text,
                "source": chunk.get("source", "unknown"),
                "metadata": {
                    "page": chunk.get("page"),
                    "source": chunk.get("source", "unknown"),
                },
            }
        )
    return documents
