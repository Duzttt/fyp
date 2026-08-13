import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

import django

django.setup()

import importlib
import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.apps import apps as django_apps
from django.test import TestCase
from django.utils import timezone

from django_app.models import SummaryJob

HISTORY_PAYLOAD = [
    {
        "id": "summary_123",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "documents": ["lecture.pdf"],
        "summary": "# Old summary\nSome text.",
        "citations": [{"point": "x", "page": 3}],
        "config": {"length": "short"},
    },
    {
        "id": "summary_456",
        "timestamp": "2026-01-02T00:00:00+00:00",
        "documents": ["a.pdf", "b.pdf"],
        "summary": "Combined text.",
        "config": {"length": "medium"},
    },
]


def _write_history_file(tmp_dir: str, payload: object) -> Path:
    path = Path(tmp_dir) / "summary_history.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _ticking_now():
    """Fake timezone.now() advancing 1 microsecond per call.

    SummaryJob.created_at is auto_now_add; rapid sequential creates can
    land in the same clock bucket, making order_by("created_at")
    nondeterministic. A ticking clock keeps insertion order stable.
    """
    base = timezone.now()

    def fake_now():
        nonlocal base
        value = base
        base = base + timedelta(microseconds=1)
        return value

    return fake_now


class TestLegacyMigration(TestCase):
    def setUp(self):
        SummaryJob.objects.all().delete()

    def test_migration_imports_entries(self):
        m = importlib.import_module(
            "django_app.migrations.0007_migrate_legacy_summary_history"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            history_file = _write_history_file(tmp_dir, HISTORY_PAYLOAD)
            with patch("django.utils.timezone.now", _ticking_now()):
                with patch.object(m, "SUMMARY_HISTORY_FILE", history_file):
                    m.migrate_summary_history(django_apps, None)

            jobs = list(SummaryJob.objects.order_by("created_at"))
            assert len(jobs) == 2
            assert jobs[0].document_id == "lecture.pdf"
            assert jobs[0].status == "completed"
            assert jobs[0].result_markdown == "# Old summary\nSome text."
            assert jobs[0].citations == [{"point": "x", "page": 3}]
            assert jobs[0].config == {
                "length": "short",
                "legacy_documents": ["lecture.pdf"],
            }
            assert jobs[1].config["legacy_documents"] == ["a.pdf", "b.pdf"]

    def test_migration_skips_malformed(self):
        m = importlib.import_module(
            "django_app.migrations.0007_migrate_legacy_summary_history"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_file = Path(tmp_dir) / "bad.json"
            bad_file.write_text(
                json.dumps([{"id": "broken", "documents": "not-a-list"}]),
                encoding="utf-8",
            )
            with patch.object(m, "SUMMARY_HISTORY_FILE", bad_file):
                m.migrate_summary_history(django_apps, None)
            assert SummaryJob.objects.count() == 0

    def test_migration_missing_file_is_noop(self):
        m = importlib.import_module(
            "django_app.migrations.0007_migrate_legacy_summary_history"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(
                m, "SUMMARY_HISTORY_FILE", Path(tmp_dir) / "does_not_exist.json"
            ):
                m.migrate_summary_history(django_apps, None)
            assert SummaryJob.objects.count() == 0
