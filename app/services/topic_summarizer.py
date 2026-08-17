"""
Retrieval-based topic summarization pipeline.

Pure logic: no Django ORM usage. Retrieval and LLM calls are injected as
callables so the pipeline is fully unit-testable.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import requests

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
        "non-overlapping topics that cover the document's content. "
        "The topic title MUST be the exact wording of a real heading, "
        "section title, or slide title that actually appears in the "
        "document. Do NOT merge separate headings into one title and do "
        "NOT invent a title that is not present in the excerpts."
    )
    user = (
        f"Document language: {language_name}. Output language: {language_name}.\n\n"
        f"Sample excerpts from the document:\n{excerpts}\n\n"
        f"Propose exactly {topic_count} distinct topics covering the document.\n"
        "Each topic title must match a real heading/slide title in the "
        "document verbatim. Do not invent or combine headings.\n"
        "Each topic needs a short title and a retrieval query "
        "(a phrase that would find that topic's content in a search engine).\n"
        "List topics in descending order of importance (most central first).\n"
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
            seen_titles = set()
            topics = []
            for item in data.get("topics", []):
                title = str(item.get("title", "")).strip()
                query = str(item.get("query", "")).strip()
                try:
                    importance = int(item.get("importance", 1))
                except (TypeError, ValueError):
                    importance = 1
                if not title or not query:
                    continue
                if title.lower() in seen_titles:
                    continue
                seen_titles.add(title.lower())
                topics.append(
                    Topic(title=title, query=query, importance=importance)
                )
            if not topics:
                raise ValueError("no topics in response")
            topics.sort(key=lambda t: t.importance, reverse=True)
            return topics[:topic_count]
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            last_error = exc
    raise TopicSummarizerError(
        f"Topic discovery failed: {last_error}", code="malformed_json"
    )


@dataclass
class TopicPoint:
    text: str
    pages: List[int]


@dataclass
class TopicSection:
    title: str
    points: List[TopicPoint]


def build_topic_summary_messages(
    topic: Topic, chunks: List[Dict[str, Any]], language: str
) -> List[Dict[str, str]]:
    """Build prompt asking for a structured section summary with evidence refs."""
    language_name = "Chinese" if language == "zh" else "English"
    chunk_lines = []
    for i, chunk in enumerate(chunks, start=1):
        page = chunk.get("page")
        page_label = f"page {page}" if page is not None else "unknown page"
        chunk_lines.append(f"[{i}] ({page_label})\n{chunk.get('text', '')}")
    context = "\n\n".join(chunk_lines)
    system = (
        "You summarize retrieved document passages into concise study notes. "
        "Output language must match the requested language. "
        "Never invent facts; only use the provided passages."
    )
    user = (
        f"Topic: {topic.title}\n"
        f"Output language: {language_name}.\n\n"
        f"Retrieved passages:\n{context}\n\n"
        f"Write a summary section for this topic.\n"
        "Respond ONLY with JSON in this shape:\n"
        '{"heading": "string", "points": [{"text": "string", "evidence_chunk": 1}]}\n'
        "Include 3-8 points. evidence_chunk is the number of the passage "
        "([1], [2], ...) that supports the point."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _chunk_pages(chunks: List[Dict[str, Any]]) -> List[int]:
    """Return the distinct page numbers of the given chunks, in order."""
    pages: List[int] = []
    for chunk in chunks:
        page = chunk.get("page")
        if page is None:
            continue
        try:
            page_int = int(page)
        except (TypeError, ValueError):
            continue
        if page_int not in pages:
            pages.append(page_int)
    return pages


def parse_topic_summary_json(raw: str, chunks: List[Dict[str, Any]]) -> TopicSection:
    """Parse the topic summary JSON and map evidence refs to chunk pages."""
    try:
        data = json.loads(_extract_json(raw))
        heading = str(data.get("heading", "")).strip()
        points_raw = data.get("points")
        if not heading or not isinstance(points_raw, list) or not points_raw:
            raise ValueError("missing heading or points")
        points: List[TopicPoint] = []
        for item in points_raw:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            evidence = item.get("evidence_chunk")
            pages: List[int] = []
            if isinstance(evidence, int) and not isinstance(evidence, bool):
                if 1 <= evidence <= len(chunks):
                    pages = _chunk_pages([chunks[evidence - 1]])
            points.append(TopicPoint(text=text, pages=pages))
        if not points:
            raise ValueError("no valid points")
        return TopicSection(title=heading, points=points)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise TopicSummarizerError(
            f"Failed to parse topic summary: {exc}", code="malformed_json"
        ) from exc


def _page_key(chunk: Dict[str, Any]) -> int:
    """Stable sort key by page (unknown pages sort last)."""
    page = chunk.get("page")
    if page is None:
        return 10 ** 9
    try:
        return int(page)
    except (TypeError, ValueError):
        return 10 ** 9


def summarize_topic(
    topic: Topic,
    top_k: int,
    language: str,
    retrieve_fn: Callable[[str, int], List[Dict[str, Any]]],
    llm_call: Callable[[List[Dict[str, str]], Optional[str]], str],
) -> Optional[TopicSection]:
    """Retrieve chunks for one topic and summarize them. None when no hits.

    Retrieved chunks are reordered by page before being numbered and shown to
    the LLM, so the evidence_chunk index is a stable, document-ordered
    reference rather than a hybrid/MMR ranking artifact.
    """
    chunks = retrieve_fn(topic.query, top_k)
    if not chunks and topic.title and topic.title.lower() != topic.query.lower():
        # The discovery query missed; relax to the verbatim heading with a
        # wider window so a real section is not silently dropped as "skipped".
        chunks = retrieve_fn(topic.title, top_k * 2)
    if not chunks:
        return None
    chunks = sorted(chunks, key=_page_key)
    messages = build_topic_summary_messages(topic, chunks, language)
    last_error: Optional[Exception] = None
    for _attempt in range(2):
        try:
            raw = llm_call(messages, "json")
            return parse_topic_summary_json(raw, chunks)
        except TopicSummarizerError as exc:
            last_error = exc
    raise TopicSummarizerError(
        f"Topic '{topic.title}' failed: {last_error}", code="malformed_json"
    )


def generate_overview(
    sections: List[TopicSection],
    language: str,
    llm_call: Callable[[List[Dict[str, str]], Optional[str]], str],
) -> str:
    """Write a 2-3 sentence overview from the topic sections."""
    language_name = "Chinese" if language == "zh" else "English"
    digest = "\n".join(
        f"- {section.title}: " + "; ".join(point.text for point in section.points[:2])
        for section in sections
    )
    system = "You are a document summarization assistant."
    user = (
        f"Output language: {language_name}.\n\n"
        f"Topic sections of a document:\n{digest}\n\n"
        "Write a 2-3 sentence overview of the whole document. "
        "Output only the overview text."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    raw = llm_call(messages, None)
    overview = str(raw).strip()
    if not overview:
        raise TopicSummarizerError(
            "Overview generation returned empty output", code="malformed_json"
        )
    return overview


def render_markdown(overview: str, sections: List[TopicSection]) -> str:
    """Render canonical Markdown: overview + one section per topic."""
    lines: List[str] = [overview.strip(), ""]
    for section in sections:
        lines.append(f"## {section.title}")
        for point in section.points:
            pages = ", ".join(f"p.{page}" for page in point.pages)
            citation = f" [{pages}]" if pages else ""
            lines.append(f"- {point.text}{citation}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _resolve_topic_count(length: str, topic_limit: Optional[int]) -> int:
    count = LENGTH_TOPIC_COUNTS.get(length, LENGTH_TOPIC_COUNTS["medium"])
    if topic_limit is not None:
        count = int(topic_limit)
    return max(1, min(count, MAX_TOPICS))


def run_pipeline(
    document_id: str,
    chunks: List[Dict[str, Any]],
    length: str,
    retrieve_fn: Callable[[str, int], List[Dict[str, Any]]],
    llm_call: Callable[[List[Dict[str, str]], Optional[str]], str],
    topic_limit: Optional[int] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    on_progress: Optional[Callable[[str, int, Optional[Dict[str, Any]]], None]] = None,
) -> Dict[str, Any]:
    """Run the full retrieval-based topic summarization pipeline."""

    def report(
        stage: str, progress: int, payload: Optional[Dict[str, Any]] = None
    ) -> None:
        if on_progress is not None:
            on_progress(stage, progress, payload)

    language = detect_language([chunk.get("text", "") for chunk in chunks[:10]])
    report("language", 5, {"language": language})

    topic_count = _resolve_topic_count(length, topic_limit)
    samples = sample_chunks_for_topics(chunks, max_samples=10)
    topics = propose_topics(samples, language, topic_count, llm_call)
    topic_meta = [
        {"title": t.title, "query": t.query, "importance": t.importance} for t in topics
    ]
    report("topics", 15, {"topics": topic_meta, "language": language})

    top_k = LENGTH_TOP_K.get(length, LENGTH_TOP_K["medium"])
    topic_concurrency = max(1, int(getattr(settings, "SUMMARY_TOPIC_CONCURRENCY", 2)))
    sections: List[TopicSection] = []
    skipped_topics: List[str] = []
    completed = 0
    total = len(topics)

    def run_one(topic: Topic) -> Optional[TopicSection]:
        if is_cancelled is not None and is_cancelled():
            raise TopicSummarizerError("Job cancelled", code="cancelled")
        return summarize_topic(topic, top_k, language, retrieve_fn, llm_call)

    with ThreadPoolExecutor(max_workers=topic_concurrency) as pool:
        futures = {pool.submit(run_one, topic): topic for topic in topics}
        for future in as_completed(futures):
            topic = futures[future]
            if is_cancelled is not None and is_cancelled():
                raise TopicSummarizerError("Job cancelled", code="cancelled")
            try:
                section = future.result()
            except TopicSummarizerError as exc:
                if exc.code == "cancelled":
                    raise
                raise TopicSummarizerError(
                    f"Topic '{topic.title}' failed: {exc}", code=exc.code
                ) from exc
            completed += 1
            if section is not None:
                sections.append(section)
                progress = 15 + int(60 * completed / total)
                report(
                    "partial",
                    progress,
                    {
                        "section": {
                            "title": section.title,
                            "points": [
                                {"text": p.text, "pages": p.pages}
                                for p in section.points
                            ],
                        }
                    },
                )
            else:
                skipped_topics.append(topic.title)

    if not sections:
        raise TopicSummarizerError("No topics could be summarized", code="no_topics")

    report("overview", 85)
    overview = generate_overview(sections, language, llm_call)
    report("render", 95)
    markdown = render_markdown(overview, sections)

    return {
        "document_id": document_id,
        "language": language,
        "overview": overview,
        "topics": topic_meta,
        "sections": [
            {
                "title": section.title,
                "points": [
                    {"text": point.text, "pages": point.pages}
                    for point in section.points
                ],
            }
            for section in sections
        ],
        "skipped_topics": skipped_topics,
        "markdown": markdown,
    }


def build_llm_caller() -> Callable[[List[Dict[str, str]], Optional[str]], str]:
    """Wrap call_llm with runtime settings; map failures to error codes."""
    from app.services.llm_client import call_llm
    from app.services.runtime_llm import load_runtime_llm_settings

    rt = load_runtime_llm_settings()

    def llm_call(
        messages: List[Dict[str, str]], response_format: Optional[str] = None
    ) -> str:
        try:
            return call_llm(
                provider=rt["provider"],
                model=rt["model"],
                call_type="summary",
                messages=messages,
                api_key=rt["api_key"],
                base_url=rt["base_url"],
                timeout=settings.LOCAL_LLM_TIMEOUT_SECONDS,
                temperature=0.3,
                max_tokens=2048,
                response_format=response_format,
            )
        except requests.Timeout as exc:
            raise TopicSummarizerError("LLM request timed out", code="timeout") from exc
        except TopicSummarizerError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise TopicSummarizerError(
                f"LLM unavailable: {exc}", code="llm_unavailable"
            ) from exc

    return llm_call


def build_retriever(document_id: str) -> Callable[[str, int], List[Dict[str, Any]]]:
    """Wrap retrieve_with_faiss, restricted to one document."""

    def retrieve_fn(query: str, top_k: int) -> List[Dict[str, Any]]:
        from app.services.local_rag import retrieve_with_faiss

        return retrieve_with_faiss(
            query=query,
            top_k=top_k,
            source_filter=[document_id],
            reranker_enabled=False,
        )

    return retrieve_fn
