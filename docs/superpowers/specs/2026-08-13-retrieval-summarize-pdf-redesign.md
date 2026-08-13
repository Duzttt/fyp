# Retrieval-Based Summarize PDF Module Redesign

## Overview

Rebuild the existing summarize PDF module from scratch as a retrieval-based
topic summarizer. Instead of feeding whole documents to the LLM (with arbitrary
truncation), the new pipeline lets the LLM propose topics from sampled chunks,
retrieves the most relevant chunks for each topic via the existing hybrid
retriever (FAISS + BM25), summarizes each topic independently, and merges the
results into structured topic-based Markdown notes with page citations.

This design replaces the previous Studio summary tool spec
(`2026-06-15-studio-summary-tool-design.md`). The old document is superseded.

## Goals

- Summarize one indexed PDF's complete content via topic-directed retrieval.
- Discover topics automatically with LLM assistance (no manual topic input).
- Produce structured Markdown notes: overview plus one section per topic.
- Attach page citations to key points, taken from retrieved chunk metadata
  (never invented by the LLM).
- Stream stage progress and partial output over SSE.
- Auto-detect output language (Chinese/English) from the document.
- Use the global runtime LLM settings (no per-job provider/model selection).
- Store summary history in the database with a one-time migration of the old
  JSON history file.
- Fail with retryable errors; never silently fall back to extractive output.

## Non-Goals

- Multi-document synthesis or comparison.
- Conversational refinement of summaries.
- Markdown editing or checkpoints in the UI.
- Per-job provider/model/temperature selection.
- Celery/Redis or distributed execution.
- Resuming an individual LLM request after a Django process restart.
- Extractive fallback summarization.

## Pipeline

### 1. Load document

Resolve the document identifier against indexed chunks in the existing
`VectorStore`. Matching uses the canonical `source` field of chunks (exact
match), not substring matching. Chunks are ordered by page and then by stable
chunk order. A document with no indexed chunks fails with
`document_not_indexed`.

### 2. Language detection

Sample up to 10 chunks and compute the CJK character ratio. A ratio at or above
0.2 selects Chinese; otherwise English. Pure heuristic, no LLM call. The
detected language is stored on the job and used for prompts and output.

### 3. Topic discovery

Sample chunks evenly across pages (up to 10 chunks) and ask the LLM to propose
a JSON topic list. Each topic is `{"title": "...", "query": "...", "importance": 1-5}`.
The `query` is a retrieval-friendly phrase used in step 4. Default topic
counts by length preset: short 4, medium 8, detailed 12. `topic_limit` in
the job config overrides the default; values above 12 are rejected.

### 4. Per-topic retrieval and summary

For each topic:

- Retrieve top-k chunks with the hybrid retriever
  (`retrieval/hybrid_retriever.py`), restricted to the target document.
  `top_k` depends on the length preset: short 4, medium 6, detailed 8.
- The LLM summarizes the retrieved chunks into JSON: a section heading and
  3-8 key points. Each key point references supporting chunk IDs.
- Page numbers are resolved from chunk metadata, not from the LLM.

Topics run concurrently with a configurable bound (default 2-3). Each completed
topic emits a `partial` event carrying its Markdown section.

### 5. Merge and render

The LLM writes a 2-3 sentence overview from the topic summaries (one call).
The backend renders canonical Markdown from validated structured output:

- Overview paragraph
- One `##` section per topic
- Bulleted key points, each followed by page citations like `[p.12]`

The backend never trusts model-generated HTML. Topic summaries with empty
retrieval results are skipped with a warning; the job still completes if at
least one topic succeeded.

## Error Policy

- LLM failure, timeout, or malformed JSON (after one retry of the topic call)
  marks the job `failed` with a stable `error_code`. No extractive fallback.
- Empty retrieval for a topic: skip the topic, emit a warning, continue.
- Cancellation stops scheduling new topic calls and suppresses late commits.
- Completed partial output remains visible after failure and is labeled
  incomplete.

## Architecture

### Backend

#### `app/services/topic_summarizer.py` (new)

Pure pipeline logic: language detection, topic discovery prompts, per-topic
retrieval and summary, JSON parsing, Markdown rendering. Depends on
`retrieval/hybrid_retriever.py`, `app/services/llm_client.call_llm`, and
`app/services/vector_store.VectorStore`. No Django ORM usage.

#### `app/services/summary_job_service.py` (new)

Job lifecycle: validate documents and config, create jobs, submit to the
executor, handle retry and cancel, mark stale running/queued jobs
`interrupted` at startup.

#### `app/services/summary_executor.py` (new)

In-process `ThreadPoolExecutor`. Configurable global job concurrency (default
1) and per-job topic concurrency (default 2-3). Jobs are claimed atomically
before execution. The interface is isolated so a future Celery/RQ adapter can
replace it without changing API or frontend contracts.

#### `django_app/models.py`

Adds `SummaryJob` and `SummaryEvent` (see Data Model).

#### `django_app/views/summaries.py` (rewritten)

Jobs API plus SSE endpoint. Views validate requests and delegate to the job
service; they do not execute the pipeline inline.

#### Removed

- `app/services/summarizer.py` (old `DocumentSummarizer`) is deleted.
- `tests/test_summarizer.py` is deleted (replaced by new tests).
- Legacy endpoints `/api/summary/generate`, `/api/summary/history`,
  `/api/summary/delete`, `/api/summary/regenerate` are removed after the
  frontend stops calling them.

### Frontend

#### `SummaryModal.vue` / `SummaryViewer.vue` (rewritten)

Setup view (document, length preset) → generating view (stage progress bar,
partial topic output) → result view (topic-structured Markdown, page citation
jump to the existing PDF viewer).

#### `summaryStore.js` (rewritten)

Owns active job state, `EventSource` connection (reconnect with
`Last-Event-ID` replay), partial output, history loading, delete, and retry.

### SSE event types

`stage`, `progress`, `partial`, `completed`, `failed`, `cancelled`. The
database event ID is the SSE `id`. The endpoint replays persisted events after
`Last-Event-ID` before subscribing to new ones.

### Startup recovery

At Django startup, jobs left in `queued` or `running` are marked `interrupted`
and become retryable. Individual LLM calls are not resumed.

## Data Model

### `SummaryJob`

- `id`: UUID string
- `document_id`: string
- `status`: `queued`, `running`, `completed`, `failed`, `interrupted`,
  `cancelled`
- `stage`: current pipeline stage
- `progress`: integer 0-100
- `config`: JSON (length preset, topic limit, provider/model snapshot)
- `detected_language`: string (`zh` or `en`)
- `topics`: JSON (topic discovery result)
- `result_markdown`: text
- `result_json`: JSON (structured output)
- `citations`: JSON (key point → page references)
- `error_code`: string
- `error_message`: text
- `created_at`, `started_at`, `completed_at`, `updated_at`

### `SummaryEvent`

- `id`: auto-increment (used as SSE id)
- `job`: FK
- `event_type`: `stage`, `progress`, `partial`, `completed`, `failed`,
  `cancelled`
- `stage`: string
- `payload`: JSON
- `created_at`

## API

### `POST /api/summary/jobs`

Request:

```json
{
  "document_id": "lecture-4.pdf",
  "config": {
    "length": "medium"
  }
}
```

Response contains the job and an estimate (topic count, expected LLM calls).
Validates that the document is indexed. Jobs are queued immediately.

### `GET /api/summary/jobs`

Shared history with pagination (`limit`, default 20, max 50), ordered newest
first. Includes status, document name, and a preview of the summary.

### `GET /api/summary/jobs/{id}`

Full job state including topics, Markdown result, citations, and error
information.

### `GET /api/summary/jobs/{id}/events`

SSE endpoint with `Last-Event-ID` replay and live subscription.

### `POST /api/summary/jobs/{id}/cancel`

Sets cancel state; the executor stops scheduling new topic calls.

### `POST /api/summary/jobs/{id}/retry`

Re-runs the pipeline for failed/interrupted jobs. Retry is rejected for
running or queued jobs.

### `DELETE /api/summary/jobs/{id}`

Deletes the job and its events. Running jobs must be cancelled first.

## Migration

One-time migration of `data/summary_history.json`:

- Each entry becomes one `completed` `SummaryJob` with
  `result_markdown = summary`, preserved `citations` and `config`, and the
  first document name as `document_id` (multi-document entries keep the
  combined summary text and note the document list in `config`).
- Malformed entries are skipped with a logged warning.
- The JSON file is kept as a backup; new writes use the database only.

Implemented as a Django data migration or a management command.

## Testing Strategy

### Unit tests

- Language detection thresholds
- Topic discovery prompt construction and JSON parsing
- Document chunk loading and ordering
- Retrieval filtering per document
- Markdown rendering from structured output
- Job state transitions and cancellation checks
- Startup interruption recovery

### Service tests (mocked LLM and retriever)

- Full pipeline success (single document)
- Malformed topic JSON with one retry, then failure
- LLM timeout and provider failure
- Empty retrieval for a topic (skip with warning)
- Cancellation during topic generation
- Partial output event publication

### API tests

- Job creation and estimate
- Job detail and history pagination
- SSE replay with `Last-Event-ID`
- Cancel, retry, and delete
- Legacy JSON history migration

### Frontend tests

- Store state and SSE reconnect with replay
- Progress and partial output rendering
- History view, delete, and retry actions
- Page citation jump to PDF viewer

## Acceptance Criteria

- A selected PDF is summarized through topic-directed retrieval without
  document truncation.
- Topics are discovered automatically; no manual topic input is required.
- The result is structured Markdown: overview plus per-topic sections.
- Key points carry page citations resolved from chunk metadata.
- Selecting a citation opens the PDF viewer at the cited page.
- Progress and per-topic partial output stream over SSE while the job runs.
- Output language is auto-detected from the document.
- Summary history is database-backed with view, delete, and retry actions.
- LLM failures produce retryable errors and never extractive fallback.
- Interrupted jobs are marked after restart and can be retried.
