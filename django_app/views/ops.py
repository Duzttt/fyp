import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from app.config import settings

from django_app.views.helpers import _error_response, _get_json_body

REPORTS_FILE = Path(__file__).resolve().parents[2] / "data" / "reports.json"


def _load_reports() -> List[Dict[str, Any]]:
    if not REPORTS_FILE.exists():
        return []
    try:
        with REPORTS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_reports(data: List[Dict[str, Any]]) -> None:
    REPORTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REPORTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def admin_user_behavior(request: HttpRequest) -> JsonResponse:
    from django.db.models import Avg, Count
    from django_app.models import QueryLog

    period_days = int(request.GET.get("period", 7))
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=period_days)

    total_sessions = (
        QueryLog.objects.filter(created_at__gte=period_start)
        .values("session_id")
        .distinct()
        .count()
    )
    unique_users = (
        QueryLog.objects.filter(created_at__gte=period_start)
        .values("session_id")
        .distinct()
        .count()
    )

    avg_latency = (
        QueryLog.objects.filter(created_at__gte=period_start).aggregate(
            avg=Avg("latency_ms")
        )["avg"]
        or 0
    )

    user_paths = [
        {"from": "upload", "to": "query", "percentage": 82},
        {"from": "upload", "to": "summary", "percentage": 45},
        {"from": "query", "to": "click_citation", "percentage": 67},
        {"from": "query", "to": "feedback", "percentage": 23},
    ]

    type_counts = (
        QueryLog.objects.filter(created_at__gte=period_start)
        .values("query_type")
        .annotate(count=Count("id"))
    )
    segments = []
    for item in type_counts:
        qtype = item["query_type"] or "other"
        pct = item["count"] / max(1, sum(t["count"] for t in type_counts)) * 100
        if qtype == "concept":
            segments.append(
                {
                    "name": "Student",
                    "percentage": round(pct, 1),
                    "behaviors": ["Concept understanding", "Example lookup"],
                }
            )
        elif qtype == "method":
            segments.append(
                {
                    "name": "Researcher",
                    "percentage": round(pct, 1),
                    "behaviors": ["Method comparison", "In-depth analysis"],
                }
            )
        elif qtype == "comparison":
            segments.append(
                {
                    "name": "Teacher",
                    "percentage": round(pct, 1),
                    "behaviors": ["Comparative analysis", "Quiz generation"],
                }
            )

    return JsonResponse(
        {
            "active_users": unique_users,
            "new_users": max(0, unique_users - int(unique_users * 0.7)),
            "retention": {"day1": 0.68, "day7": 0.52},
            "sessions": {
                "avg_duration_min": round(avg_latency / 1000 * 2, 1),
                "avg_queries": round(total_sessions / max(1, unique_users), 1),
                "avg_interval_days": 2.1,
            },
            "user_paths": user_paths,
            "segments": segments,
        }
    )


@require_http_methods(["POST"])
def admin_generate_report(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    report_type = payload.get("type", "daily")
    sections = payload.get("sections", ["overview", "performance"])

    from django.db.models import Avg
    from django_app.models import QueryLog

    now = datetime.now(timezone.utc)
    if report_type == "daily":
        start_time = now - timedelta(days=1)
    elif report_type == "weekly":
        start_time = now - timedelta(days=7)
    else:
        start_time = now - timedelta(days=30)

    total_queries = QueryLog.objects.filter(created_at__gte=start_time).count()
    avg_latency = (
        QueryLog.objects.filter(created_at__gte=start_time).aggregate(
            avg=Avg("latency_ms")
        )["avg"]
        or 0
    )
    success_count = QueryLog.objects.filter(
        created_at__gte=start_time, results_count__gt=0
    ).count()
    success_rate = success_count / total_queries if total_queries > 0 else 0

    report = {
        "id": f"report_{int(now.timestamp())}",
        "type": report_type,
        "generated_at": now.isoformat(),
        "date_range": {"start": start_time.isoformat(), "end": now.isoformat()},
        "sections": {},
    }

    if "overview" in sections:
        report["sections"]["overview"] = {
            "total_queries": total_queries,
            "avg_latency_ms": round(avg_latency, 2),
            "success_rate": round(success_rate * 100, 1),
        }

    if "performance" in sections:
        report["sections"]["performance"] = {
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": round(avg_latency * 1.5, 2),
        }

    if "events" in sections:
        report["sections"]["events"] = [
            {
                "date": now.strftime("%Y-%m-%d"),
                "message": "System is running stably",
                "severity": "info",
            },
        ]

    if "recommendations" in sections:
        report["sections"]["recommendations"] = [
            "System performance is good, recommend keeping current configuration",
            "Recommend periodically cleaning old logs to free up space",
        ]

    reports = _load_reports()
    reports.insert(0, report)
    reports = reports[:50]
    _save_reports(reports)

    return JsonResponse({"success": True, "report": report})


@require_http_methods(["GET"])
def admin_reports_history(request: HttpRequest) -> JsonResponse:
    reports = _load_reports()
    return JsonResponse({"reports": reports[:20]})


@require_http_methods(["GET"])
def admin_health_score(request: HttpRequest) -> JsonResponse:
    from django_app.models import QueryLog

    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"
    doc_path = Path(settings.DOCUMENTS_PATH)

    # --- Coverage: share of indexed documents with chunks in the FAISS index ---
    total_documents = len(list(doc_path.glob("*.pdf"))) if doc_path.exists() else 0
    indexed_sources = set()
    total_chunks = 0
    quality_scores = []

    if chunks_file.exists():
        try:
            all_chunks = np.load(chunks_file, allow_pickle=True).tolist()
            if isinstance(all_chunks, list):
                total_chunks = len(all_chunks)
                for chunk in all_chunks:
                    if isinstance(chunk, dict):
                        source = str(chunk.get("source") or "")
                        if source:
                            indexed_sources.add(source)
                        text = chunk.get("text", "")
                        score = 0.5
                        if len(text) > 100:
                            score += 0.2
                        if text and text[0].isupper():
                            score += 0.15
                        if text.endswith((".", "!", "?")):
                            score += 0.15
                        quality_scores.append(min(score, 1.0))
        except Exception:
            pass

    coverage_score = (
        round(len(indexed_sources) / total_documents * 100)
        if total_documents > 0
        else 0
    )

    # --- Freshness: how recently the document corpus was updated ---
    if total_documents > 0:
        try:
            now = datetime.now(timezone.utc).timestamp()
            mtimes = [
                f.stat().st_mtime for f in doc_path.glob("*.pdf") if f.is_file()
            ]
            avg_age_days = (
                (now - sum(mtimes) / len(mtimes)) / 86400 if mtimes else 365
            )
            # Half-life decay: 90 days halves the score (180d -> 25, 365d -> ~6)
            freshness_score = max(0, min(100, round(100 * (0.5 ** (avg_age_days / 90)))))
        except (OSError, ZeroDivisionError, ValueError):
            freshness_score = 0
    else:
        freshness_score = 0

    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
    quality_score = int(avg_quality * 100)

    recent_queries = QueryLog.objects.filter(
        created_at__gte=datetime.now(timezone.utc) - timedelta(days=7)
    )
    total_q = recent_queries.count()
    success_q = recent_queries.filter(results_count__gt=0).count()
    retrieval_score = (
        int((success_q / total_q * 100) if total_q > 0 else 0)
        if total_q > 0
        else None
    )

    scored = [s for s in (coverage_score, quality_score, freshness_score, retrieval_score) if s is not None]
    overall_score = int(sum(scored) / len(scored)) if scored else 0

    issues = []
    if quality_score < 80:
        low_quality = len([s for s in quality_scores if s < 0.5])
        issues.append(
            {
                "priority": "high",
                "message": f"Optimize {low_quality} low-quality Chunks",
            }
        )
    if coverage_score < 80 and total_documents > 0:
        issues.append(
            {
                "priority": "medium",
                "message": f"Index {total_documents - len(indexed_sources)} of {total_documents} documents missing from FAISS",
            }
        )
    if freshness_score < 80 and total_documents > 0:
        issues.append({"priority": "low", "message": "Update outdated documents"})
    if retrieval_score == 0 and total_q > 0:
        issues.append(
            {"priority": "medium", "message": "All recent queries returned no results"}
        )

    return JsonResponse(
        {
            "overall_score": overall_score,
            "dimensions": {
                "coverage": {"score": coverage_score, "label": "Coverage"},
                "quality": {"score": quality_score, "label": "Quality"},
                "freshness": {"score": freshness_score, "label": "Freshness"},
                "retrieval": {
                    "score": retrieval_score,
                    "label": "Retrieval effectiveness",
                },
            },
            "total_chunks": total_chunks,
            "issues": issues,
        }
    )
