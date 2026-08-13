import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

import django

django.setup()

import json
from unittest.mock import patch

import pytest
import requests
from django.test import TestCase

from app.services.topic_summarizer import (
    TopicSummarizerError,
    build_llm_caller,
    build_retriever,
)
from app.services.summary_executor import (
    _run_job,
    mark_interrupted,
    request_cancel,
    submit,
)
from django_app.models import SummaryEvent, SummaryJob

# Note: DB tests below use django.test.TestCase (no pytest-django in this
# repo) — each test runs in a rolled-back transaction, no cleanup needed.

FAKE_RESULT = {
    "document_id": "doc.pdf",
    "language": "en",
    "overview": "Overview.",
    "topics": [{"title": "T", "query": "q", "importance": 3}],
    "sections": [{"title": "T", "points": [{"text": "point", "pages": [2]}]}],
    "skipped_topics": [],
    "markdown": "Overview.\n\n## T\n- point [p.2]\n",
}


class TestBuildLlmCaller:
    def test_timeout_maps_to_timeout_code(self, monkeypatch):
        def boom(*_args, **_kwargs):
            raise requests.Timeout("slow")

        monkeypatch.setattr("app.services.llm_client.call_llm", boom)
        caller = build_llm_caller()
        with pytest.raises(TopicSummarizerError) as exc_info:
            caller([{"role": "user", "content": "hi"}], None)
        assert exc_info.value.code == "timeout"

    def test_other_error_maps_to_llm_unavailable(self, monkeypatch):
        def boom(*_args, **_kwargs):
            raise RuntimeError("no server")

        monkeypatch.setattr("app.services.llm_client.call_llm", boom)
        caller = build_llm_caller()
        with pytest.raises(TopicSummarizerError) as exc_info:
            caller([{"role": "user", "content": "hi"}], None)
        assert exc_info.value.code == "llm_unavailable"


class TestBuildRetriever:
    def test_filters_by_source(self, monkeypatch):
        captured = {}

        def fake_retrieve_with_faiss(**kwargs):
            captured.update(kwargs)
            return [{"text": "x", "source": "doc.pdf", "page": 1}]

        monkeypatch.setattr(
            "app.services.local_rag.retrieve_with_faiss",
            fake_retrieve_with_faiss,
        )
        retrieve_fn = build_retriever("doc.pdf")
        results = retrieve_fn("query text", 6)
        assert captured["query"] == "query text"
        assert captured["top_k"] == 6
        assert captured["source_filter"] == ["doc.pdf"]
        assert captured["reranker_enabled"] is False
        assert results[0]["page"] == 1


class TestExecutorLifecycle(TestCase):
    def test_mark_interrupted_updates_active_jobs(self):
        SummaryJob.objects.create(document_id="a.pdf", status="queued")
        SummaryJob.objects.create(document_id="b.pdf", status="running")
        SummaryJob.objects.create(document_id="c.pdf", status="completed")
        assert mark_interrupted() == 2
        assert (
            SummaryJob.objects.filter(status="interrupted").count() == 2
        )

    def test_request_cancel_sets_flag_and_returns_true(self):
        job = SummaryJob.objects.create(document_id="a.pdf", status="running")
        assert request_cancel(str(job.id)) is True
        job.refresh_from_db()
        assert job.cancel_requested is True
        assert request_cancel(str(job.id)) is True  # idempotent

    def test_request_cancel_unknown_job_returns_false(self):
        assert request_cancel("00000000-0000-0000-0000-000000000000") is False

    def test_run_job_completes_and_persists_result(self):
        def fake_load_chunks(document_id):
            assert document_id == "doc.pdf"
            return [{"text": "content", "source": "doc.pdf", "page": 2}]

        def fake_run_pipeline(*_args, **kwargs):
            on_progress = kwargs.get("on_progress")
            if on_progress is not None:
                on_progress("language", 5, {"language": "en"})
                on_progress(
                    "partial",
                    40,
                    {
                        "section": {
                            "title": "T",
                            "points": [{"text": "point", "pages": [2]}],
                        }
                    },
                )
            return FAKE_RESULT

        with patch(
            "app.services.summary_executor.load_document_chunks", fake_load_chunks
        ), patch("app.services.summary_executor.run_pipeline", fake_run_pipeline):
            job = SummaryJob.objects.create(
                document_id="doc.pdf", config={"length": "medium"}
            )
            _run_job(str(job.id))
            job.refresh_from_db()

            assert job.status == "completed"
            assert job.progress == 100
            assert job.stage == "done"
            assert job.detected_language == "en"
            assert job.result_markdown == FAKE_RESULT["markdown"]
            assert job.result_json == FAKE_RESULT
            assert job.citations == [
                {
                    "topic": "T",
                    "points": [{"text": "point", "pages": [2]}],
                }
            ]
            assert job.topics == FAKE_RESULT["topics"]
            events = list(SummaryEvent.objects.filter(job=job).order_by("id"))
            assert events[0].event_type == "stage"
            assert any(e.event_type == "partial" for e in events)
            assert events[-1].event_type == "completed"

    def test_run_job_failure_persists_error(self):
        def fake_load_chunks(document_id):
            return [{"text": "c", "source": "doc.pdf", "page": 1}]

        def fake_run_pipeline(*_args, **_kwargs):
            raise TopicSummarizerError("LLM broke", code="llm_unavailable")

        with patch(
            "app.services.summary_executor.load_document_chunks", fake_load_chunks
        ), patch("app.services.summary_executor.run_pipeline", fake_run_pipeline):
            job = SummaryJob.objects.create(document_id="doc.pdf")
            _run_job(str(job.id))
            job.refresh_from_db()

            assert job.status == "failed"
            assert job.error_code == "llm_unavailable"
            assert "LLM broke" in job.error_message
            events = list(SummaryEvent.objects.filter(job=job))
            assert events[-1].event_type == "failed"

    def test_run_job_cancel_marks_cancelled(self):
        def fake_load_chunks(document_id):
            return [{"text": "c", "source": "doc.pdf", "page": 1}]

        def fake_run_pipeline(*_args, **_kwargs):
            raise TopicSummarizerError("Job cancelled", code="cancelled")

        with patch(
            "app.services.summary_executor.load_document_chunks", fake_load_chunks
        ), patch("app.services.summary_executor.run_pipeline", fake_run_pipeline):
            job = SummaryJob.objects.create(document_id="doc.pdf")
            _run_job(str(job.id))
            job.refresh_from_db()

            assert job.status == "cancelled"
            assert (
                list(SummaryEvent.objects.filter(job=job))[-1].event_type
                == "cancelled"
            )

    def test_run_job_document_not_indexed_fails_before_pipeline(self):
        def fake_load_chunks(_document_id):
            raise TopicSummarizerError("not indexed", code="document_not_indexed")

        with patch(
            "app.services.summary_executor.load_document_chunks", fake_load_chunks
        ):
            job = SummaryJob.objects.create(document_id="ghost.pdf")
            _run_job(str(job.id))
            job.refresh_from_db()
            assert job.status == "failed"
            assert job.error_code == "document_not_indexed"

    def test_submit_schedules_job(self):
        submitted = []

        class FakePool:
            def __init__(self, *args, **kwargs):
                pass

            def submit(self, fn, job_id):
                submitted.append(job_id)
                return None

        with patch("app.services.summary_executor._pool", FakePool()):
            job = SummaryJob.objects.create(document_id="a.pdf")
            submit(str(job.id))
            assert submitted == [str(job.id)]
