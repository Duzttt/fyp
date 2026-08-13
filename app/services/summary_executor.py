"""
In-process executor for retrieval-based summary jobs.

Runs jobs on a bounded thread pool, publishes SummaryEvent rows, and
marks stale jobs interrupted at startup.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from django.utils import timezone

from app.config import settings
from app.services.topic_summarizer import (
    TopicSummarizerError,
    build_llm_caller,
    build_retriever,
    load_document_chunks,
    run_pipeline,
)
from django_app.models import SummaryEvent, SummaryJob

logger = logging.getLogger(__name__)

_pool = ThreadPoolExecutor(
    max_workers=max(1, int(settings.SUMMARY_JOB_CONCURRENCY)),
    thread_name_prefix="summary-job",
)
_cancel_flags: Dict[str, bool] = {}
_cancel_lock = threading.Lock()


def publish_event(
    job: SummaryJob,
    event_type: str,
    stage: str = "",
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Append an event row for the job."""
    SummaryEvent.objects.create(
        job=job,
        event_type=event_type,
        stage=stage,
        payload=payload or {},
    )


def _set_cancel_flag(job_id: str, value: bool) -> None:
    with _cancel_lock:
        if value:
            _cancel_flags[job_id] = True
        else:
            _cancel_flags.pop(job_id, None)


def _is_cancelled(job_id: str) -> bool:
    with _cancel_lock:
        return bool(_cancel_flags.get(job_id, False))


def request_cancel(job_id: str) -> bool:
    """Mark a job as cancel-requested. Returns False for unknown jobs."""
    updated = SummaryJob.objects.filter(id=job_id).update(
        cancel_requested=True, updated_at=timezone.now()
    )
    if updated:
        _set_cancel_flag(str(job_id), True)
    return updated == 1


def submit(job_id: str) -> None:
    """Schedule a queued job for execution."""
    _set_cancel_flag(str(job_id), False)
    _pool.submit(_run_job, str(job_id))


def mark_interrupted() -> int:
    """Mark stale queued/running jobs interrupted (called at startup)."""
    return SummaryJob.objects.filter(status__in=["queued", "running"]).update(
        status="interrupted", updated_at=timezone.now()
    )


def _claim(job_id: str) -> bool:
    updated = SummaryJob.objects.filter(id=job_id, status="queued").update(
        status="running",
        started_at=timezone.now(),
        updated_at=timezone.now(),
    )
    return updated == 1


def _run_job(job_id: str) -> None:
    """Execute one job end-to-end, publishing events along the way."""
    if not _claim(job_id):
        return

    job = SummaryJob.objects.get(id=job_id)

    def report(
        stage: str, progress: int, payload: Optional[Dict[str, Any]] = None
    ) -> None:
        SummaryJob.objects.filter(id=job_id).update(
            stage=stage,
            progress=progress,
            updated_at=timezone.now(),
        )
        event_payload = dict(payload or {})
        event_payload["progress"] = progress
        event_type = "partial" if stage == "partial" else "stage"
        publish_event(job, event_type, stage=stage, payload=event_payload)

    try:
        chunks = load_document_chunks(job.document_id)
        length = str(job.config.get("length", "medium"))
        topic_limit = job.config.get("topic_limit")
        llm_call = build_llm_caller()
        retrieve_fn = build_retriever(job.document_id)

        result = run_pipeline(
            document_id=job.document_id,
            chunks=chunks,
            length=length,
            retrieve_fn=retrieve_fn,
            llm_call=llm_call,
            topic_limit=topic_limit,
            is_cancelled=lambda: _is_cancelled(job_id),
            on_progress=report,
        )

        citations = [
            {
                "topic": section["title"],
                "points": [
                    {"text": point["text"], "pages": point["pages"]}
                    for point in section["points"]
                ],
            }
            for section in result["sections"]
        ]
        job.refresh_from_db()
        job.status = "completed"
        job.stage = "done"
        job.progress = 100
        job.detected_language = result["language"]
        job.topics = result["topics"]
        job.result_markdown = result["markdown"]
        job.result_json = result
        job.citations = citations
        job.completed_at = timezone.now()
        job.save()
        publish_event(
            job, "completed", stage="done", payload={"summary": result["markdown"]}
        )
    except TopicSummarizerError as exc:
        _finalize_failure(job_id, exc.code, str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Summary job %s crashed", job_id)
        _finalize_failure(job_id, "pipeline_error", str(exc))


def _finalize_failure(job_id: str, error_code: str, message: str) -> None:
    job = SummaryJob.objects.get(id=job_id)
    status = "cancelled" if error_code == "cancelled" else "failed"
    job.status = status
    job.error_code = error_code
    job.error_message = message
    job.completed_at = timezone.now()
    job.save()
    publish_event(
        job,
        "cancelled" if status == "cancelled" else "failed",
        stage=status,
        payload={"error_code": error_code, "error_message": message},
    )
