"""
Admin Dashboard Utilities

Helper functions for monitoring, analytics, and system diagnostics.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from django.db.models import Avg, Count

from app.config import settings
from app.services.runtime_embedding import load_runtime_embedding_settings
from app.services.runtime_llm import resolve_local_llm_urls
from django_app.models import ConfigHistory, QueryLog, SystemMetric


def get_system_stats() -> Dict[str, Any]:
    """
    Get comprehensive system statistics.

    Returns:
        Dictionary containing document stats, vector stats, and storage info.
    """
    # Document statistics
    doc_path = Path(settings.DOCUMENTS_PATH)
    pdf_files = list(doc_path.glob("*.pdf")) if doc_path.exists() else []
    total_documents = len(pdf_files)

    # Calculate total pages and size
    total_pages = 0
    total_docs_size = 0
    for pdf in pdf_files:
        try:
            total_docs_size += pdf.stat().st_size
            # Page count would require PDF parsing; use chunk estimate instead
        except OSError:
            continue

    # Vector store statistics
    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"
    index_file = index_path / "index.faiss"

    total_chunks = 0
    index_size = 0

    if chunks_file.exists():
        try:
            chunks_data = np.load(chunks_file, allow_pickle=True).tolist()
            if isinstance(chunks_data, list):
                total_chunks = len(chunks_data)
                # Estimate pages from chunks (rough estimate: ~2 chunks per page)
                total_pages = max(total_pages, len(chunks_data) // 2)
        except Exception:
            pass

    if index_file.exists():
        try:
            index_size = index_file.stat().st_size
        except OSError:
            pass

    # Storage statistics
    faiss_index_size_kb = index_size / 1024
    documents_size_kb = total_docs_size / 1024

    rt = load_runtime_embedding_settings()

    return {
        "documents": {
            "total": total_documents,
            "total_pages": total_pages,
            "total_chunks": total_chunks,
        },
        "vectors": {
            "dimension": rt["embedding_dim"],
            "index_type": "IndexFlatL2",
            "total_vectors": total_chunks,
        },
        "storage": {
            "faiss_index_size_kb": round(faiss_index_size_kb, 2),
            "documents_size_kb": round(documents_size_kb, 2),
        },
    }


def get_query_stats(time_range_hours: int = 24) -> Dict[str, Any]:
    """
    Get query statistics for a given time range.

    Args:
        time_range_hours: Number of hours to look back

    Returns:
        Dictionary containing query metrics.
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=time_range_hours)

    # Filter queries by time range
    queries = QueryLog.objects.filter(created_at__gte=cutoff_time)

    total_queries = queries.count()

    if total_queries == 0:
        return {
            "total_queries": 0,
            "avg_latency_ms": 0,
            "p95_latency_ms": 0,
            "cache_hit_rate": 0.0,
        }

    # Calculate latency statistics
    latencies = list(queries.values_list("latency_ms", flat=True))
    avg_latency = sum(latencies) / len(latencies)

    # P95 latency
    sorted_latencies = sorted(latencies)
    p95_index = int(len(sorted_latencies) * 0.95)
    p95_latency = sorted_latencies[min(p95_index, len(sorted_latencies) - 1)]

    # Cache hit rate
    cache_hits = queries.filter(cache_hit=True).count()
    cache_hit_rate = (cache_hits / total_queries * 100) if total_queries > 0 else 0

    return {
        "total_queries": total_queries,
        "avg_latency_ms": round(avg_latency, 2),
        "p95_latency_ms": p95_latency,
        "cache_hit_rate": round(cache_hit_rate, 2),
    }


def get_health_status() -> Dict[str, Any]:
    """
    Get system health status.

    Returns:
        Dictionary containing health checks for various components.
    """
    health_checks = {}

    # FAISS Index health
    index_path = Path(settings.FAISS_INDEX_PATH)
    index_file = index_path / "index.faiss"
    chunks_file = index_path / "chunks.npy"

    faiss_healthy = index_file.exists() and chunks_file.exists()
    health_checks["faiss_index"] = {
        "healthy": faiss_healthy,
        "message": "OK" if faiss_healthy else "Index files missing",
    }

    # LLM service health
    llm_healthy = True
    llm_message = "OK"

    if settings.LLM_PROVIDER == "gemini":
        llm_healthy = bool(settings.GEMINI_API_KEY)
        llm_message = "OK" if llm_healthy else "API key missing"
    elif settings.LLM_PROVIDER == "openrouter":
        llm_healthy = bool(settings.OPENROUTER_API_KEY)
        llm_message = "OK" if llm_healthy else "API key missing"
    elif settings.LLM_PROVIDER == "local_llm":
        # Check if llama.cpp server is reachable
        import httpx

        try:
            server_root, _ = resolve_local_llm_urls(settings.LOCAL_LLM_BASE_URL)
            response = httpx.get(f"{server_root}/health", timeout=5)
            llm_healthy = response.status_code == 200
            llm_message = "OK" if llm_healthy else "llama.cpp not responding"
        except Exception:
            llm_healthy = False
            llm_message = "Cannot connect to llama.cpp"

    health_checks["llm_service"] = {
        "healthy": llm_healthy,
        "message": llm_message,
        "provider": settings.LLM_PROVIDER,
    }

    # Disk space check
    try:
        import shutil

        total_disk, used_disk, free_disk = shutil.disk_usage(
            str(Path(settings.DOCUMENTS_PATH).parent)
        )
        free_disk_gb = free_disk / (1024**3)
        disk_healthy = free_disk_gb > 1.0  # At least 1GB free
        health_checks["disk_space"] = {
            "healthy": disk_healthy,
            "message": f"{free_disk_gb:.2f} GB free",
        }
    except Exception:
        health_checks["disk_space"] = {
            "healthy": True,
            "message": "Unable to check",
        }

    # Memory check (basic)
    try:
        import psutil

        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_healthy = memory_percent < 90
        health_checks["memory"] = {
            "healthy": memory_healthy,
            "message": f"{memory_percent}% used",
        }
    except ImportError:
        health_checks["memory"] = {
            "healthy": True,
            "message": "psutil not installed",
        }
    except Exception:
        health_checks["memory"] = {
            "healthy": True,
            "message": "Unable to check",
        }

    # Overall health
    all_healthy = all(check["healthy"] for check in health_checks.values())

    return {
        "overall_healthy": all_healthy,
        "checks": health_checks,
    }


def get_performance_data(time_range: str = "24h") -> Dict[str, Any]:
    """
    Get performance data for charts.

    Args:
        time_range: Time range specifier ("24h", "7d", etc.)

    Returns:
        Dictionary containing time series data for charts.
    """
    if time_range == "24h":
        hours = 24
        interval = timedelta(hours=1)
    elif time_range == "7d":
        hours = 168
        interval = timedelta(hours=6)
    else:
        hours = 24
        interval = timedelta(hours=1)

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Get latency trend
    latency_data = []
    current_time = cutoff_time
    while current_time < datetime.now(timezone.utc):
        window_end = current_time + interval
        queries = QueryLog.objects.filter(
            created_at__gte=current_time, created_at__lt=window_end
        )

        if queries.exists():
            avg_latency = queries.aggregate(Avg("latency_ms"))["latency_ms__avg"] or 0
            query_count = queries.count()
        else:
            avg_latency = 0
            query_count = 0

        latency_data.append(
            {
                "timestamp": current_time.isoformat(),
                "avg_latency_ms": round(avg_latency, 2),
                "query_count": query_count,
            }
        )

        current_time = window_end

    # Get query type distribution
    query_types = (
        QueryLog.objects.filter(created_at__gte=cutoff_time)
        .values("query_type")
        .annotate(count=Count("id"))
    )

    query_type_distribution = {
        item["query_type"]: item["count"] for item in query_types
    }

    # Get slow queries (top 5)
    slow_queries = QueryLog.objects.filter(created_at__gte=cutoff_time).order_by(
        "-latency_ms"
    )[:5]

    slow_queries_list = []
    for q in slow_queries:
        slow_queries_list.append(
            {
                "query": q.query[:100],
                "latency_ms": q.latency_ms,
                "query_type": q.query_type,
                "created_at": q.created_at.isoformat(),
                "possible_reason": _analyze_slow_query(q),
            }
        )

    return {
        "latency_trend": latency_data,
        "query_type_distribution": query_type_distribution,
        "slow_queries": slow_queries_list,
        "time_range": time_range,
    }


def _analyze_slow_query(query_log: QueryLog) -> str:
    """Analyze a slow query and suggest possible reasons."""
    reasons = []

    if query_log.latency_ms > 2000:
        reasons.append("Very high latency")

    if query_log.top_k > 10:
        reasons.append(f"High top_k ({query_log.top_k})")

    if not query_log.cache_hit:
        reasons.append("Cache miss")

    if query_log.results_count == 0:
        reasons.append("No results found")

    if len(query_log.query) > 200:
        reasons.append("Long query text")

    return "; ".join(reasons) if reasons else "Unknown"


# Query classification patterns — single source of truth shared by
# analytics (query clusters) and query logging (rag.py).
QUERY_TYPE_PATTERNS: Dict[str, List[str]] = {
    "concept": ["what is", "what are", "what's", "define", "explain", "meaning of", "what does"],
    "method": ["how to", "how do", "how does", "steps to", "process of", "method"],
    "comparison": ["difference between", "compare", " vs ", "versus"],
    "reason": ["why does", "why is", "why do", "reason", "because", "explain why"],
    "example": ["example", "application", "use case", "instance of"],
}

QUERY_TYPE_LABELS: Dict[str, str] = {
    "concept": "concept_definition",
    "method": "method_process",
    "comparison": "comparison",
    "reason": "reason_explanation",
    "example": "example_application",
    "other": "other_queries",
}

QUERY_TYPE_COLORS: Dict[str, str] = {
    "concept": "#22c55e",
    "method": "#3b82f6",
    "comparison": "#f59e0b",
    "reason": "#8b5cf6",
    "example": "#ec4899",
    "other": "#6b7280",
}


def classify_query_type(query: str) -> str:
    """
    Classify a query into a cluster type based on keyword patterns.

    Patterns are checked in definition order, so the first matching
    category wins. Returns "other" when no pattern matches.

    Args:
        query: The raw query text

    Returns:
        One of "concept", "method", "comparison", "reason", "example", or "other".
    """
    text = str(query).lower()
    for qtype, patterns in QUERY_TYPE_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            return qtype
    return "other"


def log_query(
    query: str,
    latency_ms: int,
    results_count: int,
    query_type: str = "other",
    cache_hit: bool = False,
    top_k: int = 3,
    similarity_threshold: float = 0.6,
    retrieved_documents: Optional[List] = None,
    user_feedback: Optional[bool] = None,
    session_id: str = "",
    llm_model: str = "",
    answer_length: int = 0,
    log_id: Optional[int] = None,
) -> QueryLog:
    """
    Log a query to the database.

    Args:
        query: The query text
        latency_ms: Query latency in milliseconds
        results_count: Number of results returned
        query_type: Type of query
        cache_hit: Whether result was from cache
        top_k: Top-K parameter used
        similarity_threshold: Similarity threshold used
        retrieved_documents: List of retrieved document references
        user_feedback: User feedback if provided
        session_id: Session identifier
        llm_model: LLM model used
        answer_length: Length of generated answer
        log_id: Existing QueryLog ID to update instead of creating a new row

    Returns:
        Created or updated QueryLog instance
    """
    payload = {
        "query": query,
        "query_type": query_type,
        "latency_ms": latency_ms,
        "cache_hit": cache_hit,
        "results_count": results_count,
        "top_k": top_k,
        "similarity_threshold": similarity_threshold,
        "retrieved_documents": retrieved_documents or [],
        "user_feedback": user_feedback,
        "session_id": session_id,
        "llm_model": llm_model,
        "answer_length": answer_length,
    }

    if log_id is not None:
        try:
            log_entry = QueryLog.objects.get(id=log_id)
        except QueryLog.DoesNotExist:
            pass
        else:
            for field, value in payload.items():
                setattr(log_entry, field, value)
            log_entry.save(update_fields=list(payload.keys()))
            return log_entry

    return QueryLog.objects.create(
        query=query,
        query_type=query_type,
        latency_ms=latency_ms,
        cache_hit=cache_hit,
        results_count=results_count,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        retrieved_documents=retrieved_documents or [],
        user_feedback=user_feedback,
        session_id=session_id,
        llm_model=llm_model,
        answer_length=answer_length,
    )


def record_metric(
    name: str,
    value: float,
    metadata: Optional[Dict[str, Any]] = None,
) -> SystemMetric:
    """
    Record a system metric.

    Args:
        name: Metric name
        value: Metric value
        metadata: Additional metadata

    Returns:
        Created SystemMetric instance
    """
    return SystemMetric.objects.create(
        name=name,
        value=value,
        metadata=metadata or {},
    )


def save_config_change(
    category: str,
    config: Dict[str, Any],
    previous_config: Optional[Dict[str, Any]] = None,
    changed_by: str = "system",
    reason: str = "",
) -> ConfigHistory:
    """
    Save a configuration change to history.

    Args:
        category: Configuration category
        config: New configuration values
        previous_config: Previous configuration values
        changed_by: Who made the change
        reason: Reason for the change

    Returns:
        Created ConfigHistory instance
    """
    # Deactivate previous active config for this category
    ConfigHistory.objects.filter(category=category, is_active=True).update(
        is_active=False
    )

    return ConfigHistory.objects.create(
        category=category,
        config=config,
        previous_config=previous_config or {},
        changed_by=changed_by,
        reason=reason,
        is_active=True,
    )
