# Quiz Module Design (Multiple-Choice Quiz)

- Date: 2026-08-13
- Status: Approved

## 1. Goal

Add a quiz module to the RAG lecture-note system: generate multiple-choice
quizzes (single- and multi-select) from indexed documents via the configured
LLM, let users answer them in the Vue frontend, grade instantly server-side,
show per-question explanations, and support redoing wrong questions. Quiz and
attempt history are persisted in a JSON file, mirroring the existing summary
module.

## 2. Non-Goals

- No open-ended/short-answer questions (out of scope; LLM answer grading not needed).
- No question bank with reusable random draws.
- No database models; JSON-file persistence only.
- No flashcards (separate feature, remains `comingSoon`).

## 3. Approach

**Chosen: one-shot LLM generation + server-side local grading (Option A).**

One LLM call produces all questions, options, answer keys, and explanations.
The quiz record (including the answer key) is stored in JSON history. Submitting
answers grades locally against the stored key — no LLM call at submit time, so
grading is instant, deterministic, and free of extra cost. Explanations are
generated alongside the questions and shown after submission.

Rejected alternatives:
- Option B (LLM grading at submit): slower, non-deterministic, extra cost.
- Option C (question bank + repeated draws): unnecessary complexity (YAGNI).

## 4. Architecture & Components

Follows the existing summary-module layering exactly.

### Backend

| Component | File | Responsibility |
|---|---|---|
| Generation service | `app/services/quiz_generator.py` | LLM quiz generation: build prompt, call LLM via provider routing (`call_llm`, runtime_llm settings), parse & validate strict JSON, retry once on failure, raise `QuizGenerationError` |
| API views | `django_app/views/quiz.py` | 4 endpoints: generate, submit, history, delete; JSON history file read/write (`data/quiz_history.json`, max 50 entries, same pattern as `summaries.py`) |
| Routes | `django_backend/urls.py` | Register endpoints with and without trailing slash (existing convention) |

### Frontend

| Component | File | Responsibility |
|---|---|---|
| Pinia store | `frontend/src/stores/quizStore.js` | generating state, current quiz, submit/grading state |
| Generate modal | `frontend/src/components/studio/QuizModal.vue` | confirm documents + config (num questions, difficulty, question-type mix) |
| Quiz viewer | `frontend/src/components/studio/QuizViewer.vue` | answering (radio/checkbox), submit, results (score + per-question correctness + explanation), redo-wrong |
| API client | `frontend/src/services/api.js` | 4 API functions |
| Entry point | `frontend/src/components/layout/StudioPanel.vue` | remove `comingSoon` on `quiz` tool, wire `openQuizModal()` (requires selected documents, like summary) |

### Dependencies

`QuizViewer/Modal → quizStore → api.js → django_app/views/quiz.py → app/services/quiz_generator.py → call_llm`

Document text retrieval reuses the vector-store lookup pattern from
`django_app/views/summaries.py::_get_document_text` (truncated to ~5000 chars per document).

## 5. Data Flow

```
select docs → config (count/difficulty/types) → POST /api/quiz/generate
  → get doc text from FAISS index
  → one LLM call → {question, options, answer_index, explanation}[]
  → validate/parse JSON (retry once)
  → save history entry (with answer key) → return questions (no answers)
  → user answers in UI → POST /api/quiz/submit {quiz_id, answers}
  → server grades against answer key → {score, per_question: correct/correct_answers/explanation}
  → redo wrong: frontend starts new answering session with wrong-question subset
    (frontend state only, not persisted)
```

## 6. API Design

All endpoints `@csrf_exempt`; errors via `_error_response(detail, status)`.

| Endpoint | Method | Request | Response |
|---|---|---|---|
| `/api/quiz/generate` | POST | `{document_ids: [...], config: {num_questions, difficulty, question_types}}` | `{success, quiz_id, questions(no answers), config, document_count}` |
| `/api/quiz/submit` | POST | `{quiz_id, answers: {q_index: [choice_idx, ...]}}` | `{success, score, total, per_question: [{correct, correct_answers, explanation}]}` |
| `/api/quiz/history` | GET | `?limit=` | `{history: [...], total}` |
| `/api/quiz/<id>/delete` | POST | — | `{success}` |

### Question object (stored internally)

```json
{
  "type": "single" | "multiple",
  "text": "…",
  "options": ["…", "…", "…", "…"],
  "answer": [2],
  "explanation": "…"
}
```

### History entry (`data/quiz_history.json`)

```json
{
  "id": "quiz_1723000000",
  "timestamp": "2026-08-13T…Z",
  "documents": ["lec1.pdf"],
  "config": {"num_questions": 5, "difficulty": "medium",
             "question_types": {"single": 3, "multiple": 2}},
  "questions": [ {…}, … ],
  "attempts": [{"timestamp": "…", "answers": {…}, "score": 4, "total": 5}]
}
```

- Default config: 5 questions, difficulty `medium`, mix `single:multiple = 3:2`.
- Ranges: num_questions 1–20; difficulty `easy|medium|hard`; question_types
  values must be non-negative integers summing to num_questions.
- Multi-select grading: full match only (partial credit = wrong).
- History listing strips answer keys (anti-cheat).
- Max 50 history entries, newest first, trimmed on save (same as summaries).

## 7. Frontend UX

- After generation, QuizViewer opens automatically: progress indicator
  (question x/N) + document names.
- Single = radio; multiple = checkbox with a "multiple choice" badge.
- Unanswered-question check on submit.
- Results view: big total score + per-question cards (correct/incorrect badge,
  my answers, correct answers, collapsible explanation).
- "Redo wrong questions" button: visible only when wrong answers exist; starts
  a new answering session with the wrong subset (frontend-only, no new history
  entry).
- After closing, the quiz remains accessible via history (QuizModal lists
  recent quizzes, same pattern as SummaryViewer history).

## 8. Error Handling

- 400: no documents selected; invalid config (num_questions/difficulty/
  question_types validation).
- 404: document not in index; unknown quiz_id on submit/delete.
- 500: LLM failure or JSON parse failure after one retry
  (`QuizGenerationError`).
- Frontend: `isGenerating` loading state (like summaryStore); retryable error
  message on LLM timeout/failure.

## 9. Testing

`tests/test_quiz.py`, mocking `call_llm`:

- Generate: valid JSON parse; invalid JSON retries once; insufficient question
  count; answer index out of range; missing documents → 400.
- Submit: all correct; all wrong; partial multi-select = wrong; unknown quiz_id
  → 404.
- History: save; list strips answer keys; trim at 50; delete unknown id → 404.
- Service-layer unit tests for `QuizGenerator`; view-layer tests via Django
  test client (`django.test.Client`, `DJANGO_SETTINGS_MODULE` per AGENTS.md).
