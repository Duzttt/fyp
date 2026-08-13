"""
Retrieval-based topic summarization pipeline.

Pure logic: no Django ORM usage. Retrieval and LLM calls are injected as
callables so the pipeline is fully unit-testable.
"""

from typing import Any, Dict, List, Optional  # noqa: F401

from app.config import settings
from app.services.runtime_embedding import load_runtime_embedding_settings
from app.services.vector_store import VectorStore

CJK_LANGUAGE_THRESHOLD = 0.2

LENGTH_TOPIC_COUNTS = {"short": 4, "medium": 8, "detailed": 12}
LENGTH_TOP_K = {"short": 4, "medium": 6, "detailed": 8}
MAX_TOPICS = 12


class TopicSummarizerError(Exception):
    """Raised for pipeline failures. ``code`` maps to job error_code."""

    def __init__(self, message: str, code: str = "pipeline_error"):
        super().__init__(message)
        self.code = code


def detect_language(texts: List[str]) -> str:
    """Return 'zh' when the CJK character ratio is at or above the threshold."""
    cjk_chars = 0
    total_chars = 0
    for text in texts:
        for ch in text:
            total_chars += 1
            if "\u4e00" <= ch <= "\u9fff":
                cjk_chars += 1
    if total_chars == 0:
        return "en"
    return "zh" if (cjk_chars / total_chars) >= CJK_LANGUAGE_THRESHOLD else "en"


def load_document_chunks(document_id: str) -> List[Dict[str, Any]]:
    """Load all indexed chunks of one document, ordered by page (stable)."""
    rt = load_runtime_embedding_settings()
    vector_store = VectorStore.get_cached(
        index_path=settings.FAISS_INDEX_PATH,
        embedding_dim=rt["embedding_dim"],
    )
    chunks = [
        chunk
        for chunk in vector_store.chunks
        if str(chunk.get("source", "")) == str(document_id)
    ]
    if not chunks:
        raise TopicSummarizerError(
            f"Document not indexed: {document_id}", code="document_not_indexed"
        )
    chunks.sort(key=lambda c: int(c.get("page") or 0))
    return chunks
