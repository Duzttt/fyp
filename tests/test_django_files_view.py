import os
from pathlib import Path

import django
import pytest
from django.test import Client

from app.config import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()


@pytest.fixture
def client() -> Client:
    return Client()


def test_list_files_empty(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setattr(settings, "DOCUMENTS_PATH", str(tmp_path))

    response = client.get("/api/files")

    assert response.status_code == 200
    data = response.json()
    assert data["files"] == []


def test_list_files_returns_pdf_only(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setattr(settings, "DOCUMENTS_PATH", str(tmp_path))
    (tmp_path / "note.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "ignore.txt").write_text("ignore me", encoding="utf-8")

    response = client.get("/api/files")

    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 1
    assert data["files"][0]["name"] == "note.pdf"
