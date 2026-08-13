import json
import os

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

from django.test import Client  # noqa: E402

from app.services.mcq_generator import MCQGenerationError  # noqa: E402
from django_app.models import MCQAttempt, MCQQuiz  # noqa: E402


@pytest.fixture
def client():
    return Client()


class FakeMCQService:
    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider or "local_llm"

    def generate_mcqs(
        self, documents, num_questions=5, difficulty="mixed", timeout_seconds=60
    ):
        return [
            {
                "question": f"Question {i + 1}?",
                "options": {
                    "A": "Option A",
                    "B": "Option B",
                    "C": "Option C",
                    "D": "Option D",
                },
                "correct_answer": "A",
                "explanation": f"Explanation {i + 1}",
                "difficulty": "medium",
                "source_doc": "lecture1.pdf",
            }
            for i in range(num_questions)
        ]


class FailingMCQService:
    def __init__(self, llm_provider=None):
        self.llm_provider = "local_llm"

    def generate_mcqs(self, *args, **kwargs):
        raise MCQGenerationError("LLM unavailable")


@pytest.fixture(autouse=True)
def patch_deps(monkeypatch):
    monkeypatch.setattr(
        "django_app.views.mcq._get_document_text",
        lambda filename: "Sample lecture text about RAG.",
    )
    monkeypatch.setattr(
        "app.services.mcq_generator.MCQGeneratorService", FakeMCQService
    )
    yield
    MCQAttempt.objects.all().delete()
    MCQQuiz.objects.all().delete()


def _make_quiz(**overrides):
    defaults = {
        "questions": [
            {
                "id": "q1",
                "question": "What is RAG?",
                "options": {"A": "A1", "B": "B1", "C": "C1", "D": "D1"},
                "correct_answer": "B",
                "explanation": "Because.",
                "difficulty": "easy",
                "source_doc": "lecture1.pdf",
            },
            {
                "id": "q2",
                "question": "What is BM25?",
                "options": {"A": "A2", "B": "B2", "C": "C2", "D": "D2"},
                "correct_answer": "A",
                "explanation": "It ranks.",
                "difficulty": "medium",
                "source_doc": "lecture1.pdf",
            },
        ],
        "document_names": "lecture1.pdf",
        "difficulty": "mixed",
        "question_count": 2,
        "llm_provider": "local_llm",
    }
    defaults.update(overrides)
    return MCQQuiz.objects.create(**defaults)


def _post(client, path, payload):
    return client.post(path, data=json.dumps(payload), content_type="application/json")


def test_generate_mcq_success(client):
    response = _post(
        client,
        "/api/mcq/generate",
        {
            "document_ids": ["lecture1.pdf"],
            "num_questions": 3,
            "difficulty": "mixed",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["quiz_id"]
    assert len(data["questions"]) == 3
    q1 = data["questions"][0]
    assert q1["id"] == "q1"
    assert set(q1["options"].keys()) == {"A", "B", "C", "D"}
    assert "correct_answer" not in q1
    assert "explanation" not in q1

    quiz = MCQQuiz.objects.get(pk=data["quiz_id"])
    assert quiz.questions[0]["correct_answer"] == "A"
    assert quiz.question_count == 3


def test_generate_mcq_missing_document_ids(client):
    response = _post(client, "/api/mcq/generate", {})
    assert response.status_code == 400
    assert "detail" in response.json()


def test_generate_mcq_invalid_difficulty(client):
    response = _post(
        client,
        "/api/mcq/generate",
        {"document_ids": ["a.pdf"], "difficulty": "impossible"},
    )
    assert response.status_code == 400


def test_generate_mcq_invalid_num_questions(client):
    response = _post(
        client,
        "/api/mcq/generate",
        {"document_ids": ["a.pdf"], "num_questions": "abc"},
    )
    assert response.status_code == 400


def test_generate_mcq_no_valid_documents(client, monkeypatch):
    monkeypatch.setattr(
        "django_app.views.mcq._get_document_text", lambda filename: None
    )
    response = _post(client, "/api/mcq/generate", {"document_ids": ["missing.pdf"]})
    assert response.status_code == 404


def test_generate_mcq_service_error(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.mcq_generator.MCQGeneratorService", FailingMCQService
    )
    response = _post(client, "/api/mcq/generate", {"document_ids": ["a.pdf"]})
    assert response.status_code == 500


def test_get_mcq_success(client):
    quiz = _make_quiz()
    response = client.get(f"/api/mcq/{quiz.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["questions"]) == 2
    assert "correct_answer" not in data["questions"][0]


def test_get_mcq_not_found(client):
    response = client.get("/api/mcq/999999")
    assert response.status_code == 404


def test_submit_attempt_all_correct(client):
    quiz = _make_quiz()
    response = _post(
        client,
        f"/api/mcq/{quiz.id}/attempt",
        {
            "answers": [
                {"question_id": "q1", "selected": "B"},
                {"question_id": "q2", "selected": "A"},
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 2
    assert data["total"] == 2
    assert data["percentage"] == 100.0
    assert all(r["is_correct"] for r in data["results"])
    assert data["results"][0]["explanation"] == "Because."
    assert MCQAttempt.objects.filter(quiz=quiz).count() == 1


def test_submit_attempt_partial(client):
    quiz = _make_quiz()
    response = _post(
        client,
        f"/api/mcq/{quiz.id}/attempt",
        {
            "answers": [
                {"question_id": "q1", "selected": "B"},
                {"question_id": "q2", "selected": "B"},
            ]
        },
    )
    data = response.json()
    assert data["score"] == 1
    assert data["percentage"] == 50.0
    assert [r["is_correct"] for r in data["results"]] == [True, False]


def test_submit_attempt_incomplete_answers(client):
    quiz = _make_quiz()
    response = _post(
        client,
        f"/api/mcq/{quiz.id}/attempt",
        {"answers": [{"question_id": "q1", "selected": "B"}]},
    )
    assert response.status_code == 400


def test_submit_attempt_invalid_selected(client):
    quiz = _make_quiz()
    response = _post(
        client,
        f"/api/mcq/{quiz.id}/attempt",
        {
            "answers": [
                {"question_id": "q1", "selected": "X"},
                {"question_id": "q2", "selected": "A"},
            ]
        },
    )
    assert response.status_code == 400


def test_submit_attempt_unknown_question_id(client):
    quiz = _make_quiz()
    response = _post(
        client,
        f"/api/mcq/{quiz.id}/attempt",
        {
            "answers": [
                {"question_id": "q9", "selected": "A"},
                {"question_id": "q2", "selected": "A"},
            ]
        },
    )
    assert response.status_code == 400


def test_submit_attempt_quiz_not_found(client):
    response = _post(client, "/api/mcq/999999/attempt", {"answers": []})
    assert response.status_code == 404


def test_get_history(client):
    quiz = _make_quiz()
    MCQAttempt.objects.create(quiz=quiz, answers=[], score=1, total=2)
    _make_quiz(
        document_names="lecture2.pdf",
        difficulty="easy",
        question_count=1,
    )
    response = client.get("/api/mcq/history?limit=20")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["quizzes"]) == 2
    newest = data["quizzes"][0]
    assert newest["question_count"] == 1
    assert newest["difficulty"] == "easy"
    older = data["quizzes"][1]
    assert older["best_score"] == 50.0


def test_delete_quiz(client):
    quiz = _make_quiz()
    MCQAttempt.objects.create(quiz=quiz, answers=[], score=0, total=2)
    response = client.delete(f"/api/mcq/{quiz.id}")
    assert response.status_code == 200
    assert MCQQuiz.objects.filter(pk=quiz.id).count() == 0
    assert MCQAttempt.objects.filter(quiz_id=quiz.id).count() == 0


def test_delete_quiz_not_found(client):
    response = client.delete("/api/mcq/999999")
    assert response.status_code == 404


def test_mcq_urls_resolve():
    from django.urls import resolve

    import django_app.views.mcq as mcq_views

    cases = {
        "/api/mcq/generate": mcq_views.generate_mcq,
        "/api/mcq/history": mcq_views.get_mcq_history,
        "/api/mcq/5": mcq_views.get_mcq,
        "/api/mcq/5/attempt": mcq_views.submit_mcq_attempt,
        "/api/mcq/5/delete": mcq_views.delete_mcq,
    }
    for path, view in cases.items():
        assert resolve(path).func == view, f"unresolved: {path}"
