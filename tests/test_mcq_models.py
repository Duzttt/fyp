import os

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

from django_app.models import MCQAttempt, MCQQuiz  # noqa: E402


@pytest.fixture(autouse=True)
def cleanup():
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
            }
        ],
        "document_names": "lecture1.pdf, lecture2.pdf",
        "difficulty": "mixed",
        "question_count": 1,
        "llm_provider": "local_llm",
    }
    defaults.update(overrides)
    return MCQQuiz.objects.create(**defaults)


def test_mcq_quiz_create_and_defaults():
    quiz = _make_quiz()
    assert quiz.questions[0]["correct_answer"] == "B"
    assert quiz.difficulty == "mixed"
    assert quiz.question_count == 1
    assert quiz.llm_provider == "local_llm"
    assert quiz.created_at is not None
    assert str(quiz).startswith("MCQQuiz #")


def test_mcq_quiz_get_document_names():
    quiz = _make_quiz()
    assert quiz.get_document_names() == ["lecture1.pdf", "lecture2.pdf"]


def test_mcq_quiz_get_document_names_empty():
    quiz = _make_quiz(document_names="")
    assert quiz.get_document_names() == []


def test_mcq_attempt_creation():
    quiz = _make_quiz()
    attempt = MCQAttempt.objects.create(
        quiz=quiz,
        answers=[{"question_id": "q1", "selected": "B"}],
        score=1,
        total=1,
    )
    assert attempt.quiz_id == quiz.id
    assert attempt.score == 1
    assert "1/1" in str(attempt)


def test_attempt_cascade_delete():
    quiz = _make_quiz()
    MCQAttempt.objects.create(quiz=quiz, answers=[], score=0, total=1)
    assert MCQAttempt.objects.filter(quiz_id=quiz.id).count() == 1
    quiz.delete()
    assert MCQAttempt.objects.filter(quiz_id=quiz.id).count() == 0


def test_best_score_with_attempts():
    quiz = _make_quiz(question_count=3)
    MCQAttempt.objects.create(quiz=quiz, answers=[], score=2, total=3)
    MCQAttempt.objects.create(quiz=quiz, answers=[], score=3, total=3)
    assert quiz.best_score() == 100.0


def test_best_score_partial():
    quiz = _make_quiz(question_count=3)
    MCQAttempt.objects.create(quiz=quiz, answers=[], score=1, total=3)
    assert quiz.best_score() == 33.3


def test_best_score_no_attempts():
    quiz = _make_quiz()
    assert quiz.best_score() is None
