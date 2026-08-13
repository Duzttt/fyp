import json
import os
from unittest import mock

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

import django

django.setup()

from django.test import Client, TestCase
from django_app.models import SummaryEvent, SummaryJob

# Note: DB tests use django.test.TestCase (no pytest-django in this repo) —
# each test runs in a rolled-back transaction. pytest (7.4) does NOT inject
# fixtures into unittest.TestCase methods, so a plain `Client` plus
# `unittest.mock.patch` context managers are used instead of the
# `client`/`monkeypatch` pytest fixtures.


class TestCreateJob(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_create_job_with_valid_document(self):
        def fake_chunks(document_id):
            assert document_id == "lecture.pdf"
            return [{"text": "c", "source": "lecture.pdf", "page": 1}]

        submitted = []
        with mock.patch(
            "django_app.views.summaries.load_document_chunks", new=fake_chunks
        ), mock.patch(
            "django_app.views.summaries.submit",
            new=lambda job_id: submitted.append(job_id),
        ):
            response = self.client.post(
                "/api/summary/jobs",
                data=json.dumps(
                    {"document_id": "lecture.pdf", "config": {"length": "detailed"}}
                ),
                content_type="application/json",
            )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        job_id = data["job"]["id"]
        assert submitted == [job_id]
        job = SummaryJob.objects.get(id=job_id)
        assert job.config["length"] == "detailed"
        assert job.status == "queued"
        assert data["estimate"]["topics"] == 12
        assert data["estimate"]["llm_calls"] == 14

    def test_create_job_missing_document_id(self):
        response = self.client.post(
            "/api/summary/jobs",
            data=json.dumps({"config": {}}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_create_job_unindexed_document(self):
        from app.services.topic_summarizer import TopicSummarizerError

        def fake_chunks(_document_id):
            raise TopicSummarizerError("not indexed", code="document_not_indexed")

        with mock.patch(
            "django_app.views.summaries.load_document_chunks", new=fake_chunks
        ):
            response = self.client.post(
                "/api/summary/jobs",
                data=json.dumps({"document_id": "ghost.pdf", "config": {}}),
                content_type="application/json",
            )
        assert response.status_code == 404
        assert response.json()["detail"] == "not indexed"

    def test_create_job_invalid_length(self):
        response = self.client.post(
            "/api/summary/jobs",
            data=json.dumps({"document_id": "a.pdf", "config": {"length": "huge"}}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_create_job_topic_limit_above_max_rejected(self):
        response = self.client.post(
            "/api/summary/jobs",
            data=json.dumps({"document_id": "a.pdf", "config": {"topic_limit": 99}}),
            content_type="application/json",
        )
        assert response.status_code == 400


class TestListAndDetail(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_list_jobs_paginated(self):
        for i in range(3):
            SummaryJob.objects.create(document_id=f"doc{i}.pdf")
        response = self.client.get("/api/summary/jobs?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 2
        assert data["total"] == 3

    def test_get_job_detail(self):
        job = SummaryJob.objects.create(
            document_id="a.pdf",
            status="completed",
            progress=100,
            result_markdown="# Summary",
        )
        response = self.client.get(f"/api/summary/jobs/{job.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job"]["result_markdown"] == "# Summary"
        assert data["job"]["status"] == "completed"

    def test_get_job_missing_returns_404(self):
        response = self.client.get(
            "/api/summary/jobs/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404


class TestCancelRetryDelete(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_cancel_job(self):
        job = SummaryJob.objects.create(document_id="a.pdf", status="running")
        with mock.patch(
            "django_app.views.summaries.request_cancel", new=lambda job_id: True
        ):
            response = self.client.post(f"/api/summary/jobs/{job.id}/cancel")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_cancel_unknown_job(self):
        with mock.patch(
            "django_app.views.summaries.request_cancel", new=lambda job_id: False
        ):
            response = self.client.post(
                "/api/summary/jobs/00000000-0000-0000-0000-000000000000/cancel"
            )
        assert response.status_code == 404

    def test_retry_failed_job(self):
        submitted = []
        job = SummaryJob.objects.create(
            document_id="a.pdf", status="failed", error_code="llm_unavailable"
        )
        SummaryEvent.objects.create(job=job, event_type="failed", payload={"x": 1})
        with mock.patch(
            "django_app.views.summaries.submit",
            new=lambda job_id: submitted.append(job_id),
        ):
            response = self.client.post(f"/api/summary/jobs/{job.id}/retry")
        assert response.status_code == 200
        job.refresh_from_db()
        assert job.status == "queued"
        assert job.error_code == ""
        assert job.events.count() == 0
        assert submitted == [str(job.id)]

    def test_retry_running_job_rejected(self):
        job = SummaryJob.objects.create(document_id="a.pdf", status="running")
        response = self.client.post(f"/api/summary/jobs/{job.id}/retry")
        assert response.status_code == 400

    def test_delete_job(self):
        job = SummaryJob.objects.create(document_id="a.pdf", status="completed")
        SummaryEvent.objects.create(job=job, event_type="completed")
        response = self.client.delete(f"/api/summary/jobs/{job.id}")
        assert response.status_code == 200
        assert SummaryJob.objects.filter(id=job.id).count() == 0
        assert SummaryEvent.objects.count() == 0

    def test_delete_running_job_rejected(self):
        job = SummaryJob.objects.create(document_id="a.pdf", status="running")
        response = self.client.delete(f"/api/summary/jobs/{job.id}")
        assert response.status_code == 400


class TestSSE(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_sse_replays_events_and_terminates(self):
        job = SummaryJob.objects.create(document_id="a.pdf", status="completed")
        SummaryEvent.objects.create(
            job=job, event_type="stage", stage="topics", payload={"topics": []}
        )
        SummaryEvent.objects.create(
            job=job, event_type="completed", stage="done", payload={}
        )
        response = self.client.get(f"/api/summary/jobs/{job.id}/events")
        assert response.status_code == 200
        assert response["Content-Type"] == "text/event-stream"
        body = b"".join(response.streaming_content).decode("utf-8")
        assert "event: stage" in body
        assert "event: completed" in body
        assert body.startswith("id: ")

    def test_sse_last_event_id_replays_only_newer(self):
        job = SummaryJob.objects.create(document_id="a.pdf", status="completed")
        first = SummaryEvent.objects.create(
            job=job, event_type="stage", stage="language", payload={}
        )
        SummaryEvent.objects.create(
            job=job, event_type="completed", stage="done", payload={}
        )
        response = self.client.get(
            f"/api/summary/jobs/{job.id}/events",
            HTTP_LAST_EVENT_ID=str(first.id),
        )
        body = b"".join(response.streaming_content).decode("utf-8")
        assert "event: stage" not in body
        assert "event: completed" in body

    def test_sse_missing_job_returns_404(self):
        response = self.client.get(
            "/api/summary/jobs/00000000-0000-0000-0000-000000000000/events"
        )
        assert response.status_code == 404
