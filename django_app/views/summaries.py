import json
import time
from typing import Any, Dict

from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.services.runtime_llm import load_runtime_llm_settings
from app.services.summary_executor import request_cancel, submit
from app.services.topic_summarizer import (
    LENGTH_TOPIC_COUNTS,
    MAX_TOPICS,
    TopicSummarizerError,
    load_document_chunks,
)
from django_app.models import SummaryEvent, SummaryJob
from django_app.views.helpers import _error_response, _get_json_body

TERMINAL_STATUSES = {"completed", "failed", "cancelled", "interrupted"}
VALID_LENGTHS = set(LENGTH_TOPIC_COUNTS.keys())


def _serialize_job(job: SummaryJob) -> Dict[str, Any]:
    return {
        "id": str(job.id),
        "document_id": job.document_id,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "config": job.config,
        "detected_language": job.detected_language,
        "topics": job.topics,
        "result_markdown": job.result_markdown,
        "result_json": job.result_json,
        "citations": job.citations,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def _resolve_topic_count(config: Dict[str, Any]) -> int:
    length = config.get("length", "medium")
    topic_limit = config.get("topic_limit")
    count = LENGTH_TOPIC_COUNTS[length]
    if topic_limit is not None:
        count = int(topic_limit)
    return count


@csrf_exempt
@require_http_methods(["POST"])
def create_summary_job(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    document_id = str(payload.get("document_id", "")).strip()
    config = payload.get("config", {})
    if not isinstance(config, dict):
        config = {}

    if not document_id:
        return _error_response("document_id is required", status=400)

    length = str(config.get("length", "medium"))
    if length not in VALID_LENGTHS:
        return _error_response(
            f"length must be one of {sorted(VALID_LENGTHS)}", status=400
        )
    topic_limit = config.get("topic_limit")
    if topic_limit is not None:
        try:
            topic_limit_int = int(topic_limit)
        except (TypeError, ValueError):
            return _error_response("topic_limit must be an integer", status=400)
        if topic_limit_int > MAX_TOPICS:
            return _error_response(
                f"topic_limit must be at most {MAX_TOPICS}", status=400
            )

    try:
        load_document_chunks(document_id)
    except TopicSummarizerError as exc:
        return _error_response(str(exc), status=404)

    rt = load_runtime_llm_settings()
    job = SummaryJob.objects.create(
        document_id=document_id,
        config={**config, "provider": rt["provider"], "model": rt["model"]},
    )
    submit(str(job.id))

    topic_count = _resolve_topic_count(config)
    return JsonResponse(
        {
            "success": True,
            "job": _serialize_job(job),
            "estimate": {
                "topics": topic_count,
                "llm_calls": topic_count + 2,
            },
        }
    )


@require_http_methods(["GET"])
def list_summary_jobs(request: HttpRequest) -> JsonResponse:
    try:
        limit = int(request.GET.get("limit", 20))
    except ValueError:
        limit = 20
    limit = min(max(limit, 1), 50)

    jobs = SummaryJob.objects.all()[:limit]
    return JsonResponse(
        {
            "jobs": [_serialize_job(job) for job in jobs],
            "total": SummaryJob.objects.count(),
        }
    )


@require_http_methods(["GET"])
def get_summary_job(request: HttpRequest, job_id: str) -> JsonResponse:
    job = SummaryJob.objects.filter(id=job_id).first()
    if job is None:
        return _error_response("Summary job not found", status=404)
    return JsonResponse({"job": _serialize_job(job)})


@require_http_methods(["GET"])
def summary_job_events(request: HttpRequest, job_id: str) -> StreamingHttpResponse:
    job = SummaryJob.objects.filter(id=job_id).first()
    if job is None:
        return _error_response("Summary job not found", status=404)  # type: ignore[return-value]

    last_event_id_raw = request.META.get("HTTP_LAST_EVENT_ID", "")
    last_event_id = int(last_event_id_raw) if str(last_event_id_raw).isdigit() else 0

    def _sse_format(event: SummaryEvent) -> str:
        payload = dict(event.payload)
        payload.setdefault("stage", event.stage)
        return (
            f"id: {event.id}\n"
            f"event: {event.event_type}\n"
            f"data: {json.dumps(payload)}\n\n"
        )

    def event_stream():
        last_id = last_event_id
        for event in (
            SummaryEvent.objects.filter(job_id=job_id, id__gt=last_id)
            .order_by("id")
            .iterator()
        ):
            last_id = event.id
            yield _sse_format(event)

        current = SummaryJob.objects.get(id=job_id)
        while current.status not in TERMINAL_STATUSES:
            time.sleep(1)
            for event in (
                SummaryEvent.objects.filter(job_id=job_id, id__gt=last_id)
                .order_by("id")
                .iterator()
            ):
                last_id = event.id
                yield _sse_format(event)
            current.refresh_from_db()
            yield ": keep-alive\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@csrf_exempt
@require_http_methods(["POST"])
def cancel_summary_job(request: HttpRequest, job_id: str) -> JsonResponse:
    job = SummaryJob.objects.filter(id=job_id).first()
    if job is None:
        return _error_response("Summary job not found", status=404)
    if not request_cancel(str(job.id)):
        return _error_response("Summary job not found", status=404)
    return JsonResponse({"success": True})


@csrf_exempt
@require_http_methods(["POST"])
def retry_summary_job(request: HttpRequest, job_id: str) -> JsonResponse:
    job = SummaryJob.objects.filter(id=job_id).first()
    if job is None:
        return _error_response("Summary job not found", status=404)
    if job.status in {"queued", "running"}:
        return _error_response("Job is already queued or running", status=400)

    job.events.all().delete()
    job.status = "queued"
    job.stage = ""
    job.progress = 0
    job.error_code = ""
    job.error_message = ""
    job.cancel_requested = False
    job.completed_at = None
    job.save()
    submit(str(job.id))
    return JsonResponse({"success": True, "job": _serialize_job(job)})


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_summary_job(request: HttpRequest, job_id: str) -> JsonResponse:
    job = SummaryJob.objects.filter(id=job_id).first()
    if job is None:
        return _error_response("Summary job not found", status=404)
    if job.status in {"queued", "running"}:
        return _error_response("Cancel the job before deleting it", status=400)
    job.delete()
    return JsonResponse({"success": True})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def summary_jobs(request: HttpRequest) -> JsonResponse:
    """Dispatch the collection path: GET lists jobs, POST creates one."""
    if request.method == "GET":
        return list_summary_jobs(request)
    return create_summary_job(request)


@csrf_exempt
@require_http_methods(["GET", "DELETE"])
def summary_job_detail(request: HttpRequest, job_id: str) -> JsonResponse:
    """Dispatch the item path: GET fetches, DELETE removes."""
    if request.method == "DELETE":
        return delete_summary_job(request, job_id)
    return get_summary_job(request, job_id)
