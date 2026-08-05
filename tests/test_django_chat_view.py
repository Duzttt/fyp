"""Tests for the primary chat endpoint."""

import json

import pytest
import requests
from django.test import Client


@pytest.fixture
def client() -> Client:
    return Client()


def test_ask_chat_success(client: Client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "django_app.views.rag.retrieve_with_faiss",
        lambda query, top_k=3, source_filter=None, similarity_threshold=0.6, reranker_enabled=False: [
            {"text": "trend one", "source": "Intelligent_Agent.pdf", "page": 7},
            {"text": "trend two", "source": "Intelligent_Agent.pdf", "page": 8},
        ],
    )
    monkeypatch.setattr(
        "django_app.views.rag.generate",
        lambda **kwargs: ("根据资料，这五个趋势是 ...", None, 1),
    )

    response = client.post(
        "/api/chat",
        data=json.dumps({"query": "What are the five trends?"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"].startswith("根据资料")
    assert data["sources"] == ["Intelligent_Agent.pdf"]
    assert len(data["source_snippets"]) == 2


def test_ask_chat_timeout(client: Client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "django_app.views.rag.retrieve_with_faiss",
        lambda query, top_k=3, source_filter=None, similarity_threshold=0.6, reranker_enabled=False: [
            {"text": "trend one", "source": "Intelligent_Agent.pdf", "page": 7}
        ],
    )

    def raise_timeout(**kwargs):
        raise requests.Timeout("timeout")

    monkeypatch.setattr(
        "django_app.views.rag.generate",
        raise_timeout,
    )

    response = client.post(
        "/api/chat",
        data=json.dumps({"query": "test"}),
        content_type="application/json",
    )

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


def test_ask_chat_missing_query(client: Client):
    response = client.post(
        "/api/chat",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Query cannot be empty"
