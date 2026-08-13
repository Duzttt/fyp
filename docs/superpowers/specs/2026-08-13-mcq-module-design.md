# MCQ Generation Module Design

Date: 2026-08-13
Status: Approved

## Overview

Add a full-stack "Generate MCQ" module to the Lecture Note Q&A system: the user
selects documents in the Studio panel, opens the MCQ tool, configures question
count and difficulty, and the LLM generates multiple-choice questions (4 options,
1 correct answer, explanation) grounded in the selected documents. The user takes
the quiz interactively (one-shot submit grading) and both quizzes and attempt
results are persisted in the database.

The module mirrors the existing `summary` feature pattern (service + view +
Pinia store + studio modal/viewer) and reuses the shared LLM routing
(`app/services/llm_client.py`) and vector-store document text extraction
(`django_app/views/summaries.py` pattern).

## Architecture

### Backend

| File | Responsibility |
|---|---|
| `app/services/mcq_generator.py` | `MCQGeneratorService` + `MCQGenerationError`. LLM JSON generation, parsing, validation, retry, timeout (Windows threading pattern, same as `question_suggestions.py`). |
| `django_app/models.py` | New `MCQQuiz` and `MCQAttempt` models (appended to existing file). |
| `django_app/views/mcq.py` | POST generate, GET history, GET quiz, POST attempt (server-side grading), DELETE quiz. |
| `django_backend/urls.py` | Route registrations for the endpoints above, with and without trailing slash (existing convention). |

### Frontend

| File | Responsibility |
|---|---|
| `frontend/src/services/api.js` | Five API functions: `generateMcq`, `getMcqHistory`, `getMcq`, `submitMcqAttempt`, `deleteMcq`. |
| `frontend/src/stores/mcqStore.js` | Pinia store mirroring `summaryStore.js`: `currentQuiz`, `history`, `isGenerating`, `error`, `generate()`, `loadHistory()`, `submit()`, `remove()`. |
| `frontend/src/components/studio/McqModal.vue` | Config modal: question count (5/10/15), difficulty (mixed/easy/medium/hard), selected document count. |
| `frontend/src/components/studio/QuizViewer.vue` | Quiz flow: questions with option radios, Submit (disabled until all answered), results view (per-question correct/incorrect + explanation + total score). |
| `frontend/src/components/layout/StudioPanel.vue` | Remove `comingSoon: true` from the existing "Generate MCQ" tool card and wire it into the modal flow (like the summary tool). |

## Data Flow

### Generation

```
StudioPanel MCQ card -> McqModal (count/difficulty) -> mcqStore.generate(docIds, config)
  -> POST /api/mcq/generate
    -> view extracts selected document texts from VectorStore (mirror _get_document_text in summaries.py)
    -> MCQGeneratorService.generate_mcqs()
      -> build prompt -> call_llm(response_format="json", provider routing local_llm/gemini/openrouter)
      -> parse JSON (strip code fences -> json.loads) -> validate (4 options / A-D answer / non-empty / count) -> retry up to 2 times on failure
    -> save MCQQuiz -> return quiz WITHOUT correct answers
  -> QuizViewer opens
```

### Attempt

```
QuizViewer all answered -> Submit -> mcqStore.submit(quizId, answers)
  -> POST /api/mcq/<id>/attempt -> server compares answers -> save MCQAttempt
  -> returns {score, percentage, results: [{correct_answer, explanation, is_correct}]}
  -> results view shows per-question feedback + total score
```

## API Contract

| Endpoint | Method | Request | Response highlights |
|---|---|---|---|
| `/api/mcq/generate` | POST | `{document_ids: [], num_questions: 5, difficulty: "mixed"}` | `{success, quiz_id, questions: [{id, question, options: {"A".."D": str}, difficulty, source_doc}], document_count}` |
| `/api/mcq/<quiz_id>` | GET | - | Same shape as generate response (for retaking) |
| `/api/mcq/<quiz_id>/attempt` | POST | `{answers: [{question_id, selected}]}` | `{success, score, total, percentage, results: [...]}` |
| `/api/mcq/history` | GET | `?limit=20` | `{quizzes: [{id, question_count, difficulty, documents, created_at, best_score}]}` |
| `/api/mcq/<quiz_id>` | DELETE | - | `{success, message}` |

Validation rules:

- `num_questions` clamped to 1-20 (default 5).
- `difficulty` must be one of `mixed|easy|medium|hard`.
- Attempt answers must cover all questions; `selected` must be one of A-D.
- `options` are serialized as a dict `{"A": str, "B": str, "C": str, "D": str}`
  in both the LLM schema, the DB, and API responses (single format everywhere).

### MCQ JSON schema (LLM output)

```json
{
  "questions": [
    {
      "question": "string",
      "options": {"A": "string", "B": "string", "C": "string", "D": "string"},
      "correct_answer": "A-D",
      "explanation": "string",
      "difficulty": "easy|medium|hard",
      "source_doc": "string"
    }
  ]
}
```

### Django Models

`MCQQuiz`:

- `questions`: JSONField (list of MCQ dicts, correct answers included internally)
- `document_names`: TextField (comma-separated)
- `difficulty`: CharField with choices (mixed/easy/medium/hard)
- `question_count`: IntegerField
- `llm_provider`: CharField
- `created_at` / `updated_at`: DateTimeField
- Index on `-created_at`

`MCQAttempt`:

- `quiz`: ForeignKey(MCQQuiz, on_delete=CASCADE, related_name="attempts")
- `answers`: JSONField (list of `{question_id, selected}`)
- `score`: IntegerField
- `total`: IntegerField
- `created_at`: DateTimeField
- Index on `-created_at`

Migration required for both models.

## Grading

Server-side: the generate/GET endpoints never expose correct answers. The attempt
endpoint compares submitted answers against stored questions, persists the
attempt, and returns per-question results (correct answer, explanation,
is_correct) plus the score.

## Key Decisions

- No template fallback: MCQs cannot be produced with plausible distractors via
  templates, so LLM failure returns an error instead of degraded output.
- Server-side grading keeps answer records consistent and cheat-proof.
- Persistence uses Django models (not JSON files) per requirement to save
  quizzes and attempt records.

## Error Handling

- Views (AGENTS.md pattern): 400 for missing/invalid parameters, 404 for no
  valid documents or unknown quiz id, 500 for `MCQGenerationError` / unknown
  exceptions, all via `_error_response(detail, status)`.
- Service: `MCQGenerationError` custom exception; LLM timeout default 60s
  (Windows threading pattern); JSON parse or structure validation failure
  retries up to 2 times, then raises; insufficient question count raises
  (no silent truncation).
- Frontend: store records `error`; QuizViewer renders error state with a retry
  action; generate button disabled while in-flight.

## Testing

Mirrors `tests/test_question_suggestions.py`, `tests/test_django_suggestions.py`,
`tests/test_summarizer.py`.

| File | Coverage |
|---|---|
| `tests/test_mcq_generator.py` | Prompt building (doc context/difficulty/count); JSON parsing (valid, fenced, invalid, truncated); structure validation (option count, answer range, count mismatch); retry logic (mocked call_llm fails then succeeds); timeout (mocked slow call); provider routing. |
| `tests/test_mcq_views.py` | Django Client with mocked service: generate success/400/404; attempt grading correctness (all correct/partial/all wrong); history; delete; incomplete answers -> 400. |
| `tests/test_mcq_models.py` | MCQQuiz/MCQAttempt creation, cascade delete of attempts, best_score aggregation. |

Frontend has no test infra (no vitest config); verified manually via dev server,
consistent with existing frontend practice. Backend command:
`pytest tests/test_mcq_generator.py tests/test_mcq_views.py tests/test_mcq_models.py`
