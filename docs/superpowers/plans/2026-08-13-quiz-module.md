# Quiz Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full-stack multiple-choice quiz module (LLM-generated questions, instant server-side grading, explanations, retake-wrong, JSON history) to the RAG lecture-note system.

**Architecture:** Mirrors the existing summary module exactly: `app/services/quiz_generator.py` (LLM generation, one call per quiz, answers+explanations stored server-side), `django_app/views/quiz.py` (4 REST endpoints + JSON-file history at `data/quiz_history.json`), Vue frontend (`quizStore.js` Pinia store, `QuizModal.vue`, `QuizViewer.vue`) wired into the existing Studio panel `quiz` tool.

**Tech Stack:** Python 3.9+ / Django views, `call_llm` provider routing (local_llm/gemini/openrouter), pytest + Django test client, Vue 3 `<script setup>` + Pinia + axios.

## Global Constraints

- Line length 88 (Black), 4-space indent, trailing commas in multi-line constructs; absolute imports; `ruff`/`black`/`mypy` must pass on changed files.
- No comments unless they document non-obvious intent (match existing files' docstring style).
- Endpoints registered twice in `django_backend/urls.py` (with and without trailing slash).
- All quiz endpoints `@csrf_exempt`; errors via `_error_response(detail, status)` from `django_app/views/helpers`; JSON bodies via `_get_json_body(request)`.
- History: `data/quiz_history.json`, max 50 entries, newest first, trim on save; history responses strip `answer` and `explanation` keys (anti-cheat).
- Config: `num_questions` 1–20 (default 5), `difficulty` in {easy, medium, hard} (default medium), `question_types` = `{"single": n, "multiple": m}` non-negative ints summing to `num_questions`; when absent default to all-single.
- Grading: multi-select requires exact full match (partial = wrong).
- LLM calls use `call_type="quiz"`.
- Tests in `tests/` using pytest (conftest.py already sets `DJANGO_SETTINGS_MODULE`); mock `call_llm` — never hit a real LLM or the real `data/quiz_history.json` (monkeypatch `QUIZ_HISTORY_FILE` to tmp_path).
- Frontend: no test framework — verify with `npm run build` (workdir `frontend`).
- Question object shape (stored): `{"type": "single"|"multiple", "text": str, "options": [str...], "answer": [int...], "explanation": str}`.

---

### Task 1: QuizGenerator service (TDD)

**Files:**
- Create: `app/services/quiz_generator.py`
- Test: `tests/test_quiz_generator.py`

**Interfaces:**
- Consumes: `call_llm(provider, model, call_type, messages, **kwargs)` from `app.services.llm_client`; `settings` from `app.config`; `load_runtime_llm_settings()` from `app.services.runtime_llm`.
- Produces: `class QuizGenerationError(Exception)`; `class QuizGenerator` with `generate_quiz(documents: List[Dict], config: Dict) -> Dict` returning `{"questions": [...], "config": config}`; retries once on parse/validation/count failure, raises `QuizGenerationError` after 2 attempts.

- [ ] **Step 1: Write the failing test**

Create `tests/test_quiz_generator.py`:

```python
"""Unit tests for the QuizGenerator service."""

import json

import pytest

from app.services.quiz_generator import QuizGenerationError, QuizGenerator

SINGLE_Q = {
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
}

MULTI_Q = {
    "type": "multiple",
    "text": "Which components are part of a RAG pipeline?",
    "options": ["Retriever", "Generator", "Battery", "Water pump"],
    "answer": [0, 1],
    "explanation": "A RAG pipeline has a retriever and a generator.",
}

DOCS = [{"name": "lec1.pdf", "text": "RAG combines retrieval with generation."}]


def _config(num, single, multiple, difficulty="medium"):
    return {
        "num_questions": num,
        "difficulty": difficulty,
        "question_types": {"single": single, "multiple": multiple},
    }


def _make_generator():
    return QuizGenerator(llm_provider="local_llm", model="test-model")


def _patch_llm(monkeypatch, responses):
    responses = list(responses)

    def fake_call_llm(**kwargs):
        return responses.pop(0)

    monkeypatch.setattr("app.services.quiz_generator.call_llm", fake_call_llm)
    return responses


def test_generate_quiz_parses_valid_json(monkeypatch):
    _patch_llm(monkeypatch, [json.dumps([SINGLE_Q, MULTI_Q, SINGLE_Q])])
    result = _make_generator().generate_quiz(DOCS, _config(3, 2, 1))
    assert len(result["questions"]) == 3
    assert result["questions"][0]["answer"] == [0]
    assert result["questions"][1]["answer"] == [0, 1]


def test_generate_quiz_retries_after_invalid_json(monkeypatch):
    responses = _patch_llm(
        monkeypatch, ["not json at all", json.dumps([SINGLE_Q, SINGLE_Q])]
    )
    result = _make_generator().generate_quiz(DOCS, _config(2, 2, 0))
    assert len(result["questions"]) == 2
    assert responses == []


def test_generate_quiz_raises_after_two_failures(monkeypatch):
    _patch_llm(monkeypatch, ["garbage", "still garbage"])
    with pytest.raises(QuizGenerationError):
        _make_generator().generate_quiz(DOCS, _config(1, 1, 0))


def test_generate_quiz_retries_on_count_mismatch(monkeypatch):
    responses = _patch_llm(
        monkeypatch, [json.dumps([SINGLE_Q]), json.dumps([SINGLE_Q, MULTI_Q])]
    )
    result = _make_generator().generate_quiz(DOCS, _config(2, 1, 1))
    assert len(result["questions"]) == 2
    assert responses == []


def test_generate_quiz_drops_questions_with_out_of_range_answer(monkeypatch):
    bad = {**SINGLE_Q, "answer": [9]}
    _patch_llm(monkeypatch, [json.dumps([SINGLE_Q, bad, MULTI_Q])])
    result = _make_generator().generate_quiz(DOCS, _config(2, 1, 1))
    assert len(result["questions"]) == 2
    assert all(q["type"] != "single" or q["answer"] == [0] for q in result["questions"])


def test_generate_quiz_parses_markdown_fenced_json(monkeypatch):
    payload = "```json\n" + json.dumps([SINGLE_Q]) + "\n```"
    _patch_llm(monkeypatch, [payload])
    result = _make_generator().generate_quiz(DOCS, _config(1, 1, 0))
    assert len(result["questions"]) == 1


def test_generate_quiz_accepts_dict_wrapped_questions(monkeypatch):
    _patch_llm(monkeypatch, [json.dumps({"questions": [SINGLE_Q]})])
    result = _make_generator().generate_quiz(DOCS, _config(1, 1, 0))
    assert len(result["questions"]) == 1


def test_generate_quiz_rejects_questions_with_fewer_than_two_options(monkeypatch):
    one_option = {**SINGLE_Q, "options": ["only one"]}
    _patch_llm(monkeypatch, [json.dumps([one_option, MULTI_Q])])
    result = _make_generator().generate_quiz(DOCS, _config(1, 0, 1))
    assert len(result["questions"]) == 1
    assert result["questions"][0]["type"] == "multiple"


def test_generate_quiz_rejects_questions_without_explanation(monkeypatch):
    no_explanation = {**SINGLE_Q, "explanation": ""}
    _patch_llm(monkeypatch, [json.dumps([no_explanation, SINGLE_Q])])
    result = _make_generator().generate_quiz(DOCS, _config(1, 1, 0))
    assert len(result["questions"]) == 1


def test_generate_quiz_raises_without_documents():
    with pytest.raises(QuizGenerationError):
        _make_generator().generate_quiz([], _config(1, 1, 0))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_quiz_generator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.quiz_generator'`

- [ ] **Step 3: Write the implementation**

Create `app/services/quiz_generator.py`:

```python
"""
Quiz Generator Service

Generates multiple-choice quiz questions (single- and multi-select)
from documents using the configured LLM.
"""

import json
import re
from typing import Any, Dict, List

from app.config import settings
from app.services.llm_client import call_llm

VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_QUESTION_TYPES = {"single", "multiple"}
MAX_GENERATION_ATTEMPTS = 2

DIFFICULTY_PROMPTS = {
    "easy": "basic recall of key facts and definitions from the content",
    "medium": "understanding and application of core concepts from the content",
    "hard": "analysis, synthesis, and distinguishing subtle differences between concepts",
}


class QuizGenerationError(Exception):
    """Exception raised for quiz generation errors."""


class QuizGenerator:
    """Quiz generation service using the configured LLM."""

    def __init__(self, llm_provider: str = None, model: str = None):
        from app.services.runtime_llm import load_runtime_llm_settings

        rt = load_runtime_llm_settings()
        self.llm_provider = llm_provider or rt["provider"] or settings.LLM_PROVIDER
        self.model = model or rt["model"] or settings.LOCAL_LLM_MODEL
        self.base_url = rt["base_url"] or settings.LOCAL_LLM_BASE_URL
        self.timeout = settings.LOCAL_LLM_TIMEOUT_SECONDS

    def _build_prompt(
        self, documents: List[Dict[str, Any]], config: Dict[str, Any]
    ) -> str:
        num_questions = int(config["num_questions"])
        difficulty = config["difficulty"]
        question_types = config["question_types"]
        single_count = int(question_types.get("single", 0))
        multiple_count = int(question_types.get("multiple", 0))

        doc_list = "\n\n".join(
            f"### Document: {doc['name']}\n{doc['text'][:5000]}"
            for doc in documents
        )

        return f"""Generate {num_questions} multiple-choice quiz questions based ONLY on the following document(s).

{doc_list}

Requirements:
- {single_count} single-choice question(s): exactly ONE correct option.
- {multiple_count} multiple-choice question(s): TWO OR MORE correct options.
- Difficulty: {DIFFICULTY_PROMPTS[difficulty]}.
- Each question has exactly 4 options with plausible distractors grounded in the content.
- Provide a concise explanation of the correct answer for every question.

Respond with ONLY a JSON array (no markdown fences, no extra text) in this exact format:
[
  {{"type": "single", "text": "Question text?", "options": ["A", "B", "C", "D"], "answer": [2], "explanation": "Why option index 2 is correct."}},
  {{"type": "multiple", "text": "Question text?", "options": ["A", "B", "C", "D"], "answer": [0, 3], "explanation": "Why options 0 and 3 are correct."}}
]"""

    def _build_messages(self, prompt: str) -> List[Dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are an exam question generator for lecture notes. "
                    "Generate accurate questions grounded in the provided content. "
                    "Output ONLY valid JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ]

    def _call_local_llm(self, prompt: str) -> str:
        try:
            messages = self._build_messages(prompt)
            result = call_llm(
                provider="local_llm",
                model=self.model,
                call_type="quiz",
                messages=messages,
                base_url=self.base_url,
                timeout=self.timeout,
            )
            return result[0] if isinstance(result, tuple) else str(result)
        except Exception as exc:
            raise QuizGenerationError(f"Failed to call local LLM: {str(exc)}") from exc

    def _call_gemini(self, prompt: str) -> str:
        try:
            api_key = settings.GEMINI_API_KEY
            if not api_key:
                raise QuizGenerationError("Gemini API key not configured")
            messages = self._build_messages(prompt)
            result = call_llm(
                provider="gemini",
                model=settings.GEMINI_MODEL,
                call_type="quiz",
                messages=messages,
                api_key=api_key,
                base_url=settings.GEMINI_BASE_URL,
                temperature=0.3,
                max_tokens=4096,
                response_format="json",
            )
            return result[0] if isinstance(result, tuple) else str(result)
        except QuizGenerationError:
            raise
        except Exception as exc:
            raise QuizGenerationError(f"Failed to call Gemini: {str(exc)}") from exc

    def _call_openrouter(self, prompt: str) -> str:
        try:
            api_key = settings.OPENROUTER_API_KEY
            if not api_key:
                raise QuizGenerationError("OpenRouter API key not configured")
            messages = self._build_messages(prompt)
            result = call_llm(
                provider="openrouter",
                model=settings.OPENROUTER_MODEL,
                call_type="quiz",
                messages=messages,
                api_key=api_key,
                base_url=settings.OPENROUTER_BASE_URL,
                temperature=0.3,
                max_tokens=4096,
            )
            return result[0] if isinstance(result, tuple) else str(result)
        except QuizGenerationError:
            raise
        except Exception as exc:
            raise QuizGenerationError(f"Failed to call OpenRouter: {str(exc)}") from exc

    def _call_llm(self, prompt: str) -> str:
        if self.llm_provider == "local_llm":
            return self._call_local_llm(prompt)
        if self.llm_provider == "gemini":
            return self._call_gemini(prompt)
        if self.llm_provider == "openrouter":
            return self._call_openrouter(prompt)
        raise QuizGenerationError(f"Unknown LLM provider: {self.llm_provider}")

    def _extract_json(self, raw: str) -> Any:
        text = str(raw).strip()
        fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        start_indexes = [i for i in (text.find("["), text.find("{")) if i != -1]
        if not start_indexes:
            raise QuizGenerationError("LLM output contains no JSON")
        start = min(start_indexes)
        end = max(text.rfind("]"), text.rfind("}"))
        if end <= start:
            raise QuizGenerationError("LLM output contains incomplete JSON")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise QuizGenerationError(f"Failed to parse LLM JSON: {str(exc)}") from exc

    def _normalize_question(self, raw: Any) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            return None

        q_type = str(raw.get("type", "")).strip().lower()
        if q_type not in VALID_QUESTION_TYPES:
            return None

        text = str(raw.get("text", "")).strip()
        if not text:
            return None

        options = raw.get("options")
        if not isinstance(options, list) or len(options) < 2:
            return None
        options = [str(option).strip() for option in options]
        if any(not option for option in options):
            return None

        answer = raw.get("answer", [])
        if isinstance(answer, int):
            answer = [answer]
        if not isinstance(answer, list) or not answer:
            return None
        try:
            answer_indexes = [int(a) for a in answer]
        except (TypeError, ValueError):
            return None
        if any(idx < 0 or idx >= len(options) for idx in answer_indexes):
            return None
        answer_indexes = sorted(set(answer_indexes))
        if q_type == "single":
            answer_indexes = answer_indexes[:1]

        explanation = str(raw.get("explanation", "")).strip()
        if not explanation:
            return None

        return {
            "type": q_type,
            "text": text,
            "options": options,
            "answer": answer_indexes,
            "explanation": explanation,
        }

    def generate_quiz(
        self, documents: List[Dict[str, Any]], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a quiz from the given documents.

        Args:
            documents: List of document dicts with name and text
            config: Quiz config with num_questions, difficulty, question_types

        Returns:
            Dict with questions (including answers) and config

        Raises:
            QuizGenerationError: If generation fails after retries
        """
        if not documents:
            raise QuizGenerationError("No documents provided")

        expected_count = int(config["num_questions"])
        last_error = None
        for _ in range(MAX_GENERATION_ATTEMPTS):
            try:
                prompt = self._build_prompt(documents, config)
                raw = self._call_llm(prompt)
                data = self._extract_json(raw)
                if isinstance(data, dict):
                    if "questions" not in data:
                        raise QuizGenerationError(
                            "LLM JSON object missing 'questions' key"
                        )
                    data = data["questions"]
                if not isinstance(data, list):
                    raise QuizGenerationError(
                        "LLM output must be a JSON array of questions"
                    )

                questions = []
                for item in data:
                    normalized = self._normalize_question(item)
                    if normalized is not None:
                        questions.append(normalized)

                if len(questions) != expected_count:
                    raise QuizGenerationError(
                        f"Expected {expected_count} questions, got {len(questions)}"
                    )
                return {"questions": questions, "config": config}
            except QuizGenerationError as exc:
                last_error = exc

        raise QuizGenerationError(
            f"Quiz generation failed after {MAX_GENERATION_ATTEMPTS} attempts: {last_error}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_quiz_generator.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Lint check**

Run: `ruff check app/services/quiz_generator.py && black --check app/services/quiz_generator.py`
Expected: no errors, no reformat needed (run `black app/services/quiz_generator.py` if it reformats)

- [ ] **Step 6: Commit**

```bash
git add app/services/quiz_generator.py tests/test_quiz_generator.py
git commit -m "feat: add quiz generator service"
```

---

### Task 2: Quiz views — helpers + generate endpoint (TDD)

**Files:**
- Create: `django_app/views/quiz.py`
- Test: `tests/test_quiz_views.py`

**Interfaces:**
- Consumes: `_error_response`, `_get_json_body` from `django_app.views.helpers`; `settings` from `app.config`; `QuizGenerator` / `QuizGenerationError` from `app.services.quiz_generator` (imported inside view functions, matching `summaries.py`).
- Produces: `QUIZ_HISTORY_FILE` (module constant, monkeypatchable), `_load_quiz_history() -> List[Dict]`, `_save_quiz_history(history) -> None`, `_get_document_text(filename) -> Optional[str]`, `_normalize_config(raw) -> Dict` (raises `ValueError`), `_strip_answers(questions) -> List[Dict]`, `generate_quiz(request) -> JsonResponse`. Later tasks add `_grade_quiz`, `submit_quiz`, `get_quiz_history`, `delete_quiz` (exact signatures below in Task 3).

- [ ] **Step 1: Write the failing test**

Create `tests/test_quiz_views.py`:

```python
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
def test_generate_quiz_invalid_config(
    client, mock_docs, quiz_history_file, bad_config
):
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_quiz_views.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'django_app.views.quiz'`

- [ ] **Step 3: Write the implementation**

Create `django_app/views/quiz.py`:

```python
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

    quiz_id = f"quiz_{int(time.time())}"
    entry = {
        "id": quiz_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "documents": [doc["name"] for doc in documents],
        "config": config,
        "questions": result["questions"],
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
            "questions": _strip_answers(result["questions"]),
            "config": config,
            "document_count": len(documents),
        }
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_quiz_views.py -v`
Expected: PASS (all tests; only generate-related tests exist so far)

- [ ] **Step 5: Lint check**

Run: `ruff check django_app/views/quiz.py && black --check django_app/views/quiz.py`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add django_app/views/quiz.py tests/test_quiz_views.py
git commit -m "feat: add quiz generate endpoint with JSON history"
```

---

### Task 3: Quiz views — submit, history, delete endpoints (TDD)

**Files:**
- Modify: `django_app/views/quiz.py`
- Test: `tests/test_quiz_views.py` (append tests)

**Interfaces:**
- Produces: `_grade_quiz(quiz: Dict, answers: Dict) -> Dict` returning `{"score": int, "total": int, "per_question": [{"index", "correct", "correct_answers", "your_answers", "explanation"}]}`; `submit_quiz(request) -> JsonResponse` (request JSON `{quiz_id: str, answers: {q_index: [choice_idx, ...]}}`); `get_quiz_history(request) -> JsonResponse`; `delete_quiz(request, quiz_id: str) -> JsonResponse`.

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_quiz_views.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_quiz_views.py -v`
Expected: submit/history/delete tests FAIL with 404 (URLs not registered yet) or attribute errors; the generate tests from Task 2 still PASS.

Note: URL failures appear as 404 because routes are only registered in Task 4. In Django test client, an unregistered URL raises 404 response. This is fine — after Task 4 the same tests pass. If you prefer to see the real failure earlier, temporarily add the routes from Task 4 now; otherwise proceed.

- [ ] **Step 3: Implement the endpoints**

Append to `django_app/views/quiz.py` (after `_strip_answers`):

```python
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
        limit = int(request.GET.get("limit", 20))
        limit = min(limit, 50)

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
```

- [ ] **Step 4: Lint check**

Run: `ruff check django_app/views/quiz.py && black --check django_app/views/quiz.py`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add django_app/views/quiz.py tests/test_quiz_views.py
git commit -m "feat: add quiz submit, history, and delete endpoints"
```

---

### Task 4: Register URLs and view exports

**Files:**
- Modify: `django_backend/urls.py` (insert quiz block after the "Question Suggestion endpoints" block, before "# LLM Monitoring")
- Modify: `django_app/views/__init__.py` (import + `__all__` entries)

**Interfaces:**
- Produces: URL paths `api/quiz/generate`, `api/quiz/submit`, `api/quiz/history`, `api/quiz/<str:quiz_id>/delete` (each with and without trailing slash); names `generate_quiz`, `submit_quiz`, `get_quiz_history`, `delete_quiz` exported from `django_app.views`.

- [ ] **Step 1: Add URL routes**

In `django_backend/urls.py`, after the block:

```python
    path("api/suggestions/history", views.get_suggestion_history),
    path("api/suggestions/history/", views.get_suggestion_history),
```

insert:

```python
    # Quiz endpoints
    path("api/quiz/generate", views.generate_quiz),
    path("api/quiz/generate/", views.generate_quiz),
    path("api/quiz/submit", views.submit_quiz),
    path("api/quiz/submit/", views.submit_quiz),
    path("api/quiz/history", views.get_quiz_history),
    path("api/quiz/history/", views.get_quiz_history),
    path("api/quiz/<str:quiz_id>/delete", views.delete_quiz),
    path("api/quiz/<str:quiz_id>/delete/", views.delete_quiz),
```

- [ ] **Step 2: Export views**

In `django_app/views/__init__.py`, after the Summaries import block:

```python
# Summaries
from django_app.views.summaries import (
    generate_summary,
    get_summary_history,
    delete_summary,
    regenerate_summary,
)
```

insert:

```python
# Quiz
from django_app.views.quiz import (
    generate_quiz,
    submit_quiz,
    get_quiz_history,
    delete_quiz,
)
```

And in `__all__`, after the `"regenerate_summary",` line insert:

```python
    # Quiz
    "generate_quiz",
    "submit_quiz",
    "get_quiz_history",
    "delete_quiz",
```

- [ ] **Step 3: Verify with Django checks and tests**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

Run: `pytest tests/test_quiz_views.py -v`
Expected: PASS (all generate + submit + history + delete tests)

- [ ] **Step 4: Commit**

```bash
git add django_backend/urls.py django_app/views/__init__.py
git commit -m "feat: register quiz API routes"
```

---

### Task 5: Frontend API functions

**Files:**
- Modify: `frontend/src/services/api.js` (insert before `export default api`)

**Interfaces:**
- Produces: `generateQuiz(documentIds, config)`, `submitQuiz(quizId, answers)`, `getQuizHistory(limit)`, `deleteQuiz(quizId)` — all return `response.data` via the existing axios instance (baseURL `/api`).

- [ ] **Step 1: Add API functions**

In `frontend/src/services/api.js`, before the line `export default api`, insert:

```js
// Quiz API
export const generateQuiz = async (documentIds, config = {}) => {
  const response = await api.post('/quiz/generate', {
    document_ids: documentIds,
    config,
  })
  return response.data
}

export const submitQuiz = async (quizId, answers) => {
  const response = await api.post('/quiz/submit', {
    quiz_id: quizId,
    answers,
  })
  return response.data
}

export const getQuizHistory = async (limit = 20) => {
  const response = await api.get(`/quiz/history?limit=${limit}`)
  return response.data
}

export const deleteQuiz = async (quizId) => {
  const response = await api.post(`/quiz/${quizId}/delete`)
  return response.data
}
```

- [ ] **Step 2: Verify build**

Run (workdir `frontend`): `npm run build`
Expected: build succeeds (existing code unaffected; no import errors)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat: add quiz API client functions"
```

---

### Task 6: Pinia quiz store

**Files:**
- Create: `frontend/src/stores/quizStore.js`

**Interfaces:**
- Consumes: `generateQuiz`, `submitQuiz`, `getQuizHistory`, `deleteQuiz` from `../services/api`.
- Produces: `useQuizStore()` (setup store) exposing state `currentQuiz` (shape `{quiz_id, questions, config, documents, attempts}`), `quizHistory`, `isLoading`, `isGenerating`, `isSubmitting`, `lastResult` (shape `{score, total, per_question}`), `error`; actions `loadHistory(limit)`, `generate(documentIds, config)`, `submit(answers)`, `remove(quizId)`, `selectFromHistory(quiz)`, `clearCurrent()`. `generate`/`submit` return the result or `null` on failure.

- [ ] **Step 1: Create the store**

Create `frontend/src/stores/quizStore.js`:

```js
import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  generateQuiz,
  submitQuiz,
  getQuizHistory,
  deleteQuiz,
} from '../services/api'

export const useQuizStore = defineStore('quiz', () => {
  const currentQuiz = ref(null)
  const quizHistory = ref([])
  const isLoading = ref(false)
  const isGenerating = ref(false)
  const isSubmitting = ref(false)
  const lastResult = ref(null)
  const error = ref(null)

  async function loadHistory(limit = 20) {
    try {
      isLoading.value = true
      error.value = null
      const response = await getQuizHistory(limit)
      quizHistory.value = response.history || []
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      console.error('Failed to load quiz history:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function generate(documentIds, config = {}) {
    try {
      isGenerating.value = true
      error.value = null
      const response = await generateQuiz(documentIds, config)

      currentQuiz.value = {
        quiz_id: response.quiz_id,
        questions: response.questions || [],
        config: response.config,
        documents: response.documents || [],
        attempts: 0,
      }
      lastResult.value = null

      quizHistory.value.unshift({
        id: response.quiz_id,
        timestamp: new Date().toISOString(),
        documents: response.documents || [],
        questions: response.questions || [],
        config: response.config,
        attempts: [],
      })

      return currentQuiz.value
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      console.error('Failed to generate quiz:', err)
      return null
    } finally {
      isGenerating.value = false
    }
  }

  async function submit(answers) {
    if (!currentQuiz.value) return null
    try {
      isSubmitting.value = true
      error.value = null
      const response = await submitQuiz(currentQuiz.value.quiz_id, answers)

      lastResult.value = {
        score: response.score,
        total: response.total,
        per_question: response.per_question || [],
      }

      return lastResult.value
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      console.error('Failed to submit quiz:', err)
      return null
    } finally {
      isSubmitting.value = false
    }
  }

  async function remove(quizId) {
    try {
      error.value = null
      await deleteQuiz(quizId)

      quizHistory.value = quizHistory.value.filter((h) => h.id !== quizId)

      if (currentQuiz.value?.quiz_id === quizId) {
        currentQuiz.value = null
      }

      return true
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      console.error('Failed to delete quiz:', err)
      return false
    }
  }

  function selectFromHistory(quiz) {
    currentQuiz.value = {
      quiz_id: quiz.id,
      questions: quiz.questions || [],
      config: quiz.config,
      documents: quiz.documents || [],
      attempts: quiz.attempts || [],
    }
    lastResult.value = null
  }

  function clearCurrent() {
    currentQuiz.value = null
    lastResult.value = null
    error.value = null
  }

  return {
    currentQuiz,
    quizHistory,
    isLoading,
    isGenerating,
    isSubmitting,
    lastResult,
    error,
    loadHistory,
    generate,
    submit,
    remove,
    selectFromHistory,
    clearCurrent,
  }
})
```

- [ ] **Step 2: Verify build**

Run (workdir `frontend`): `npm run build`
Expected: build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/stores/quizStore.js
git commit -m "feat: add quiz pinia store"
```

---

### Task 7: QuizModal component

**Files:**
- Create: `frontend/src/components/studio/QuizModal.vue`

**Interfaces:**
- Props: `show: Boolean`, `selectedDocs: Array` (document ids).
- Emits: `update:show`, `close`, `generate` (payload = config object `{num_questions, difficulty, question_types}`), `view` (user opened a quiz from history).
- Consumes: `useQuizStore` from `../../stores/quizStore` (`loadHistory`, `selectFromHistory`, `remove`, `quizHistory`, `isLoading`, `error`).
- Behavior: on open loads history; config = 5 questions / medium / 3:2; changing total auto-splits 60/40; validates sum before emitting `generate`; history list with open/delete per entry.

- [ ] **Step 1: Create the component**

Create `frontend/src/components/studio/QuizModal.vue`:

```vue
<script setup>
import { ref, computed, watch } from 'vue'
import { useQuizStore } from '../../stores/quizStore'

const props = defineProps({
  show: Boolean,
  selectedDocs: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:show', 'close', 'generate', 'view'])

const quizStore = useQuizStore()

const config = ref({
  num_questions: 5,
  difficulty: 'medium',
  question_types: { single: 3, multiple: 2 },
})

const error = ref('')

const selectedCount = computed(() => props.selectedDocs.length)

const typeSum = computed(
  () => config.value.question_types.single + config.value.question_types.multiple
)

const isConfigValid = computed(() => {
  const total = config.value.num_questions
  if (!Number.isInteger(total) || total < 1 || total > 20) return false
  if (config.value.question_types.single < 0 || config.value.question_types.multiple < 0) {
    return false
  }
  return typeSum.value === total
})

const difficultyOptions = [
  { value: 'easy', label: 'Easy', desc: 'Basic recall of facts and definitions' },
  { value: 'medium', label: 'Medium', desc: 'Understanding and application' },
  { value: 'hard', label: 'Hard', desc: 'Analysis and synthesis' },
]

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      error.value = ''
      quizStore.loadHistory(20)
    }
  }
)

function onTotalChange() {
  const total = config.value.num_questions || 1
  const single = Math.max(0, Math.round(total * 0.6))
  config.value.question_types = { single, multiple: total - single }
}

function handleClose() {
  emit('update:show', false)
  emit('close')
}

function handleGenerate() {
  error.value = ''
  if (props.selectedDocs.length === 0) {
    error.value = 'Please select at least one document'
    return
  }
  if (!isConfigValid.value) {
    error.value = 'Single + multiple must equal the total number of questions'
    return
  }
  emit('generate', JSON.parse(JSON.stringify(config.value)))
}

function handleOpenHistory(quiz) {
  quizStore.selectFromHistory(quiz)
  emit('view')
}

async function handleDeleteHistory(quizId) {
  const ok = await quizStore.remove(quizId)
  if (!ok) {
    error.value = quizStore.error || 'Failed to delete quiz'
  }
}
</script>

<template>
  <transition name="modal">
    <div v-if="show" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>Quiz Generator</h3>
          <button class="modal-close" @click="handleClose" aria-label="Close quiz modal">✕</button>
        </div>
        <div class="modal-body">
          <div class="selected-docs-info">
            <div class="info-header">
              <span class="info-icon">📄</span>
              <span class="info-text">{{ selectedCount }} document(s) selected</span>
            </div>
            <div class="doc-list">
              <div v-for="doc in selectedDocs" :key="doc" class="doc-item">
                <span class="doc-icon">📋</span>
                <span class="doc-name" :title="doc">{{ doc }}</span>
              </div>
            </div>
          </div>

          <div class="config-section">
            <h4>Quiz Configuration</h4>

            <div class="config-item">
              <label class="config-label">Number of Questions</label>
              <input
                type="number"
                min="1"
                max="20"
                class="num-input"
                v-model.number="config.num_questions"
                @change="onTotalChange"
              />
            </div>

            <div class="config-item">
              <label class="config-label">Difficulty</label>
              <div class="option-grid">
                <button
                  v-for="opt in difficultyOptions"
                  :key="opt.value"
                  type="button"
                  class="option-card"
                  :class="{ active: config.difficulty === opt.value }"
                  @click="config.difficulty = opt.value"
                >
                  <span class="option-title">{{ opt.label }}</span>
                  <span class="option-desc">{{ opt.desc }}</span>
                </button>
              </div>
            </div>

            <div class="config-item">
              <label class="config-label">Question Types</label>
              <div class="type-row">
                <div class="type-input">
                  <span class="type-name">Single choice</span>
                  <input
                    type="number"
                    min="0"
                    class="type-num"
                    v-model.number="config.question_types.single"
                  />
                </div>
                <div class="type-input">
                  <span class="type-name">Multiple choice</span>
                  <input
                    type="number"
                    min="0"
                    class="type-num"
                    v-model.number="config.question_types.multiple"
                  />
                </div>
              </div>
              <p v-if="!isConfigValid" class="type-warning">
                Single + multiple must equal {{ config.num_questions }}
              </p>
            </div>
          </div>

          <div class="history-section" v-if="quizStore.quizHistory.length > 0">
            <h4>Recent Quizzes</h4>
            <div v-if="quizStore.isLoading" class="history-empty">Loading...</div>
            <div v-for="quiz in quizStore.quizHistory" :key="quiz.id" class="history-item">
              <div class="history-info">
                <span class="history-docs">{{ quiz.documents.join(', ') }}</span>
                <span class="history-meta">
                  {{ quiz.config ? `${quiz.config.num_questions} questions` : '' }}
                </span>
              </div>
              <div class="history-actions">
                <button type="button" class="btn-history" @click="handleOpenHistory(quiz)">Open</button>
                <button type="button" class="btn-history danger" @click="handleDeleteHistory(quiz.id)">Delete</button>
              </div>
            </div>
          </div>

          <div v-if="error" class="error-message">
            {{ error }}
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="handleClose">Cancel</button>
          <button
            class="btn-generate"
            @click="handleGenerate"
            :disabled="quizStore.isGenerating || selectedCount === 0 || !isConfigValid"
          >
            {{ quizStore.isGenerating ? 'Generating...' : '✨ Generate Quiz' }}
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  width: min(600px, 90vw);
  max-height: 85vh;
  background: var(--surface-container);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--outline-variant);
  border-radius: 20px;
  box-shadow: 0 30px 60px rgba(0, 0, 0, 0.8);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--outline-variant);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--on-surface);
}

.modal-close {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-high);
  color: var(--on-surface-variant);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.modal-close:hover {
  background: var(--tertiary-container);
  color: var(--on-tertiary);
  transform: rotate(90deg);
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.selected-docs-info {
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 12px;
  padding: 12px;
}

.info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.info-icon {
  font-size: 16px;
}

.info-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary-container);
}

.doc-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 120px;
  overflow-y: auto;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--surface-container);
  font-size: 11px;
  color: var(--on-surface-variant);
}

.doc-icon {
  font-size: 14px;
}

.doc-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.config-section h4,
.history-section h4 {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--on-surface-variant);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.config-item {
  margin-bottom: 16px;
}

.config-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--on-surface);
  margin-bottom: 8px;
}

.num-input,
.type-num {
  width: 100px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 13px;
}

.option-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.option-card {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
}

.option-card:hover {
  border-color: var(--primary);
  background: var(--surface-container-high);
}

.option-card.active {
  border-color: var(--primary-container);
  background: var(--primary-container);
  box-shadow: 0 0 0 1px var(--primary);
}

.option-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--on-surface);
}

.option-desc {
  font-size: 10px;
  color: var(--on-surface-variant);
}

.type-row {
  display: flex;
  gap: 24px;
}

.type-input {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.type-name {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.type-warning {
  margin: 8px 0 0;
  font-size: 11px;
  color: #fbbf24;
}

.history-section {
  border-top: 1px solid var(--outline-variant);
  padding-top: 16px;
}

.history-empty {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--surface-container-high);
  margin-bottom: 6px;
}

.history-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.history-docs {
  font-size: 12px;
  color: var(--on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-meta {
  font-size: 10px;
  color: var(--on-surface-variant);
}

.history-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.btn-history {
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 11px;
  cursor: pointer;
}

.btn-history:hover {
  border-color: var(--primary);
}

.btn-history.danger:hover {
  border-color: #ef4444;
  color: #ef4444;
}

.error-message {
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--tertiary-container);
  border: 1px solid var(--tertiary);
  color: var(--on-tertiary);
  font-size: 12px;
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--outline-variant);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  background: var(--surface-container-low);
}

.btn-cancel {
  padding: 10px 20px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-cancel:hover {
  border-color: var(--on-surface-variant);
}

.btn-generate {
  padding: 10px 24px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, var(--primary-container), var(--primary));
  color: var(--on-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-generate:hover:not(:disabled) {
  transform: scale(1.02);
  box-shadow: 0 10px 25px var(--primary);
}

.btn-generate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.modal-enter-active,
.modal-leave-active {
  transition: all 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95) translateY(20px);
}
</style>
```

- [ ] **Step 2: Verify build**

Run (workdir `frontend`): `npm run build`
Expected: build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studio/QuizModal.vue
git commit -m "feat: add quiz generation modal"
```

---

### Task 8: QuizViewer component

**Files:**
- Create: `frontend/src/components/studio/QuizViewer.vue`

**Interfaces:**
- Props: `show: Boolean`.
- Emits: `update:show`, `close`.
- Consumes: `useQuizStore` (`currentQuiz`, `isSubmitting`, `lastResult`, `submit`, `error`).
- Behavior: on `show` resets session (phase `answering`, answers `{}`, activeIndices = all). Single = radio, multiple = checkbox. Submit blocked with message when unanswered; calls `quizStore.submit({index: [choiceIdx...]})` keyed by original question index; on success phase = `results`. `startRetake()` sets activeIndices to wrong-question indices and clears answers (frontend-only).

- [ ] **Step 1: Create the component**

Create `frontend/src/components/studio/QuizViewer.vue`:

```vue
<script setup>
import { ref, computed, watch } from 'vue'
import { useQuizStore } from '../../stores/quizStore'

const props = defineProps({
  show: Boolean,
})

const emit = defineEmits(['update:show', 'close'])

const quizStore = useQuizStore()

const phase = ref('answering')
const activeIndices = ref([])
const answers = ref({})
const submitError = ref('')

const quiz = computed(() => quizStore.currentQuiz)
const isSubmitting = computed(() => quizStore.isSubmitting)
const result = computed(() => quizStore.lastResult)

const activeQuestions = computed(() => {
  if (!quiz.value) return []
  return activeIndices.value
    .map((index) => ({ index, question: quiz.value.questions[index] }))
    .filter((item) => item.question)
})

const answeredCount = computed(() => {
  return activeQuestions.value.filter((item) => {
    const answer = answers.value[item.index]
    return Array.isArray(answer) && answer.length > 0
  }).length
})

const wrongIndices = computed(() => {
  if (!result.value) return []
  return result.value.per_question
    .filter((item) => !item.correct)
    .map((item) => item.index)
})

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      resetSession()
    }
  }
)

function resetSession() {
  phase.value = 'answering'
  submitError.value = ''
  answers.value = {}
  activeIndices.value = quiz.value
    ? quiz.value.questions.map((_, index) => index)
    : []
}

function toggleOption(questionIndex, optionIndex) {
  const question = quiz.value?.questions[questionIndex]
  if (!question) return

  if (question.type === 'single') {
    answers.value[questionIndex] = [optionIndex]
    return
  }

  if (!answers.value[questionIndex]) {
    answers.value[questionIndex] = []
  }
  const current = answers.value[questionIndex]
  const position = current.indexOf(optionIndex)
  if (position === -1) {
    current.push(optionIndex)
  } else {
    current.splice(position, 1)
  }
}

function resultFor(index) {
  if (!result.value) return null
  return result.value.per_question.find((item) => item.index === index) || null
}

async function handleSubmit() {
  submitError.value = ''
  const unanswered = activeQuestions.value.filter((item) => {
    const answer = answers.value[item.index]
    return !(Array.isArray(answer) && answer.length > 0)
  })

  if (unanswered.length > 0) {
    submitError.value = `Please answer all questions (${unanswered.length} unanswered)`
    return
  }

  const payload = {}
  for (const item of activeQuestions.value) {
    payload[item.index] = answers.value[item.index]
  }

  const submission = await quizStore.submit(payload)
  if (submission) {
    phase.value = 'results'
  } else {
    submitError.value = quizStore.error || 'Failed to submit quiz'
  }
}

function startRetake() {
  activeIndices.value = [...wrongIndices.value]
  answers.value = {}
  phase.value = 'answering'
  submitError.value = ''
}

function handleClose() {
  emit('update:show', false)
  emit('close')
}
</script>

<template>
  <transition name="modal">
    <div v-if="show" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>Quiz</h3>
          <button class="modal-close" @click="handleClose" aria-label="Close quiz">✕</button>
        </div>

        <div class="modal-body" v-if="quiz">
          <div class="quiz-meta" v-if="phase === 'answering'">
            <span>{{ answeredCount }} / {{ activeQuestions.length }} answered</span>
            <span class="quiz-docs">{{ quiz.documents.join(', ') }}</span>
          </div>

          <template v-if="phase === 'answering'">
            <div v-for="item in activeQuestions" :key="item.index" class="question-card">
              <div class="question-header">
                <span class="question-number">Q{{ item.index + 1 }}</span>
                <span v-if="item.question.type === 'multiple'" class="type-badge">Multiple</span>
              </div>
              <p class="question-text">{{ item.question.text }}</p>
              <div class="options-list">
                <label
                  v-for="(option, optionIndex) in item.question.options"
                  :key="optionIndex"
                  class="option-item"
                  :class="{ selected: (answers[item.index] || []).includes(optionIndex) }"
                >
                  <input
                    :type="item.question.type === 'single' ? 'radio' : 'checkbox'"
                    :name="'question-' + item.index"
                    :checked="(answers[item.index] || []).includes(optionIndex)"
                    @change="toggleOption(item.index, optionIndex)"
                  />
                  <span class="option-letter">{{ String.fromCharCode(65 + optionIndex) }}</span>
                  <span class="option-text">{{ option }}</span>
                </label>
              </div>
            </div>

            <div v-if="submitError" class="error-message">{{ submitError }}</div>
          </template>

          <template v-else-if="phase === 'results' && result">
            <div class="score-panel">
              <div class="score-number">{{ result.score }} / {{ result.total }}</div>
              <div class="score-label">
                {{ result.score === result.total ? 'Perfect!' : result.score >= result.total / 2 ? 'Good effort!' : 'Keep reviewing!' }}
              </div>
            </div>

            <div
              v-for="item in activeQuestions"
              :key="item.index"
              class="question-card result-card"
            >
              <div class="question-header">
                <span class="question-number">Q{{ item.index + 1 }}</span>
                <span
                  class="result-badge"
                  :class="resultFor(item.index)?.correct ? 'correct' : 'wrong'"
                >
                  {{ resultFor(item.index)?.correct ? 'Correct' : 'Wrong' }}
                </span>
              </div>
              <p class="question-text">{{ item.question.text }}</p>
              <div class="options-list">
                <div
                  v-for="(option, optionIndex) in item.question.options"
                  :key="optionIndex"
                  class="option-item static"
                  :class="{
                    correct: (resultFor(item.index)?.correct_answers || []).includes(optionIndex),
                    wrong: (resultFor(item.index)?.your_answers || []).includes(optionIndex) && !(resultFor(item.index)?.correct_answers || []).includes(optionIndex),
                  }"
                >
                  <span class="option-letter">{{ String.fromCharCode(65 + optionIndex) }}</span>
                  <span class="option-text">{{ option }}</span>
                </div>
              </div>
              <div class="explanation">
                <strong>Explanation:</strong> {{ resultFor(item.index)?.explanation }}
              </div>
            </div>
          </template>
        </div>

        <div class="modal-footer" v-if="quiz">
          <template v-if="phase === 'answering'">
            <span class="footer-note">{{ activeQuestions.length }} question(s)</span>
            <div class="footer-actions">
              <button class="btn-cancel" @click="handleClose" :disabled="isSubmitting">Cancel</button>
              <button class="btn-generate" @click="handleSubmit" :disabled="isSubmitting">
                {{ isSubmitting ? 'Submitting...' : 'Submit Answers' }}
              </button>
            </div>
          </template>
          <template v-else-if="phase === 'results'">
            <span class="footer-note">Score: {{ result.score }} / {{ result.total }}</span>
            <div class="footer-actions">
              <button
                v-if="wrongIndices.length > 0"
                class="btn-retake"
                @click="startRetake"
              >
                Redo Wrong Questions ({{ wrongIndices.length }})
              </button>
              <button class="btn-cancel" @click="handleClose">Close</button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  width: min(640px, 92vw);
  max-height: 88vh;
  background: var(--surface-container);
  border: 1px solid var(--outline-variant);
  border-radius: 20px;
  box-shadow: 0 30px 60px rgba(0, 0, 0, 0.8);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--outline-variant);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--on-surface);
}

.modal-close {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-high);
  color: var(--on-surface-variant);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.modal-close:hover {
  background: var(--tertiary-container);
  color: var(--on-tertiary);
  transform: rotate(90deg);
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.quiz-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--on-surface-variant);
}

.quiz-docs {
  max-width: 55%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.question-card {
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 12px;
  padding: 16px;
}

.question-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.question-number {
  font-size: 12px;
  font-weight: 700;
  color: var(--primary-container);
}

.type-badge {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 3px 8px;
  border-radius: 8px;
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.question-text {
  margin: 0 0 12px;
  font-size: 14px;
  color: var(--on-surface);
  line-height: 1.5;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  cursor: pointer;
  transition: all 0.15s;
}

.option-item:hover {
  border-color: var(--primary);
}

.option-item.selected {
  border-color: var(--primary-container);
  background: var(--primary-container);
}

.option-item input {
  width: 16px;
  height: 16px;
  accent-color: var(--primary-container);
  cursor: pointer;
  flex-shrink: 0;
}

.option-letter {
  font-size: 12px;
  font-weight: 700;
  color: var(--on-surface-variant);
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1px solid var(--outline-variant);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.option-text {
  font-size: 13px;
  color: var(--on-surface);
}

.option-item.static {
  cursor: default;
}

.option-item.static.correct {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.12);
}

.option-item.static.wrong {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.12);
}

.score-panel {
  text-align: center;
  padding: 20px;
  border-radius: 12px;
  background: var(--primary-container);
}

.score-number {
  font-size: 32px;
  font-weight: 700;
  color: var(--on-primary);
}

.score-label {
  margin-top: 4px;
  font-size: 13px;
  color: var(--on-primary);
  opacity: 0.9;
}

.result-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 8px;
}

.result-badge.correct {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.result-badge.wrong {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.explanation {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--surface-container);
  font-size: 12px;
  color: var(--on-surface-variant);
  line-height: 1.5;
}

.error-message {
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--tertiary-container);
  border: 1px solid var(--tertiary);
  color: var(--on-tertiary);
  font-size: 12px;
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--outline-variant);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--surface-container-low);
}

.footer-note {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.footer-actions {
  display: flex;
  gap: 10px;
}

.btn-cancel {
  padding: 10px 20px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-cancel:hover:not(:disabled) {
  border-color: var(--on-surface-variant);
}

.btn-cancel:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-generate {
  padding: 10px 24px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, var(--primary-container), var(--primary));
  color: var(--on-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-generate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-retake {
  padding: 10px 20px;
  border-radius: 10px;
  border: 1px solid var(--primary-container);
  background: var(--surface-container);
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-retake:hover {
  background: var(--primary-container);
  color: var(--on-primary);
}

.modal-enter-active,
.modal-leave-active {
  transition: all 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95) translateY(20px);
}
</style>
```

- [ ] **Step 2: Verify build**

Run (workdir `frontend`): `npm run build`
Expected: build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studio/QuizViewer.vue
git commit -m "feat: add quiz viewer with grading and retake"
```

---

### Task 9: Wire quiz into StudioPanel

**Files:**
- Modify: `frontend/src/components/layout/StudioPanel.vue`

**Interfaces:**
- Consumes: `QuizModal` (`v-model:show`, `:selected-docs`, `@generate`, `@view`, `@close`), `QuizViewer` (`v-model:show`, `@close`), `useQuizStore` from `../../stores/quizStore`.

- [ ] **Step 1: Update imports and script setup**

In `frontend/src/components/layout/StudioPanel.vue` script block, change:

```js
import { useDocumentStore } from '../../stores/documentStore'
import { useSummaryStore } from '../../stores/summaryStore'
import SummaryModal from '../studio/SummaryModal.vue'
import SummaryViewer from '../studio/SummaryViewer.vue'
```

to:

```js
import { useDocumentStore } from '../../stores/documentStore'
import { useSummaryStore } from '../../stores/summaryStore'
import { useQuizStore } from '../../stores/quizStore'
import SummaryModal from '../studio/SummaryModal.vue'
import SummaryViewer from '../studio/SummaryViewer.vue'
import QuizModal from '../studio/QuizModal.vue'
import QuizViewer from '../studio/QuizViewer.vue'
```

Change:

```js
const documentStore = useDocumentStore()
const summaryStore = useSummaryStore()
```

to:

```js
const documentStore = useDocumentStore()
const summaryStore = useSummaryStore()
const quizStore = useQuizStore()
```

- [ ] **Step 2: Enable the quiz tool card**

In the `studioTools` array, change the `quiz` entry:

```js
  {
    id: 'quiz',
    title: 'Quiz',
    desc: 'Test your understanding with an interactive quiz.',
    icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z',
    comingSoon: true,
  },
```

to:

```js
  {
    id: 'quiz',
    title: 'Quiz',
    desc: 'Test your understanding with an interactive quiz.',
    icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z',
    action: 'quiz',
  },
```

- [ ] **Step 3: Add quiz state and handlers**

After the `showSummaryModal`/`showSummaryViewer` refs:

```js
const showSummaryModal = ref(false)
const showSummaryViewer = ref(false)
```

add:

```js
const showQuizModal = ref(false)
const showQuizViewer = ref(false)
```

In `handleToolClick`, after the summary branch:

```js
  if (tool.action === 'summary') {
    openSummaryModal()
  }
```

add:

```js
  if (tool.action === 'quiz') {
    openQuizModal()
  }
```

After `openSummaryModal` definition, add:

```js
const openQuizModal = () => {
  if (selectedCount.value === 0) {
    alert('Please select at least one document in the sidebar first')
    return
  }
  showQuizModal.value = true
}

const handleQuizGenerate = async (config) => {
  const quiz = await quizStore.generate(selectedDocs.value, config)
  showQuizModal.value = false
  if (quiz) {
    showQuizViewer.value = true
  }
}

const handleQuizOpenFromHistory = () => {
  showQuizModal.value = false
  showQuizViewer.value = true
}

const closeQuizViewer = () => {
  showQuizViewer.value = false
  quizStore.clearCurrent()
}
```

- [ ] **Step 4: Add modal components to the template**

After the existing `SummaryModal` tag:

```html
    <SummaryModal
      v-model:show="showSummaryModal"
      :selected-docs="selectedDocs"
      @generate="handleSummaryGenerate"
      @close="showSummaryModal = false"
    />
```

add:

```html
    <QuizModal
      v-model:show="showQuizModal"
      :selected-docs="selectedDocs"
      @generate="handleQuizGenerate"
      @view="handleQuizOpenFromHistory"
      @close="showQuizModal = false"
    />

    <QuizViewer
      v-model:show="showQuizViewer"
      @close="closeQuizViewer"
    />
```

Also, in the tool-card template, change the badge condition:

```html
          <span v-else-if="tool.action === 'summary' && selectedCount > 0" class="tool-badge" aria-hidden="true">
            {{ selectedCount }}
          </span>
```

to:

```html
          <span
            v-else-if="(tool.action === 'summary' || tool.action === 'quiz') && selectedCount > 0"
            class="tool-badge"
            aria-hidden="true"
          >
            {{ selectedCount }}
          </span>
```

- [ ] **Step 5: Verify build**

Run (workdir `frontend`): `npm run build`
Expected: build succeeds

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/layout/StudioPanel.vue
git commit -m "feat: wire quiz tool into studio panel"
```

---

### Task 10: Final verification and quality gates

**Files:**
- None (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `pytest tests/test_quiz_generator.py tests/test_quiz_views.py -v`
Expected: PASS (all quiz tests)

Run: `pytest tests/ -q`
Expected: passes (if pre-existing failures exist unrelated to quiz, note them but do not fix in this feature)

- [ ] **Step 2: Lint and typecheck changed backend files**

Run: `ruff check app/services/quiz_generator.py django_app/views/quiz.py django_app/views/__init__.py django_backend/urls.py`
Expected: no errors

Run: `black --check app/services/quiz_generator.py django_app/views/quiz.py django_app/views/__init__.py django_backend/urls.py`
Expected: no reformat needed (if reformatted, re-run black and commit)

Run: `mypy app/services/quiz_generator.py django_app/views/quiz.py`
Expected: no new errors

- [ ] **Step 3: Verify frontend build**

Run (workdir `frontend`): `npm run build`
Expected: build succeeds

- [ ] **Step 4: Manual smoke test (optional, requires configured LLM)**

Run: `python manage.py runserver 0.0.0.0:8000`

1. Open the app, select a document in the sidebar.
2. Open Studio panel → click Quiz tool → configure 3 questions → Generate Quiz.
3. Answer some questions (leave one unanswered → submit shows warning).
4. Answer all → Submit → verify score, per-question correct/wrong badges, explanations.
5. Click "Redo Wrong Questions" → verify only wrong questions appear.
6. Reopen Quiz modal → verify quiz appears under Recent Quizzes → Open → Delete works.
7. Check `data/quiz_history.json` contains entries with answers server-side.

Expected: all steps behave as described.

- [ ] **Step 5: Final commit (if lint fixes were needed)**

```bash
git add -A && git commit -m "style: apply lint fixes for quiz module"
```

---

## Self-Review Notes

- Spec coverage: generation service (Task 1), 4 endpoints (Tasks 2–3), routes/exports (Task 4), frontend API/store/modal/viewer/wiring (Tasks 5–9), error handling (400/404/500 tests in Tasks 2–3), history strip + cap 50 (implemented in Task 2, trimmed on save), multi-select full-match grading (Task 3 test `test_submit_quiz_partial_multi_is_wrong`), retake-wrong (Task 8 `startRetake`), default config 5/medium/3:2 (QuizModal defaults; backend `DEFAULT_QUESTION_COUNT` + all-single fallback).
- Known deviation: frontend sends `question_types` explicitly, so the backend all-single fallback only triggers for API-only clients; acceptable per spec (default 3:2 applies to the UI default).
- The cap-50 trim is exercised indirectly (no dedicated test); acceptable given the summaries module has the same pattern.
