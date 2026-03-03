from typing import Dict, List, Optional

import numpy as np

from app.config import settings
from app.services.embedding import EmbeddingError, EmbeddingService
from app.services.pdf_chunking import read_pdf_text, split_text_into_chunks
from app.services.vector_store import VectorStore, VectorStoreError


class PDFIndexingError(Exception):
    pass


def _normalize_path_arg(path: str) -> str:
    cleaned = str(path).strip()
    if (
        len(cleaned) >= 2
        and cleaned[0] == cleaned[-1]
        and cleaned[0] in {"'", '"'}
    ):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _validate_embeddings(embeddings: np.ndarray, chunks: List[str]) -> int:
    if embeddings.size == 0:
        raise PDFIndexingError("Embedding result is empty")

    if embeddings.ndim != 2:
        raise PDFIndexingError("Embedding result should be a 2D matrix")

    if embeddings.shape[0] != len(chunks):
        raise PDFIndexingError("Embedding rows must match number of chunks")

    return int(embeddings.shape[1])


def index_pdf_file(
    pdf_path: str,
    chunk_size: int = 500,
    index_path: Optional[str] = None,
    model_name: Optional[str] = None,
    clear_existing: bool = False,
) -> Dict[str, int]:
    """
    Read PDF -> split into chunks -> embed -> store vectors in FAISS.

    Returns stats useful for API response / logging.
    """
    cleaned_pdf_path = _normalize_path_arg(pdf_path)
    try:
        text = read_pdf_text(cleaned_pdf_path)
    except FileNotFoundError as exc:
        raise PDFIndexingError(str(exc)) from exc
    except OSError as exc:
        raise PDFIndexingError(
            f"Failed to read PDF '{cleaned_pdf_path}': {str(exc)}"
        ) from exc
    if not text.strip():
        raise PDFIndexingError("No text extracted from PDF")

    chunks = split_text_into_chunks(text, chunk_size=chunk_size)
    if not chunks:
        raise PDFIndexingError("No chunks created from text")

    embedding_service = EmbeddingService(
        model_name=model_name or settings.EMBEDDING_MODEL
    )

    try:
        embeddings = embedding_service.embed_texts(chunks)
        embedding_dim = _validate_embeddings(embeddings, chunks)
    except EmbeddingError as exc:
        raise PDFIndexingError(str(exc)) from exc

    vector_store = VectorStore(
        index_path=index_path or settings.FAISS_INDEX_PATH,
        embedding_dim=embedding_dim,
    )

    if clear_existing:
        vector_store.clear()

    if (
        vector_store.index is not None
        and vector_store.index.ntotal > 0
        and vector_store.index.d != embedding_dim
    ):
        raise PDFIndexingError(
            "Embedding dimension mismatch with existing FAISS index. "
            "Use clear_existing=True or use the same embedding model."
        )

    try:
        vector_store.add_embeddings(embeddings, chunks)
        vector_store.save()
    except VectorStoreError as exc:
        raise PDFIndexingError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise PDFIndexingError(f"Failed to store embeddings: {str(exc)}") from exc

    return {
        "total_chars": len(text),
        "chunks_created": len(chunks),
        "total_chunks_in_index": vector_store.get_total_chunks(),
    }
