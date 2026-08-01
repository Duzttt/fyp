import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from app.config import settings
from app.services.embedding import EmbeddingError, EmbeddingService
from app.services.hybrid_retriever_service import HybridRetrieverService
from app.services.llm_client import call_llm
from app.services.runtime_embedding import load_runtime_embedding_settings
from app.services.runtime_llm import load_runtime_llm_settings, resolve_gemini_api_model
from app.services.vector_store import VectorStore, VectorStoreError
from config.retrieval_config import get_config

logger = logging.getLogger("local_rag")

SYSTEM_PROMPT = """You are an academic teaching assistant for lecture notes Q&A.

## Answer Rules
1. Base your answer **strictly** on the provided reference materials. Do not add outside knowledge.
2. Cite sources inline using the bracket labels provided, e.g. [S1], [S2]. Every factual claim must have at least one citation.
3. If the materials do not contain enough information to answer, say so explicitly — do not guess.
4. When multiple sources cover the same topic, synthesize them into a coherent answer and cite all relevant labels.
5. If sources conflict, point out the discrepancy and cite both.

## Output Format (Markdown)
Use proper Markdown formatting in your response:
- Use `**bold**` for key terms and important concepts
- Use `-` or `*` for bullet points
- Use `1.` for numbered steps or ordered lists
- Use `##` or `###` for section headings when organizing complex answers
- Use `> blockquotes` for definitions or important notes
- Use `code` backticks for technical terms, formulas, or code snippets
- Use ```language code blocks``` for longer code examples

Structure your answer with:
1. A direct answer (1-3 sentences)
2. Detailed explanation with headings, bullet points, or numbered steps
3. A **Sources** line listing only the labels you actually cited, e.g. `Sources: [S1], [S3]`

## Language
- ALWAYS respond in English. No matter what language the question is written in, your answer MUST be in English."""


class LocalRAGError(Exception):
    pass


def _source_matches(source: str, filter_str: str) -> bool:
    return source == filter_str or source.startswith(filter_str) or filter_str in source


def _record_stage(
    timings: Optional[List[Dict[str, Any]]],
    stage: str,
    started_at: float,
    candidates: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """Record a pipeline-stage duration for observability (trace/analytics)."""
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    if timings is not None:
        timings.append(
            {
                "stage": stage,
                "duration_ms": duration_ms,
                "candidates": len(candidates) if candidates is not None else None,
            }
        )
    return duration_ms


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = float(np.linalg.norm(a))
    b_norm = float(np.linalg.norm(b))
    if a_norm == 0.0 or b_norm == 0.0:
        return 0.0
    return float(np.dot(a, b) / (a_norm * b_norm))


def _mmr_select(
    candidates: List[Dict[str, Any]],
    vector_store: Optional[VectorStore],
    top_k: int,
    diversity_lambda: float = 0.7,
    max_chunks_per_source: int = 2,
) -> List[Dict[str, Any]]:
    """
    Greedy Maximum Marginal Relevance selection.

    Balances relevance (rerank/fusion score) against diversity (chunk-vector
    similarity against already-selected chunks). Also caps the number of
    chunks taken from the same source; the cap is relaxed when no other
    source has candidates left, so the system degrades gracefully instead of
    returning fewer results than requested.
    """
    if not candidates or top_k <= 0:
        return []

    # Best-effort reconstruction of chunk vectors from the persisted FAISS
    # index for inter-chunk similarity scoring.
    vectors: Dict[int, np.ndarray] = {}
    if vector_store is not None:
        indices = [
            c.get("chunk_index") for c in candidates if c.get("chunk_index") is not None
        ]
        vectors = vector_store.get_embeddings(indices)

    def _relevance(cand: Dict[str, Any]) -> float:
        return float(
            cand.get("rerank_score", cand.get("fusion_score", cand.get("score", 0.0)))
        )

    def _max_sim_to_selected(cand: Dict[str, Any]) -> float:
        cand_index = cand.get("chunk_index")
        cand_vec = vectors.get(cand_index) if cand_index is not None else None
        if cand_vec is None:
            return 0.0
        best = 0.0
        for selected in selected_chunks:
            selected_index = selected.get("chunk_index")
            selected_vec = (
                vectors.get(selected_index) if selected_index is not None else None
            )
            if selected_vec is not None:
                best = max(best, _cosine_similarity(cand_vec, selected_vec))
        return best

    selected_chunks: List[Dict[str, Any]] = []
    remaining = list(candidates)

    while len(selected_chunks) < top_k and remaining:
        # Sources that still have room under the per-source cap.
        open_sources = {
            c.get("source", "unknown")
            for c in remaining
            if sum(
                1
                for s in selected_chunks
                if s.get("source") == c.get("source", "unknown")
            )
            < max_chunks_per_source
        }
        has_open_source = len(open_sources) > 0

        best_index = -1
        best_mmr = float("-inf")
        for i, cand in enumerate(remaining):
            source = cand.get("source", "unknown")
            source_count = sum(1 for s in selected_chunks if s.get("source") == source)
            if source_count >= max_chunks_per_source and has_open_source:
                # Prefer candidates from sources below the cap when possible.
                continue

            relevance = _relevance(cand)
            max_sim = _max_sim_to_selected(cand)
            mmr = diversity_lambda * relevance - (1.0 - diversity_lambda) * max_sim
            if mmr > best_mmr:
                best_mmr = mmr
                best_index = i

        if best_index < 0:
            break
        selected_chunks.append(remaining.pop(best_index))

    return selected_chunks


def retrieve_with_faiss(
    query: str,
    top_k: int = 5,
    source_filter: Optional[List[str]] = None,
    similarity_threshold: Optional[float] = None,
    reranker_enabled: Optional[bool] = None,
    minimum_relevance_score: Optional[float] = None,
    stage_timings: Optional[List[Dict[str, Any]]] = None,
    rerank_details: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if not query.strip():
        raise LocalRAGError("Query cannot be empty")

    retrieval_config = get_config().retrieval

    # The default Dense cosine threshold (settings.SIMILARITY_THRESHOLD) is no
    # longer applied to hybrid results: a BM25-only exact match with a low
    # cosine score must not be dropped by the Dense threshold. The threshold
    # only applies to the pure-dense fallback path, and only when explicitly
    # provided by the caller.
    rerank = (
        reranker_enabled
        if reranker_enabled is not None
        else retrieval_config.reranker_enabled
    )

    # Over-fetch candidates for reranking / threshold filtering. The
    # cross-encoder only ever sees the fused top candidates, not the raw
    # BM25/FAISS pools.
    if rerank or minimum_relevance_score is not None:
        candidate_k = max(top_k * 3, retrieval_config.rerank_candidate_top_k, 20)
    else:
        candidate_k = top_k

    # --- Retrieve candidates (BM25 + persisted FAISS, RRF-fused) ---
    started_at = time.perf_counter()
    candidates: List[Dict[str, Any]] = []
    hybrid_service = HybridRetrieverService.get_instance()
    if hybrid_service is not None:
        try:
            candidates = hybrid_service.search(
                query=query, top_k=candidate_k, candidate_top_k=candidate_k
            )
        except Exception as exc:
            logger.warning("Hybrid retrieval failed, falling back to dense: %s", exc)
    _record_stage(stage_timings, "bm25_dense_fusion", started_at, candidates)

    used_dense_fallback = False
    if not candidates:
        rt = load_runtime_embedding_settings()
        embedding_service = EmbeddingService(model_name=rt["model_id"])
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=rt["embedding_dim"],
        )
        try:
            query_embedding = embedding_service.embed_query(query)
            candidates = vector_store.search_with_metadata(
                query_embedding, top_k=candidate_k
            )
            used_dense_fallback = True
        except EmbeddingError as exc:
            raise LocalRAGError(str(exc)) from exc
        except VectorStoreError as exc:
            raise LocalRAGError(str(exc)) from exc

    # --- Source filter ---
    if source_filter:
        normalized_filters = [str(s).lower().strip() for s in source_filter]
        candidates = [
            r
            for r in candidates
            if any(
                _source_matches(str(r.get("source", "")).lower().strip(), f)
                for f in normalized_filters
            )
        ]

    # --- Dense fallback cosine threshold (explicitly provided only) ---
    if (
        used_dense_fallback
        and similarity_threshold is not None
        and similarity_threshold > 0
    ):
        candidates = [
            r
            for r in candidates
            if r.get("cosine_similarity", r.get("distance", 0.0))
            >= similarity_threshold
        ]

    # --- Cross-Encoder rerank (only the fused candidates) ---
    if rerank and candidates:
        started = time.perf_counter()
        from app.services.cross_encoder_reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker.get_instance(
            settings.CROSS_ENCODER_MODEL, settings.CROSS_ENCODER_DEVICE
        )
        if rerank_details is not None:
            rerank_details["enabled"] = True
            rerank_details["model"] = settings.CROSS_ENCODER_MODEL
            rerank_details["device"] = reranker.device
            rerank_details["candidates_before"] = [
                {
                    "chunk_index": r.get("chunk_index"),
                    "source": r.get("source", "unknown"),
                    "page": r.get("page"),
                    "text": r.get("text", ""),
                    "fusion_score": r.get("fusion_score", r.get("score", 0.0)),
                    "bm25_score": r.get("bm25_score", 0.0),
                    "dense_score": r.get("dense_score", 0.0),
                }
                for r in candidates
            ]
        candidates = reranker.rerank(query, candidates)
        if rerank_details is not None:
            rerank_details["candidates_after"] = [
                {
                    "chunk_index": r.get("chunk_index"),
                    "source": r.get("source", "unknown"),
                    "page": r.get("page"),
                    "text": r.get("text", ""),
                    "rerank_score": r.get("rerank_score", 0.0),
                    "fusion_score": r.get("fusion_score", r.get("score", 0.0)),
                }
                for r in candidates
            ]
        _record_stage(stage_timings, "rerank", started, candidates)

    # --- Explicit final-score threshold (applies to the reranker score) ---
    if minimum_relevance_score is not None:
        candidates = [
            r
            for r in candidates
            if r.get("rerank_score", r.get("score", 0.0)) >= minimum_relevance_score
        ]
        _record_stage(stage_timings, "threshold", started_at, candidates)

    # --- MMR diversity selection + per-source cap ---
    if candidates:
        started = time.perf_counter()
        mmr_vector_store: Optional[VectorStore] = None
        if not used_dense_fallback:
            try:
                rt = load_runtime_embedding_settings()
                mmr_vector_store = VectorStore.get_cached(
                    index_path=settings.FAISS_INDEX_PATH,
                    embedding_dim=rt["embedding_dim"],
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load FAISS for MMR diversity: %s", exc)
        candidates = _mmr_select(
            candidates,
            vector_store=mmr_vector_store,
            top_k=top_k,
            diversity_lambda=retrieval_config.diversity_lambda,
            max_chunks_per_source=retrieval_config.max_chunks_per_source,
        )
        _record_stage(stage_timings, "mmr_diversity", started, candidates)

    return candidates[:top_k]


def build_context_from_sources(sources: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for idx, item in enumerate(sources, start=1):
        source = item.get("source", "unknown")
        page = item.get("page")
        page_label = str(page) if page is not None else "unknown"
        text = item.get("text", "")
        lines.append(f"[S{idx}] (source: {source}, page: {page_label})\n{text}")
    return "\n\n".join(lines)


def build_rag_messages(
    query: str,
    context: str,
) -> List[Dict[str, str]]:
    user_content = f"## Reference Materials\n{context}\n\n" f"## Question\n{query}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def generate_with_local_llm(
    query: str,
    context: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_seconds: Optional[int] = 30,
    return_log: bool = False,
    return_thinking: bool = False,
) -> Union[
    str,
    Tuple[str, int],
    Tuple[str, Optional[str]],
    Tuple[str, Optional[str], int],
]:
    if not context.strip():
        return "No usable reference material was retrieved, so I cannot answer based on evidence."

    runtime_settings = load_runtime_llm_settings()
    resolved_model = model or runtime_settings["model"] or settings.LOCAL_LLM_MODEL
    resolved_base_url = (
        base_url or runtime_settings["base_url"] or settings.LOCAL_LLM_BASE_URL
    )
    resolved_timeout = timeout_seconds or settings.LOCAL_LLM_TIMEOUT_SECONDS

    try:
        return call_llm(
            provider="local_llm",
            model=resolved_model,
            call_type="qa",
            messages=build_rag_messages(query, context),
            timeout=resolved_timeout,
            query_text=query,
            base_url=resolved_base_url,
            num_predict=settings.LLM_MAX_OUTPUT_TOKENS,
            return_log=return_log,
            return_thinking=return_thinking,
        )
    except ValueError as exc:
        raise LocalRAGError(str(exc)) from exc


def generate_with_openrouter(
    query: str,
    context: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.7,
    timeout_seconds: int = 60,
    return_log: bool = False,
) -> Union[str, Tuple[str, int]]:
    if not context.strip():
        return "No usable reference material was retrieved, so I cannot answer based on evidence."

    runtime_settings = load_runtime_llm_settings()
    resolved_model = model or runtime_settings["model"] or settings.OPENROUTER_MODEL
    resolved_key = api_key or runtime_settings["api_key"] or settings.OPENROUTER_API_KEY
    resolved_base_url = (
        base_url or runtime_settings["base_url"] or settings.OPENROUTER_BASE_URL
    )

    if not resolved_key:
        raise LocalRAGError("OPENROUTER_API_KEY is not configured")

    try:
        return call_llm(
            provider="openrouter",
            model=resolved_model,
            call_type="qa",
            messages=build_rag_messages(query, context),
            timeout=timeout_seconds,
            query_text=query,
            api_key=resolved_key,
            base_url=resolved_base_url,
            temperature=temperature,
            max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
            return_log=return_log,
        )
    except ValueError as exc:
        raise LocalRAGError(str(exc)) from exc


def generate_with_gemini(
    query: str,
    context: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.7,
    timeout_seconds: int = 60,
    return_log: bool = False,
) -> Union[str, Tuple[str, int]]:
    if not context.strip():
        return "No usable reference material was retrieved, so I cannot answer based on evidence."

    runtime_settings = load_runtime_llm_settings()
    resolved_model = resolve_gemini_api_model(model, runtime_settings["model"])
    resolved_key = api_key or runtime_settings["api_key"] or settings.GEMINI_API_KEY
    resolved_base_url = (
        base_url or runtime_settings["base_url"] or settings.GEMINI_BASE_URL
    )

    if not resolved_key:
        raise LocalRAGError("GEMINI_API_KEY is not configured")

    try:
        return call_llm(
            provider="gemini",
            model=resolved_model,
            call_type="qa",
            messages=build_rag_messages(query, context),
            timeout=timeout_seconds,
            query_text=query,
            api_key=resolved_key,
            base_url=resolved_base_url,
            temperature=temperature,
            max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
            return_log=return_log,
        )
    except ValueError as exc:
        raise LocalRAGError(str(exc)) from exc


def generate(
    query: str,
    context: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    timeout_seconds: int = 60,
    return_log: bool = False,
    return_thinking: bool = False,
) -> Union[
    str,
    Tuple[str, int],
    Tuple[str, Optional[str]],
    Tuple[str, Optional[str], int],
]:
    runtime_settings = load_runtime_llm_settings()
    provider = runtime_settings["provider"] or settings.LLM_PROVIDER

    if provider == "gemini":
        return generate_with_gemini(
            query=query,
            context=context,
            model=model,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            api_key=runtime_settings["api_key"],
            base_url=runtime_settings["base_url"],
            return_log=return_log,
        )
    elif provider == "openrouter":
        return generate_with_openrouter(
            query=query,
            context=context,
            model=model,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            api_key=runtime_settings["api_key"],
            base_url=runtime_settings["base_url"],
            return_log=return_log,
        )
    elif provider == "local_llm":
        return generate_with_local_llm(
            query=query,
            context=context,
            model=model,
            timeout_seconds=timeout_seconds,
            base_url=runtime_settings["base_url"],
            return_log=return_log,
            return_thinking=return_thinking,
        )
    else:
        raise LocalRAGError(f"Unsupported LLM_PROVIDER: {provider}")
