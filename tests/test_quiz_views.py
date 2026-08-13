"""View tests for quiz API endpoints."""

import json

import pytest
from django.test import Client

from app.services.quiz_generator import QuizGenerationError

QUESTIONS = [
    {
        "type": "single",
        "text": "What does RAG stand for?",
        "options": [
            "Retrieval-Augmented Generation",
            "Random Access Gateway",
            "Rapid Answer Generator",
            "None of the above",
        ],
        "answer": [0],
        "explanation": "RAG stands for Retrieval-Augmented Generation.",
    },
    {
        "type": "multiple",
        "text": "Which components are part of RAG?",
        "options": ["Retriever", "Generator", "Battery", "Water pump"],
        "answer": [0, 1],
        "explanation": "RAG has a retriever and a generator.",
    },
]

VALID_CONFIG = {
    "num_questions": 2,
    "difficulty": "medium",
    "question_types": {"single": 1, "multiple": 1},
}


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def quiz_history_file(tmp_path, monkeypatch):
    path = tmp_path / "quiz_history.json"
    monkeypatch.setattr("django_app.views.quiz.QUIZ_HISTORY_FILE", path)
    return path


@pytest.fixture
def mock_docs(monkeypatch):
    monkeypatch.setattr(
        "django_app.views.quiz._get_document_text",
        lambda filename: "RAG combines retrieval with generation.",
    )


@pytest.fixture
def mock_questions(monkeypatch):
    def fake_generate(self, documents, config):
        return {"questions": QUESTIONS, "config": config}

    monkeypatch.setattr(
        "app.services.quiz_generator.QuizGenerator.generate_quiz", fake_generate
    )


def _generate_payload():
    return {"document_ids": ["lec1.pdf"], "config": VALID_CONFIG}


def _seed_quiz(quiz_history_file, quiz_id="quiz_1"):
    entry = {
        "id": quiz_id,
        "timestamp": "2026-08-13T00:00:00+00:00",
        "documents": ["lec1.pdf"],
        "config": VALID_CONFIG,
        "questions": QUESTIONS,
        "attempts": [],
    }
    quiz_history_file.write_text(json.dumps([entry]), encoding="utf-8")
    return entry


def test_generate_quiz_success(client, mock_docs, mock_questions, quiz_history_file):
    resp = client.post(
        "/api/quiz/generate",
        data=json.dumps(_generate_payload()),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["quiz_id"].startswith("quiz_")
    assert body["document_count"] == 1
    assert len(body["questions"]) == 2


def test_generate_quiz_strips_answers_in_response(
    client, mock_docs, mock_questions, quiz_history_file
):
    resp = client.post(
        "/api/quiz/generate",
        data=json.dumps(_generate_payload()),
        content_type="application/json",
    )
    body = resp.json()
    for question in body["questions"]:
        assert "answer" not in question
        assert "explanation" not in question
        assert "type" in question
        assert "text" in question
        assert "options" in question


def test_generate_quiz_keeps_answers_in_history_file(
    client, mock_docs, mock_questions, quiz_history_file
):
    client.post(
        "/api/quiz/generate",
        data=json.dumps(_generate_payload()),
        content_type="application/json",
    )
    history = json.loads(quiz_history_file.read_text(encoding="utf-8"))
    assert len(history) == 1
    assert history[0]["questions"][0]["answer"] == [0]
    assert history[0]["attempts"] == []


def test_generate_quiz_requires_documents(client, mock_docs, quiz_history_file):
    resp = client.post(
        "/api/quiz/generate",
        data=json.dumps({"document_ids": [], "config": VALID_CONFIG}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_generate_quiz_document_ids_must_be_list(client, quiz_history_file):
    resp = client.post(
        "/api/quiz/generate",
        data=json.dumps({"document_ids": "lec1.pdf", "config": VALID_CONFIG}),
        content_type="application/json",
    )
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "bad_config",
    [
        {"num_questions": 0},
        {"num_questions": 21},
        {"num_questions": "abc"},
        {"difficulty": "impossible"},
        {"num_questions": 3, "question_types": {"single": 1, "multiple": 1}},
        {"question_types": {"essay": 5}},
        {"question_types": "not-an-object"},
    ],
)
def test_generate_quiz_invalid_config(client, mock_docs, quiz_history_file, bad_config):
    payload = {"document_ids": ["lec1.pdf"], "config": bad_config}
    resp = client.post(
        "/api/quiz/generate",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_generate_quiz_no_valid_documents(client, monkeypatch, quiz_history_file):
    monkeypatch.setattr(
        "django_app.views.quiz._get_document_text", lambda filename: None
    )
    resp = client.post(
        "/api/quiz/generate",
        data=json.dumps(_generate_payload()),
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_generate_quiz_llm_error(client, mock_docs, monkeypatch, quiz_history_file):
    def fake_generate(self, documents, config):
        raise QuizGenerationError("boom")

    monkeypatch.setattr(
        "app.services.quiz_generator.QuizGenerator.generate_quiz", fake_generate
    )
    resp = client.post(
        "/api/quiz/generate",
        data=json.dumps(_generate_payload()),
        content_type="application/json",
    )
    assert resp.status_code == 500


def test_submit_quiz_all_correct(client, quiz_history_file):
    _seed_quiz(quiz_history_file)
    resp = client.post(
        "/api/quiz/submit",
        data=json.dumps({"quiz_id": "quiz_1", "answers": {"0": [0], "1": [0, 1]}}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["score"] == 2
    assert body["total"] == 2
    assert body["per_question"][0]["correct"] is True
    assert body["per_question"][1]["correct"] is True
    assert body["per_question"][0]["explanation"]
    assert body["per_question"][1]["correct_answers"] == [0, 1]


def test_submit_quiz_partial_multi_is_wrong(client, quiz_history_file):
    _seed_quiz(quiz_history_file)
    resp = client.post(
        "/api/quiz/submit",
        data=json.dumps({"quiz_id": "quiz_1", "answers": {"0": [0], "1": [0]}}),
        content_type="application/json",
    )
    body = resp.json()
    assert body["score"] == 1
    assert body["per_question"][1]["correct"] is False
    assert body["per_question"][1]["your_answers"] == [0]


def test_submit_quiz_records_attempt(client, quiz_history_file):
    _seed_quiz(quiz_history_file)
    client.post(
        "/api/quiz/submit",
        data=json.dumps({"quiz_id": "quiz_1", "answers": {"0": [0], "1": [0, 1]}}),
        content_type="application/json",
    )
    history = json.loads(quiz_history_file.read_text(encoding="utf-8"))
    assert len(history[0]["attempts"]) == 1
    assert history[0]["attempts"][0]["score"] == 2


def test_submit_quiz_unknown_quiz_id(client, quiz_history_file):
    _seed_quiz(quiz_history_file)
    resp = client.post(
        "/api/quiz/submit",
        data=json.dumps({"quiz_id": "quiz_missing", "answers": {"0": [0]}}),
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_submit_quiz_requires_quiz_id(client, quiz_history_file):
    resp = client.post(
        "/api/quiz/submit",
        data=json.dumps({"answers": {"0": [0]}}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_submit_quiz_answers_must_be_object(client, quiz_history_file):
    _seed_quiz(quiz_history_file)
    resp = client.post(
        "/api/quiz/submit",
        data=json.dumps({"quiz_id": "quiz_1", "answers": [0]}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_get_quiz_history_strips_answers(client, quiz_history_file):
    _seed_quiz(quiz_history_file)
    resp = client.get("/api/quiz/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["history"]) == 1
    entry = body["history"][0]
    assert entry["id"] == "quiz_1"
    assert len(entry["questions"]) == 2
    for question in entry["questions"]:
        assert "answer" not in question
        assert "explanation" not in question
    assert entry["attempts"] == []


def test_get_quiz_history_empty(client, quiz_history_file):
    resp = client.get("/api/quiz/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"history": [], "total": 0}


def test_delete_quiz_success(client, quiz_history_file):
    _seed_quiz(quiz_history_file)
    resp = client.post("/api/quiz/quiz_1/delete")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    history = json.loads(quiz_history_file.read_text(encoding="utf-8"))
    assert history == []


def test_delete_quiz_unknown(client, quiz_history_file):
    _seed_quiz(quiz_history_file)
    resp = client.post("/api/quiz/quiz_missing/delete")
    assert resp.status_code == 404
