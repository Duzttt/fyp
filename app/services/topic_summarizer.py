"""
Retrieval-based topic summarization pipeline.

Pure logic: no Django ORM usage. Retrieval and LLM calls are injected as
callables so the pipeline is fully unit-testable.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

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


@dataclass
class Topic:
    """A discovered topic. ``query`` is the retrieval query."""

    title: str
    query: str
    importance: int


def sample_chunks_for_topics(
    chunks: List[Dict[str, Any]], max_samples: int = 10
) -> List[Dict[str, Any]]:
    """Evenly sample up to max_samples chunks across the document."""
    if len(chunks) <= max_samples:
        return list(chunks)
    if max_samples <= 1:
        return [chunks[0]]
    step = (len(chunks) - 1) / (max_samples - 1)
    indices = [int(i * step) for i in range(max_samples)]
    return [chunks[i] for i in indices]


def _extract_json(raw: str) -> str:
    """Strip optional markdown fences around a JSON payload."""
    cleaned = raw.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()
    return cleaned


def _build_topic_proposal_messages(
    sample_chunks: List[Dict[str, Any]],
    language: str,
    topic_count: int,
) -> List[Dict[str, str]]:
    language_name = "Chinese" if language == "zh" else "English"
    excerpts = "\n\n".join(
        f"[{i}] {chunk.get('text', '')[:600]}"
        for i, chunk in enumerate(sample_chunks, start=1)
    )
    system = (
        "You are a document analysis assistant. Propose distinct, "
        "non-overlapping topics that cover the document's content."
    )
    user = (
        f"Document language: {language_name}. Output language: {language_name}.\n\n"
        f"Sample excerpts from the document:\n{excerpts}\n\n"
        f"Propose exactly {topic_count} distinct topics covering the document.\n"
        "Each topic needs a short title and a retrieval query "
        "(a phrase that would find that topic's content in a search engine).\n"
        "Respond ONLY with JSON in this shape:\n"
        '{"topics": [{"title": "string", "query": "string", "importance": 1}]}\n'
        "importance is an integer from 1 (minor) to 5 (central)."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def propose_topics(
    sample_chunks: List[Dict[str, Any]],
    language: str,
    topic_count: int,
    llm_call: Callable[[List[Dict[str, str]], Optional[str]], str],
) -> List[Topic]:
    """Ask the LLM for topics. One retry on malformed JSON, then fail."""
    messages = _build_topic_proposal_messages(sample_chunks, language, topic_count)
    last_error: Optional[Exception] = None
    for _attempt in range(2):
        try:
            raw = llm_call(messages, "json")
            data = json.loads(_extract_json(raw))
            topics = []
            for item in data.get("topics", []):
                title = str(item.get("title", "")).strip()
                query = str(item.get("query", "")).strip()
                importance = int(item.get("importance", 1))
                if title and query:
                    topics.append(
                        Topic(title=title, query=query, importance=importance)
                    )
            if not topics:
                raise ValueError("no topics in response")
            return topics
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            last_error = exc
    raise TopicSummarizerError(
        f"Topic discovery failed: {last_error}", code="malformed_json"
    )
