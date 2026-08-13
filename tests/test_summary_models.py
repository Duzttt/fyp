import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

import django

django.setup()

from django.test import TestCase
from django_app.models import SummaryEvent, SummaryJob


class SummaryJobModelTests(TestCase):
    def test_summary_job_defaults(self):
        job = SummaryJob.objects.create(
            document_id="lecture1.pdf", config={"length": "medium"}
        )
        assert job.status == "queued"
        assert job.progress == 0
        assert job.stage == ""
        assert job.config == {"length": "medium"}
        assert job.cancel_requested is False
        assert job.error_code == ""
        assert job.topics == []
        assert job.citations == []
        assert job.result_json == {}

    def test_summary_event_belongs_to_job_and_cascades(self):
        job = SummaryJob.objects.create(document_id="a.pdf")
        event = SummaryEvent.objects.create(
            job=job, event_type="stage", stage="topics", payload={"n": 4}
        )
        assert event.job_id == job.id
        assert event.payload == {"n": 4}
        assert job.events.count() == 1
        job.delete()
        assert SummaryEvent.objects.count() == 0

    def test_summary_job_status_choices_enforced(self):
        job = SummaryJob.objects.create(document_id="b.pdf")
        job.status = "completed"
        job.save()
        job.refresh_from_db()
        assert job.status == "completed"
