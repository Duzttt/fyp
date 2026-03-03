from typing import Any, Dict, List, Optional

import requests

from app.config import settings
from app.services.embedding import EmbeddingError, EmbeddingService
from app.services.vector_store import VectorStore, VectorStoreError

SYSTEM_PROMPT = (
    "You are a rigorous academic teaching assistant. Answer strictly based on "
    "the provided reference materials. If evidence is insufficient, say so clearly. "
    "Respond in English by default unless the user explicitly requests another language."
)


class LocalRAGError(Exception):
    pass


def retrieve_with_faiss(
    query: str, top_k: int = 3, source_filter: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    if not query.strip():
        raise LocalRAGError("Query cannot be empty")

    embedding_service = EmbeddingService(model_name=settings.EMBEDDING_MODEL)
    vector_store = VectorStore.get_cached(
        index_path=settings.FAISS_INDEX_PATH,
        embedding_dim=settings.EMBEDDING_DIM,
    )

    try:
        query_embedding = embedding_service.embed_query(query)
        # If filtering is needed, retrieve more candidates and filter them
        search_k = top_k * 10 if source_filter else top_k
        results = vector_store.search_with_metadata(query_embedding, top_k=search_k)

        if source_filter:
            # Case-insensitive partial match to handle UUID prefixes
            target_sources = [s.lower() for s in source_filter]
            filtered = [
                r
                for r in results
                if any(ts in str(r.get("source", "")).lower() for ts in target_sources)
            ]
            return filtered[:top_k]

        return results
    except EmbeddingError as exc:
        raise LocalRAGError(str(exc)) from exc
    except VectorStoreError as exc:
        raise LocalRAGError(str(exc)) from exc


def build_context_from_sources(sources: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for idx, item in enumerate(sources, start=1):
        source = item.get("source", "unknown")
        page = item.get("page")
        page_label = str(page) if page is not None else "unknown"
        text = item.get("text", "")
        lines.append(f"[S{idx}] source={source} page={page_label}\n{text}")
    return "\n\n".join(lines)


def generate_with_local_qwen(
    query: str,
    context: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_seconds: Optional[int] = 30,
) -> str:
    if not context.strip():
        return "No usable reference material was retrieved, so I cannot answer based on evidence."

    resolved_model = model or settings.LOCAL_QWEN_MODEL
    resolved_base_url = base_url or settings.LOCAL_QWEN_BASE_URL
    resolved_timeout = timeout_seconds or settings.LOCAL_QWEN_TIMEOUT_SECONDS

    payload = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Reference materials:\n{context}\n\nUser question: {query}",
            },
        ],
        "stream": False,
        "keep_alive": settings.LOCAL_QWEN_KEEP_ALIVE,
    }

    response = requests.post(
        f"{resolved_base_url.rstrip('/')}/api/chat",
        json=payload,
        timeout=resolved_timeout,
    )
    response.raise_for_status()

    data = response.json()
    message = data.get("message", {}).get("content")
    if not message:
        raise LocalRAGError("Invalid response format from local Qwen model")

    return str(message).strip()
