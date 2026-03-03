import os
from pathlib import Path

import django
import pytest
from django.test import Client, override_settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()


@pytest.fixture
def client() -> Client:
    return Client()


def test_list_documents_empty(client: Client, tmp_path: Path):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        response = client.get("/api/documents")

    assert response.status_code == 200
    data = response.json()
    assert data["files"] == []


def test_list_documents_returns_pdf_only(client: Client, tmp_path: Path):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        upload_dir = tmp_path / "data_source"
        upload_dir.mkdir(parents=True, exist_ok=True)
        (upload_dir / "note.pdf").write_bytes(b"%PDF-1.4 fake")
        (upload_dir / "ignore.txt").write_text("ignore me", encoding="utf-8")

        response = client.get("/api/documents")

    assert response.status_code == 200
    data = response.json()
    assert data["files"] == ["note.pdf"]
