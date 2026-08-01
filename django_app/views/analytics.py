import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import faiss
import numpy as np
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings
from app.services.runtime_embedding import load_runtime_embedding_settings

from django_app.admin_utils import (
    QUERY_TYPE_COLORS,
    QUERY_TYPE_LABELS,
    QUERY_TYPE_PATTERNS,
    classify_query_type,
)
from django_app.views.helpers import _error_response, _get_json_body


@require_http_methods(["GET"])
def admin_document_analytics(request: HttpRequest, doc_id: str) -> JsonResponse:
    from django_app.models import QueryLog

    decoded_doc_id = urllib.parse.unquote(doc_id)
    days = int(request.GET.get("days", 90))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # To avoid N+1 queries and high memory usage, we fetch only the necessary fields.
    # We use values_list and an iterator to drastically reduce memory usage and avoid model instantiation overhead.
    logs = QueryLog.objects.filter(created_at__gte=cutoff).values_list(
        "retrieved_documents", "user_feedback", "query"
    )

    appearance_count = 0
    click_count = 0
    total_score = 0
    score_count = 0
    query_counts: Dict[str, int] = {}

    for retrieved, user_feedback, query in logs.iterator(chunk_size=1000):
        retrieved = retrieved or []
        matched = False
        for item in retrieved:
            source = item.get("source", "")
            if decoded_doc_id in source or source.endswith(decoded_doc_id):
                matched = True
                appearance_count += 1
                score = item.get("score", 0)
                if score > 0:
                    total_score += score
                    score_count += 1
                if user_feedback is True:
                    click_count += 1

        # Count each log entry once per document, regardless of how many
        # chunks of that document were retrieved in the same query.
        if matched:
            query_text = query.lower()
            query_counts[query_text] = query_counts.get(query_text, 0) + 1

    top_queries = sorted(
        [{"query": q, "count": c} for q, c in query_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    avg_score = total_score / score_count if score_count > 0 else 0
    click_rate = click_count / appearance_count if appearance_count > 0 else 0

    return JsonResponse(
        {
            "document_id": decoded_doc_id,
            "retrieval_stats": {
                "appearance_count": appearance_count,
                "avg_score": round(avg_score, 3),
                "click_count": click_count,
                "click_rate": round(click_rate, 3),
            },
            "top_queries": top_queries,
            "days": days,
        }
    )


@require_http_methods(["GET"])
def admin_query_clusters(request: HttpRequest) -> JsonResponse:
    from django_app.models import QueryLog

    days = int(request.GET.get("days", 30))
    limit = min(int(request.GET.get("limit", 1000)), 5000)

    start_time = datetime.now(timezone.utc) - timedelta(days=days)
    queries = list(
        QueryLog.objects.filter(created_at__gte=start_time)
        .values_list("query", flat=True)
        .distinct()[:limit]
    )

    if not queries:
        return JsonResponse(
            {
                "clusters": [],
                "total_queries": 0,
                "message": "No queries found for clustering",
            }
        )

    total = len(queries)

    # Group queries by keyword patterns (classify_query_type), not by the
    # stored query_type field, so historical logs cluster correctly too.
    cluster_queries: Dict[str, List[str]] = {
        qtype: [] for qtype in QUERY_TYPE_PATTERNS
    }
    cluster_queries["other"] = []

    for q in queries:
        cluster_queries[classify_query_type(q)].append(q)

    clusters = []
    for qtype, qlist in cluster_queries.items():
        if not qlist:
            continue
        clusters.append(
            {
                "name": QUERY_TYPE_LABELS.get(qtype, qtype),
                "query_type": qtype,
                "percentage": round(len(qlist) / total * 100, 1),
                "count": len(qlist),
                "patterns": QUERY_TYPE_PATTERNS.get(qtype, []),
                "color": QUERY_TYPE_COLORS.get(qtype, "#6b7280"),
                "representative": qlist[0],
                "sample_queries": qlist[:5],
            }
        )

    clusters.sort(key=lambda x: x["count"], reverse=True)

    return JsonResponse(
        {
            "clusters": clusters,
            "total_queries": total,
            "days": days,
        }
    )


# In-memory cache of 2D projections keyed by (method, perplexity, index fingerprint).
# The fingerprint includes index size + file mtime, so it invalidates on reindex.
_PROJECTION_CACHE: Dict[Tuple[str, int, str], Dict[str, Any]] = {}


@require_http_methods(["GET"])
def admin_embedding_visualization(request: HttpRequest) -> JsonResponse:
    method = request.GET.get("method", "pca")
    perplexity = int(request.GET.get("perplexity", 30))
    sample_size = min(int(request.GET.get("sample_size", 500)), 1000)

    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    if not chunks_file.exists():
        return JsonResponse(
            {
                "points": [],
                "documents": [],
                "error": "No indexed data found",
            }
        )

    try:
        all_chunks = np.load(chunks_file, allow_pickle=True).tolist()
        if not isinstance(all_chunks, list):
            return JsonResponse(
                {"points": [], "documents": [], "error": "Invalid data"}
            )
    except Exception:
        return JsonResponse(
            {"points": [], "documents": [], "error": "Failed to load data"}
        )

    documents = list(
        set(str(c.get("source", "unknown")) for c in all_chunks if isinstance(c, dict))
    )
    doc_colors = {
        doc: f"hsl({(i * 360 / len(documents)) % 360}, 70%, 50%)"
        for i, doc in enumerate(documents)
    }

    index_file = index_path / "index.faiss"
    if not index_file.exists():
        return JsonResponse(
            {
                "points": [],
                "documents": documents,
                "error": "No FAISS index found",
            }
        )

    try:
        index = faiss.read_index(str(index_file))
    except Exception:
        return JsonResponse(
            {
                "points": [],
                "documents": documents,
                "error": "Failed to load FAISS index",
            }
        )

    if index.ntotal != len(all_chunks):
        return JsonResponse(
            {
                "points": [],
                "documents": documents,
                "error": (
                    f"Index/chunk mismatch: {index.ntotal} vectors vs "
                    f"{len(all_chunks)} chunks"
                ),
            }
        )

    # Embeddings live in the FAISS index (index.faiss), not in chunks.npy,
    # so recover each vector by position — chunks.npy order matches index order.
    chunks_with_embeddings = []
    for i, chunk in enumerate(all_chunks):
        if isinstance(chunk, dict):
            chunks_with_embeddings.append(
                {
                    "index": i,
                    "text": chunk.get("text", ""),
                    "document": chunk.get("source", "unknown"),
                    "page": chunk.get("page"),
                    "embedding": index.reconstruct(i),
                }
            )

    if len(chunks_with_embeddings) < 10:
        return JsonResponse(
            {
                "points": [],
                "documents": documents,
                "error": "Not enough embeddings for visualization",
            }
        )

    embeddings = np.array([c["embedding"] for c in chunks_with_embeddings])

    rt = load_runtime_embedding_settings()
    if embeddings.shape[1] != rt["embedding_dim"]:
        return JsonResponse(
            {
                "points": [],
                "documents": documents,
                "error": f"Embedding dimension mismatch: {embeddings.shape[1]} vs {rt['embedding_dim']}",
            }
        )

    projection_start = time.perf_counter()
    explained_variance: Any = None
    try:
        from sklearn.decomposition import PCA
        from sklearn.manifold import TSNE

        # Cache projections so switching PCA/t-SNE is instant between requests.
        fingerprint = f"{index.ntotal}:{index_file.stat().st_mtime_ns}"
        cache_key = (method, perplexity, fingerprint)
        cached = _PROJECTION_CACHE.get(cache_key)

        if cached is not None:
            projected = cached["projected"]
            explained_variance = cached.get("explained_variance")
        else:
            if method == "tsne":
                tsne = TSNE(
                    n_components=2,
                    perplexity=min(perplexity, len(embeddings) - 1),
                    max_iter=1000,
                    random_state=42,
                )
                projected = tsne.fit_transform(embeddings)
            else:
                pca = PCA(n_components=2, random_state=42)
                projected = pca.fit_transform(embeddings)
                explained_variance = float(
                    sum(pca.explained_variance_ratio_[:2]) * 100
                )

            _PROJECTION_CACHE[cache_key] = {
                "projected": projected,
                "explained_variance": explained_variance,
            }
    except Exception:
        return JsonResponse(
            {
                "points": [],
                "documents": documents,
                "error": "Projection failed",
            }
        )
    projection_time_ms = round((time.perf_counter() - projection_start) * 1000, 1)

    points = []
    for i, chunk in enumerate(chunks_with_embeddings):
        points.append(
            {
                "x": float(projected[i, 0]),
                "y": float(projected[i, 1]),
                "chunk_index": chunk["index"],
                "document": chunk["document"],
                "document_color": doc_colors.get(chunk["document"], "#888"),
                "text_preview": chunk["text"],
                "page": chunk["page"],
            }
        )

    return JsonResponse(
        {
            "points": points[:sample_size],
            "documents": documents,
            "method": method,
            "total_chunks": len(chunks_with_embeddings),
            "explained_variance_ratio": explained_variance,
            "projection_time_ms": projection_time_ms,
        }
    )


@require_http_methods(["GET"])
def admin_chunk_quality(request: HttpRequest) -> JsonResponse:
    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    if not chunks_file.exists():
        return JsonResponse(
            {
                "chunks": [],
                "overall_score": 0,
                "error": "No indexed data found",
            }
        )

    try:
        all_chunks = np.load(chunks_file, allow_pickle=True).tolist()
        if not isinstance(all_chunks, list):
            return JsonResponse({"chunks": [], "error": "Invalid data"})
    except Exception:
        return JsonResponse({"chunks": [], "error": "Failed to load data"})

    from django_app.models import QueryLog

    days = int(request.GET.get("days", 90))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    chunk_stats: Dict[int, Dict[str, Any]] = {}

    for log in QueryLog.objects.filter(created_at__gte=cutoff):
        retrieved = log.retrieved_documents or []
        for item in retrieved:
            chunk_idx = item.get("chunk_index", -1)
            if chunk_idx >= 0:
                if chunk_idx not in chunk_stats:
                    chunk_stats[chunk_idx] = {"hits": 0, "total_score": 0}
                chunk_stats[chunk_idx]["hits"] += 1
                chunk_stats[chunk_idx]["total_score"] += item.get("score", 0)

    chunk_qualities = []
    for i, chunk in enumerate(all_chunks):
        if not isinstance(chunk, dict):
            continue

        text = chunk.get("text", "")
        stats = chunk_stats.get(i, {"hits": 0, "total_score": 0})

        # Base score with text-quality bonuses, retrieval signal,
        # and penalty deductions that stay in sync with the issue list.
        quality_score = 0.5

        if len(text) > 100:
            quality_score += 0.15
        if len(text) >= 300:
            quality_score += 0.05
        if text and text[0].isupper():
            quality_score += 0.05
        if " " in text.strip():
            quality_score += 0.05

        if stats["hits"] > 0:
            quality_score += 0.1
            avg_score = stats["total_score"] / stats["hits"]
            if avg_score > 0.7:
                quality_score += 0.2
            elif avg_score > 0.5:
                quality_score += 0.1
        else:
            quality_score -= 0.05

        issues = []
        if len(text) < 50:
            issues.append("Too short")
            quality_score -= 0.15
        if text.startswith("As mentioned") or text.startswith("Figure"):
            issues.append("Context dependent")
            quality_score -= 0.15
        if not text.endswith((".", "!", "?", ")")):
            issues.append("Incomplete sentence")
            quality_score -= 0.1

        quality_score = max(0.0, min(1.0, quality_score))

        chunk_qualities.append(
            {
                "index": i,
                "text_preview": text[:150] + "..." if len(text) > 150 else text,
                "source": chunk.get("source", ""),
                "page": chunk.get("page"),
                "quality_score": round(quality_score, 2),
                "retrieval_hits": stats["hits"],
                "avg_score": (
                    round(stats["total_score"] / stats["hits"], 3)
                    if stats["hits"] > 0
                    else 0
                ),
                "issues": issues,
            }
        )

    chunk_qualities.sort(key=lambda x: x["quality_score"], reverse=True)

    top_chunks = chunk_qualities[:10]
    low_chunks = [c for c in chunk_qualities if c["quality_score"] < 0.5][:10]

    overall = (
        sum(c["quality_score"] for c in chunk_qualities) / len(chunk_qualities)
        if chunk_qualities
        else 0
    )

    return JsonResponse(
        {
            "top_chunks": top_chunks,
            "low_quality_chunks": low_chunks,
            "overall_score": round(overall * 100),
            "total_chunks": len(chunk_qualities),
            "days": days,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def admin_retrieval_trace(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query", "")).strip()
    if not query:
        return _error_response("Query is required", status=400)

    trace_id = payload.get("trace_id") or f"trace_{int(time.time() * 1000)}"

    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStore

    stages = []

    start = time.perf_counter()
    query_processed = query.lower().strip()
    tokens = query_processed.split()
    query_time = (time.perf_counter() - start) * 1000

    stages.append(
        {
            "name": "query_processing",
            "time_ms": round(query_time, 2),
            "details": {
                "original": query,
                "processed": query_processed,
                "tokens": tokens,
                "token_count": len(tokens),
            },
        }
    )

    try:
        rt = load_runtime_embedding_settings()
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=rt["embedding_dim"],
        )
        embedding_service = EmbeddingService(model_name=rt["model_id"])

        start = time.perf_counter()
        query_embedding = embedding_service.embed_query(query)
        embed_time = (time.perf_counter() - start) * 1000

        stages.append(
            {
                "name": "embedding_generation",
                "time_ms": round(embed_time, 2),
                "details": {
                    "model": rt["model_id"],
                    "dimension": len(query_embedding),
                },
            }
        )

        top_k = payload.get("top_k", 5)

        start = time.perf_counter()
        dense_results = vector_store.search_with_metadata(
            query_embedding, top_k=top_k * 3
        )
        dense_time = (time.perf_counter() - start) * 1000

        stages.append(
            {
                "name": "dense_retrieval",
                "time_ms": round(dense_time, 2),
                "results": [
                    {
                        "source": r.get("source"),
                        "score": round(1 - r.get("distance", 0) / 2, 4),
                        "text_preview": r.get("text", "")[:100],
                    }
                    for r in dense_results[:top_k]
                ],
            }
        )

        from retrieval.hybrid_retriever import HybridRetriever, FusionMethod
        from retrieval.bm25_index import BM25Index

        all_chunks = vector_store.chunks
        if isinstance(all_chunks, list) and len(all_chunks) > 0:
            docs_for_bm25 = []
            for j, chunk in enumerate(all_chunks):
                text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                docs_for_bm25.append({"id": f"chunk_{j}", "text": text})

            if docs_for_bm25:
                bm25_idx = BM25Index(docs_for_bm25)

                start = time.perf_counter()
                bm25_results = bm25_idx.search(query, top_k=top_k * 3)
                bm25_time = (time.perf_counter() - start) * 1000

                stages.append(
                    {
                        "name": "bm25_retrieval",
                        "time_ms": round(bm25_time, 2),
                        "results": [
                            {
                                "doc_id": doc_id,
                                "score": round(score, 4),
                            }
                            for doc_id, score in bm25_results[:top_k]
                        ],
                    }
                )

                docs_for_hybrid = []
                for j, chunk in enumerate(all_chunks):
                    text = (
                        chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                    )
                    source = (
                        chunk.get("source", "unknown")
                        if isinstance(chunk, dict)
                        else "unknown"
                    )
                    docs_for_hybrid.append(
                        {
                            "id": f"chunk_{j}",
                            "text": text,
                            "source": source,
                        }
                    )

                hybrid_retriever = HybridRetriever(
                    documents=docs_for_hybrid,
                    fusion_method=FusionMethod.RRF,
                )

                start = time.perf_counter()
                hybrid_results = hybrid_retriever.retrieve(query, top_k=top_k)
                fusion_time = (time.perf_counter() - start) * 1000

                stages.append(
                    {
                        "name": "hybrid_fusion",
                        "time_ms": round(fusion_time, 2),
                        "method": "rrf",
                        "results": [
                            {
                                "id": r.get("id"),
                                "score": round(r.get("score", 0), 4),
                                "source": r.get("source"),
                            }
                            for r in hybrid_results
                        ],
                    }
                )

        context_start = time.perf_counter()
        top_chunks = dense_results[:3]
        context_lines = []
        for idx, item in enumerate(top_chunks, 1):
            source = item.get("source", "unknown")
            page = item.get("page")
            text = item.get("text", "")
            context_lines.append(f"[{idx}] source={source} page={page}\n{text}")
        context = "\n\n".join(context_lines)
        context_time = (time.perf_counter() - context_start) * 1000

        stages.append(
            {
                "name": "context_building",
                "time_ms": round(context_time, 2),
                "chunks_used": len(top_chunks),
                "context_length": len(context),
            }
        )

        total_time = sum(s["time_ms"] for s in stages)

        bottleneck = max(stages, key=lambda s: s["time_ms"])

        return JsonResponse(
            {
                "trace_id": trace_id,
                "query": query,
                "stages": stages,
                "total_time": round(total_time, 2),
                "bottleneck": bottleneck["name"],
            }
        )

    except Exception as exc:
        return _error_response(f"Trace failed: {str(exc)}", status=500)
