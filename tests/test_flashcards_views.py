"""View tests for flashcard API endpoints."""

import json

import pytest
from django.test import Client

from app.services.flashcard_generator import FlashcardGenerationError

CARDS = [
    {
        "front": "What does RAG stand for?",
        "back": "Retrieval-Augmented Generation.",
        "hint": "Three words.",
        "tags": ["rag"],
    },
    {
        "front": "Name one component of a RAG pipeline.",
        "back": "A retriever.",
        "hint": "It fetches passages.",
        "tags": ["architecture"],
    },
]

VALID_CONFIG = {"num_cards": 2, "topic": ""}


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def flashcards_history_file(tmp_path, monkeypatch):
    path = tmp_path / "flashcards_history.json"
    monkeypatch.setattr("django_app.views.flashcards.FLASHCARDS_HISTORY_FILE", path)
    return path


@pytest.fixture
def mock_docs(monkeypatch):
    monkeypatch.setattr(
        "django_app.views.flashcards._get_document_text",
        lambda filename: "RAG combines retrieval with generation.",
    )


@pytest.fixture
def mock_cards(monkeypatch):
    def fake_generate(self, documents, config):
        return {"cards": CARDS, "config": config}

    monkeypatch.setattr(
        "app.services.flashcard_generator.FlashcardGenerator.generate", fake_generate
    )


def _generate_payload():
    return {"document_ids": ["lec1.pdf"], "config": VALID_CONFIG}


def _seed_deck(flashcards_history_file, deck_id="deck_1"):
    entry = {
        "id": deck_id,
        "timestamp": "2026-08-13T00:00:00+00:00",
        "documents": ["lec1.pdf"],
        "config": VALID_CONFIG,
        "cards": CARDS,
    }
    flashcards_history_file.write_text(json.dumps([entry]), encoding="utf-8")
    return entry


def test_generate_flashcards_success(
    client, mock_docs, mock_cards, flashcards_history_file
):
    resp = client.post(
        "/api/flashcards/generate",
        data=json.dumps(_generate_payload()),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["deck_id"].startswith("deck_")
    assert body["document_count"] == 1
    assert len(body["cards"]) == 2


def test_generate_flashcards_persists_history(
    client, mock_docs, mock_cards, flashcards_history_file
):
    client.post(
        "/api/flashcards/generate",
        data=json.dumps(_generate_payload()),
        content_type="application/json",
    )
    history = json.loads(flashcards_history_file.read_text(encoding="utf-8"))
    assert len(history) == 1
    assert history[0]["cards"][0]["back"] == CARDS[0]["back"]


def test_generate_flashcards_requires_documents(
    client, mock_docs, flashcards_history_file
):
    resp = client.post(
        "/api/flashcards/generate",
        data=json.dumps({"document_ids": [], "config": VALID_CONFIG}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_generate_flashcards_document_ids_must_be_list(client, flashcards_history_file):
    resp = client.post(
        "/api/flashcards/generate",
        data=json.dumps({"document_ids": "lec1.pdf", "config": VALID_CONFIG}),
        content_type="application/json",
    )
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "bad_config",
    [
        {"num_cards": 0},
        {"num_cards": 51},
        {"num_cards": "abc"},
        {"topic": "x" * 201},
        "not-an-object",
    ],
)
def test_generate_flashcards_invalid_config(
    client, mock_docs, flashcards_history_file, bad_config
):
    payload = {"document_ids": ["lec1.pdf"], "config": bad_config}
    resp = client.post(
        "/api/flashcards/generate",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_generate_flashcards_no_valid_documents(
    client, monkeypatch, flashcards_history_file
):
    monkeypatch.setattr(
        "django_app.views.flashcards._get_document_text", lambda filename: None
    )
    resp = client.post(
        "/api/flashcards/generate",
        data=json.dumps(_generate_payload()),
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_generate_flashcards_llm_error(
    client, mock_docs, monkeypatch, flashcards_history_file
):
    def fake_generate(self, documents, config):
        raise FlashcardGenerationError("boom")

    monkeypatch.setattr(
        "app.services.flashcard_generator.FlashcardGenerator.generate", fake_generate
    )
    resp = client.post(
        "/api/flashcards/generate",
        data=json.dumps(_generate_payload()),
        content_type="application/json",
    )
    assert resp.status_code == 500


def test_get_flashcards_history(client, flashcards_history_file):
    _seed_deck(flashcards_history_file)
    resp = client.get("/api/flashcards/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["history"]) == 1
    entry = body["history"][0]
    assert entry["id"] == "deck_1"
    assert entry["card_count"] == 2
    assert len(entry["cards"]) == 2


def test_get_flashcards_history_empty(client, flashcards_history_file):
    resp = client.get("/api/flashcards/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"history": [], "total": 0}


def test_delete_flashcards_success(client, flashcards_history_file):
    _seed_deck(flashcards_history_file)
    resp = client.post("/api/flashcards/deck_1/delete")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    history = json.loads(flashcards_history_file.read_text(encoding="utf-8"))
    assert history == []


def test_delete_flashcards_unknown(client, flashcards_history_file):
    _seed_deck(flashcards_history_file)
    resp = client.post("/api/flashcards/deck_missing/delete")
    assert resp.status_code == 404
