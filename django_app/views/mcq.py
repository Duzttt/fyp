from typing import Any, Dict, List, Optional

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings

from django_app.views.helpers import _error_response, _get_json_body

MAX_QUESTIONS = 20
VALID_DIFFICULTIES = {"mixed", "easy", "medium", "hard"}
DOC_CONTENT_LIMIT = 6000


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


def _add_question_ids(
    questions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Assign stable question ids (q1..qN) used by attempt submissions."""
    return [{**question, "id": f"q{idx + 1}"} for idx, question in enumerate(questions)]


def _public_question(question: Dict[str, Any]) -> Dict[str, Any]:
    """Strip correct_answer/explanation before sending to the client."""
    return {
        "id": question.get("id"),
        "question": question.get("question", ""),
        "options": question.get("options", {}),
        "difficulty": question.get("difficulty", "medium"),
        "source_doc": question.get("source_doc", ""),
    }


@csrf_exempt
@require_http_methods(["POST"])
def generate_mcq(request: HttpRequest) -> JsonResponse:
    from app.services.mcq_generator import (
        MCQGenerationError,
        MCQGeneratorService,
    )

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    document_ids = payload.get("document_ids", [])
    num_questions = payload.get("num_questions", 5)
    difficulty = str(payload.get("difficulty", "mixed")).strip().lower()

    if not isinstance(document_ids, list) or not document_ids:
        return _error_response("document_ids must be a non-empty list", status=400)
    try:
        num_questions = max(1, min(int(num_questions), MAX_QUESTIONS))
    except (TypeError, ValueError):
        return _error_response("num_questions must be an integer", status=400)
    if difficulty not in VALID_DIFFICULTIES:
        return _error_response(
            "difficulty must be one of mixed|easy|medium|hard", status=400
        )

    documents = []
    for doc_id in document_ids:
        text = _get_document_text(str(doc_id))
        if text:
            documents.append({"name": str(doc_id), "content": text[:DOC_CONTENT_LIMIT]})

    if not documents:
        return _error_response("No valid documents found in index", status=404)

    try:
        service = MCQGeneratorService()
        questions = service.generate_mcqs(documents, num_questions, difficulty)
    except MCQGenerationError as exc:
        return _error_response(f"MCQ generation failed: {exc}", status=500)
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to generate MCQs: {exc}", status=500)

    from django_app.models import MCQQuiz

    questions = _add_question_ids(questions)
    quiz = MCQQuiz.objects.create(
        questions=questions,
        document_names=", ".join(str(d) for d in document_ids),
        difficulty=difficulty,
        question_count=len(questions),
        llm_provider=service.llm_provider,
    )

    return JsonResponse(
        {
            "success": True,
            "quiz_id": quiz.id,
            "questions": [_public_question(q) for q in questions],
            "difficulty": difficulty,
            "document_count": len(documents),
            "documents": [str(d) for d in document_ids],
        }
    )


@csrf_exempt
@require_http_methods(["GET", "DELETE"])
def get_mcq(request: HttpRequest, quiz_id: int) -> JsonResponse:
    from django_app.models import MCQQuiz

    if request.method == "DELETE":
        return delete_mcq(request, quiz_id)

    quiz = MCQQuiz.objects.filter(pk=quiz_id).first()
    if not quiz:
        return _error_response("Quiz not found", status=404)

    return JsonResponse(
        {
            "success": True,
            "quiz_id": quiz.id,
            "questions": [_public_question(q) for q in quiz.questions],
            "difficulty": quiz.difficulty,
            "documents": quiz.get_document_names(),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def submit_mcq_attempt(request: HttpRequest, quiz_id: int) -> JsonResponse:
    from django_app.models import MCQAttempt, MCQQuiz

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    quiz = MCQQuiz.objects.filter(pk=quiz_id).first()
    if not quiz:
        return _error_response("Quiz not found", status=404)

    answers = payload.get("answers", [])
    questions = quiz.questions
    expected_ids = [q.get("id") for q in questions]

    if not isinstance(answers, list):
        return _error_response("answers must be a list", status=400)

    answer_map: Dict[str, str] = {}
    for item in answers:
        if not isinstance(item, dict):
            return _error_response("Each answer must be an object", status=400)
        qid = str(item.get("question_id", "")).strip()
        selected = str(item.get("selected", "")).strip().upper()
        if not qid or qid not in expected_ids:
            return _error_response(f"Unknown question_id: {qid!r}", status=400)
        if selected not in {"A", "B", "C", "D"}:
            return _error_response(f"selected must be A-D for {qid}", status=400)
        if qid in answer_map:
            return _error_response(f"Duplicate answer for {qid}", status=400)
        answer_map[qid] = selected

    if set(answer_map.keys()) != set(expected_ids):
        return _error_response("Answers must cover all quiz questions", status=400)

    results: List[Dict[str, Any]] = []
    score = 0
    for question in questions:
        qid = question["id"]
        selected = answer_map[qid]
        correct = question["correct_answer"]
        is_correct = selected == correct
        if is_correct:
            score += 1
        results.append(
            {
                "question_id": qid,
                "selected": selected,
                "correct_answer": correct,
                "explanation": question["explanation"],
                "is_correct": is_correct,
            }
        )

    total = len(questions)
    MCQAttempt.objects.create(
        quiz=quiz,
        answers=[
            {"question_id": qid, "selected": selected}
            for qid, selected in answer_map.items()
        ],
        score=score,
        total=total,
    )

    return JsonResponse(
        {
            "success": True,
            "score": score,
            "total": total,
            "percentage": round(score / total * 100, 1) if total else 0.0,
            "results": results,
        }
    )


@require_http_methods(["GET"])
def get_mcq_history(request: HttpRequest) -> JsonResponse:
    from django_app.models import MCQQuiz

    try:
        limit = int(request.GET.get("limit", 20))
    except (TypeError, ValueError):
        return _error_response("limit must be an integer", status=400)
    limit = min(max(1, limit), 50)

    quizzes = MCQQuiz.objects.all()[:limit]
    items = []
    for quiz in quizzes:
        items.append(
            {
                "id": quiz.id,
                "question_count": quiz.question_count,
                "difficulty": quiz.difficulty,
                "documents": quiz.get_document_names(),
                "created_at": quiz.created_at.isoformat(),
                "best_score": quiz.best_score(),
            }
        )

    return JsonResponse({"quizzes": items, "total": MCQQuiz.objects.count()})


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_mcq(request: HttpRequest, quiz_id: int) -> JsonResponse:
    from django_app.models import MCQQuiz

    quiz = MCQQuiz.objects.filter(pk=quiz_id).first()
    if not quiz:
        return _error_response("Quiz not found", status=404)

    quiz.delete()
    return JsonResponse({"success": True, "message": "Quiz deleted"})
