"""
Quiz generation and grading API views.

Endpoints:
- POST /api/quiz/generate      -> generate quiz from selected documents
- POST /api/quiz/submit        -> grade submitted answers
- GET  /api/quiz/history       -> list recent quizzes (answers stripped)
- POST /api/quiz/<id>/delete   -> delete a quiz from history
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings

from django_app.views.helpers import _error_response, _get_json_body

QUIZ_HISTORY_FILE = Path(__file__).resolve().parents[2] / "data" / "quiz_history.json"
MAX_HISTORY_ENTRIES = 50
DEFAULT_QUESTION_COUNT = 5
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_QUESTION_TYPES = {"single", "multiple"}


def _load_quiz_history() -> List[Dict[str, Any]]:
    if not QUIZ_HISTORY_FILE.exists():
        return []

    try:
        with QUIZ_HISTORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except (OSError, json.JSONDecodeError):
        pass

    return []


def _save_quiz_history(history: List[Dict[str, Any]]) -> None:
    QUIZ_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with QUIZ_HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def _get_document_text(filename: str) -> Optional[str]:
    from app.services.runtime_embedding import load_runtime_embedding_settings
    from app.services.vector_store import VectorStore

    try:
        rt = load_runtime_embedding_settings()
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=rt["embedding_dim"],
        )

        doc_chunks = []
        for chunk in vector_store.chunks:
            chunk_source = str(chunk.get("source", ""))
            if filename in chunk_source or chunk_source.endswith(filename):
                doc_chunks.append(chunk)

        if not doc_chunks:
            return None

        doc_chunks.sort(key=lambda c: c.get("page", 0) or 0)
        return " ".join([str(c.get("text", "")) for c in doc_chunks])
    except Exception:
        return None


def _normalize_config(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("config must be an object")

    num_questions = raw.get("num_questions", DEFAULT_QUESTION_COUNT)
    try:
        num_questions = int(num_questions)
    except (TypeError, ValueError):
        raise ValueError("num_questions must be an integer")
    if not 1 <= num_questions <= 20:
        raise ValueError("num_questions must be between 1 and 20")

    difficulty = str(raw.get("difficulty", "medium")).strip().lower()
    if difficulty not in VALID_DIFFICULTIES:
        raise ValueError(
            f"difficulty must be one of: {', '.join(sorted(VALID_DIFFICULTIES))}"
        )

    question_types = raw.get("question_types")
    if question_types is None:
        normalized_types = {"single": num_questions, "multiple": 0}
    else:
        if not isinstance(question_types, dict):
            raise ValueError("question_types must be an object")
        for key in question_types:
            if key not in VALID_QUESTION_TYPES:
                raise ValueError(
                    "question_types keys must be one of: "
                    f"{', '.join(sorted(VALID_QUESTION_TYPES))}"
                )
        try:
            single = int(question_types.get("single", 0))
            multiple = int(question_types.get("multiple", 0))
        except (TypeError, ValueError):
            raise ValueError("question_types values must be integers")
        if single < 0 or multiple < 0:
            raise ValueError("question_types values must be non-negative")
        if single + multiple != num_questions:
            raise ValueError("question_types values must sum to num_questions")
        normalized_types = {"single": single, "multiple": multiple}

    return {
        "num_questions": num_questions,
        "difficulty": difficulty,
        "question_types": normalized_types,
    }


def _strip_answers(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    stripped = []
    for question in questions:
        item = {
            key: value
            for key, value in question.items()
            if key not in ("answer", "explanation")
        }
        stripped.append(item)
    return stripped


@csrf_exempt
@require_http_methods(["POST"])
def generate_quiz(request: HttpRequest) -> JsonResponse:
    from app.services.quiz_generator import QuizGenerationError, QuizGenerator

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    document_ids = payload.get("document_ids", [])
    if not isinstance(document_ids, list) or not document_ids:
        return _error_response("document_ids must be a non-empty list", status=400)

    try:
        config = _normalize_config(payload.get("config") or {})
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    documents = []
    for doc_id in document_ids:
        text = _get_document_text(str(doc_id))
        if text:
            documents.append({"name": str(doc_id), "text": text})

    if not documents:
        return _error_response("No valid documents found", status=404)

    try:
        generator = QuizGenerator()
        result = generator.generate_quiz(documents, config)
    except QuizGenerationError as exc:
        return _error_response(str(exc), status=500)
    except Exception as exc:
        return _error_response(f"Failed to generate quiz: {str(exc)}", status=500)

    questions = result.get("questions") if isinstance(result, dict) else None
    if not isinstance(questions, list):
        return _error_response("Quiz generation returned invalid data", status=500)

    quiz_id = f"quiz_{int(time.time() * 1000)}"
    entry = {
        "id": quiz_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "documents": [doc["name"] for doc in documents],
        "config": config,
        "questions": questions,
        "attempts": [],
    }

    history = _load_quiz_history()
    history.insert(0, entry)
    if len(history) > MAX_HISTORY_ENTRIES:
        history = history[:MAX_HISTORY_ENTRIES]
    _save_quiz_history(history)

    return JsonResponse(
        {
            "success": True,
            "quiz_id": quiz_id,
            "questions": _strip_answers(questions),
            "config": config,
            "document_count": len(documents),
            "documents": [doc["name"] for doc in documents],
        }
    )


def _grade_quiz(quiz: Dict[str, Any], answers: Dict[str, Any]) -> Dict[str, Any]:
    questions = quiz.get("questions", [])
    per_question = []
    score = 0

    for index, question in enumerate(questions):
        correct_answers = sorted(int(a) for a in question.get("answer", []))
        user_answers = answers.get(str(index), [])
        if not isinstance(user_answers, list):
            user_answers = [user_answers]
        try:
            normalized = sorted(int(a) for a in user_answers)
        except (TypeError, ValueError):
            normalized = []
        correct = normalized == correct_answers
        if correct:
            score += 1
        per_question.append(
            {
                "index": index,
                "correct": correct,
                "correct_answers": correct_answers,
                "your_answers": normalized,
                "explanation": question.get("explanation", ""),
            }
        )

    return {
        "score": score,
        "total": len(questions),
        "per_question": per_question,
    }


@csrf_exempt
@require_http_methods(["POST"])
def submit_quiz(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    quiz_id = str(payload.get("quiz_id", "")).strip()
    answers = payload.get("answers")

    if not quiz_id:
        return _error_response("quiz_id is required", status=400)
    if not isinstance(answers, dict):
        return _error_response("answers must be an object", status=400)

    history = _load_quiz_history()
    quiz = None
    for entry in history:
        if entry.get("id") == quiz_id:
            quiz = entry
            break

    if quiz is None:
        return _error_response("Quiz not found", status=404)

    result = _grade_quiz(quiz, answers)

    attempt = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "answers": {str(key): value for key, value in answers.items()},
        "score": result["score"],
        "total": result["total"],
    }
    quiz.setdefault("attempts", []).append(attempt)
    _save_quiz_history(history)

    return JsonResponse({"success": True, **result})


@require_http_methods(["GET"])
def get_quiz_history(request: HttpRequest) -> JsonResponse:
    try:
        try:
            limit = int(request.GET.get("limit", 20))
        except (TypeError, ValueError):
            limit = 20
        limit = max(0, min(limit, 50))

        history = _load_quiz_history()
        result = []
        for entry in history[:limit]:
            item = {key: value for key, value in entry.items() if key != "questions"}
            item["questions"] = _strip_answers(entry.get("questions", []))
            result.append(item)

        return JsonResponse({"history": result, "total": len(history)})
    except Exception as exc:
        return _error_response(f"Failed to load quiz history: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_quiz(request: HttpRequest, quiz_id: str) -> JsonResponse:
    try:
        history = _load_quiz_history()
        new_history = [entry for entry in history if entry.get("id") != quiz_id]

        if len(new_history) == len(history):
            return _error_response("Quiz not found", status=404)

        _save_quiz_history(new_history)
        return JsonResponse({"success": True, "message": "Quiz deleted"})
    except Exception as exc:
        return _error_response(f"Failed to delete quiz: {str(exc)}", status=500)
