# Studio Summary Tool Design

## Overview

Redesign the existing Studio summary feature into a persistent, background-capable
workspace for summarizing entire selected PDFs with an LLM. The tool supports
hierarchical long-document summarization, combined and per-document output,
claim-level citations, live progress and partial output, Markdown editing,
conversational refinement, and shared summary history.

This design extends the existing Vue Studio panel, Pinia summary store, Django
summary endpoints, and `DocumentSummarizer`. It does not introduce a second
summary feature or require Redis/Celery for the initial implementation.

## Goals

- Summarize the complete content of any number of selected indexed PDFs.
- Offer study notes, academic, executive, and bullet formats.
- Produce a combined overview followed by per-document sections.
- Attach verified source and page citations to key claims.
- Let users select provider, model, quality preset, temperature, and token limit.
- Continue generation when the Studio drawer is closed.
- Stream stage progress and partial output.
- Support conversational refinement and direct Markdown editing.
- Auto-save generated versions and save direct edits through explicit checkpoints.
- Store shared application history in the database.
- Open cited PDFs at the supporting page and highlight the evidence.

## Non-Goals

- Multi-user ownership or access control.
- Distributed workers or horizontal job execution.
- Resuming an individual LLM request after a Django process restart.
- Silent extractive summarization when LLM generation fails.
- Unlimited concurrent LLM requests.
- Arbitrary filesystem access through document identifiers.

## User Experience

### Entry Point

The existing **Summarize PDF** card remains in `StudioPanel.vue`. It displays the
number of selected documents. Selecting it opens a wide slide-over drawer from
the right. Sources and part of Chat remain visible behind the drawer.

If no documents are selected, the card presents an inline or toast-level
instruction rather than a blocking browser alert.

### Drawer States

The drawer has five primary states:

1. **Setup**
2. **Awaiting confirmation**
3. **Generating**
4. **Completed**
5. **Failed, interrupted, or cancelled**

Closing the drawer does not cancel an active job. Reopening the drawer restores
the latest active job and its current state.

### Setup

The setup view shows:

- Selected documents
- Automatically detected output language with a manual override
- Output format: study notes, academic, executive, or bullets
- Length: short, medium, or detailed
- Provider
- Model
- Quality preset: Fast, Balanced, or Best
- Temperature
- Maximum output tokens
- Include citations
- Include comparison

Provider and model are selected for each summary job and do not mutate global LLM
settings. Advanced controls remain available regardless of preset. Changing an
advanced value marks the configuration as custom.

### Workload Estimation

Before scheduling, the server estimates:

- Document count
- Source chunk count
- Planned section groups
- Expected LLM call count
- Estimated input and output tokens
- Approximate execution time

The design has no fixed document-count limit. Server-side safety limits still
bound total tokens, section count, and concurrent calls. Jobs above configurable
confirmation thresholds enter `awaiting_confirmation`. The drawer presents the
estimate and requires explicit confirmation before work starts.

### Progress and Partial Output

The generation view shows these stages:

1. Preparing documents
2. Summarizing sections
3. Synthesizing each document
4. Creating the combined synthesis
5. Verifying citations
6. Finalizing output

Each stage exposes status and progress. Completed section and document summaries
appear as partial output while later stages continue. Partial content is labeled
as incomplete and is not treated as a saved generated version.

### Completed Result

The completed view shows:

1. Combined overview
2. Key concepts
3. Agreements, differences, and complementary points
4. Per-document sections
5. Conclusions
6. Verified citations

The result can be copied or exported as Markdown.

### Editing

Editing uses a split view:

- Left: Markdown editor
- Right: live sanitized preview

Generated versions are immutable. Direct edits exist as a local draft until the
user selects **Save checkpoint**. A checkpoint stores the current Markdown,
name, timestamp, and source generated version.

If the user closes the drawer with unsaved direct edits, the client warns before
discarding them. Closing the drawer during generation does not show this warning.

### Conversational Refinement

A refinement input appears below the editor and preview. Instructions such as
“focus on methodology” or “shorten the conclusions” create a new generated
version. The request includes the selected source version, instruction, current
job configuration, and verified source context.

Refinement never silently overwrites a manual draft. If unsaved edits exist, the
user must either save a checkpoint, discard the draft, or refine from the last
saved version.

### History

History is shared across the application and database-backed. It includes:

- Summary jobs
- Immutable generated versions
- Refinement versions
- Named manual checkpoints
- Model and configuration metadata
- Status and diagnostic information

Users can reopen, rename, export, retry, or delete history entries. The user-facing
job title and checkpoint names are renamable; immutable generated versions are
identified by their sequence, kind, and creation time.
Deleting a job deletes its versions, checkpoints, and events after confirmation.

### Citation Navigation

Each key claim may contain one or more citation markers. Selecting a citation:

1. Opens the existing PDF viewer.
2. Navigates to the cited page.
3. Highlights the verified supporting passage.

If highlighting fails, the viewer still opens the cited page and displays the
evidence text in the citation details.

## Architecture

### Frontend Components

#### `StudioPanel.vue`

- Keeps the Studio tool entry point.
- Opens and closes the summary drawer.
- Does not own job execution state.

#### `SummaryDrawer.vue`

New top-level summary workspace containing:

- Setup and estimate view
- Progress timeline
- Partial result view
- Result and history views
- Editor/preview split
- Refinement controls
- Failure and retry states

#### Focused Child Components

- `SummaryJobSetup.vue`
- `SummaryProgress.vue`
- `SummaryResult.vue`
- `SummaryMarkdownEditor.vue`
- `SummaryRefinement.vue`
- `SummaryHistory.vue`
- `SummaryCitation.vue`

Each component receives explicit data and emits actions. It does not call APIs
directly.

#### `summaryStore.js`

The Pinia store owns:

- Active job ID
- Jobs and statuses
- Workload estimates
- Ordered SSE events
- Partial output
- Generated versions
- Checkpoints
- Current editor draft
- Unsaved-draft state
- History loading and selection

The store remains active when the drawer closes. It reconnects to an active
job's SSE stream after drawer reopening or page restoration.

### Backend Components

#### Summary Views

Django views validate requests, enforce HTTP contracts, serialize models, and
delegate work to the job service. They do not execute the summarization pipeline
inline.

#### `SummaryJobService`

Responsibilities:

- Validate documents and configuration
- Resolve provider and model
- Estimate workload
- Decide whether confirmation is required
- Create jobs and attempts
- Submit work to the executor
- Handle retry and cancellation requests
- Mark stale running jobs interrupted during startup recovery

#### `HierarchicalSummarizer`

Responsibilities:

- Load complete indexed document chunks
- Preserve document and page order
- Group chunks into bounded semantic sections
- Summarize sections
- Synthesize each document
- Produce the combined summary
- Generate structured claim-to-evidence candidates
- Verify citations
- Render canonical Markdown

`DocumentSummarizer` remains the LLM generation unit or is decomposed into
prompt-oriented helpers used by `HierarchicalSummarizer`. Job persistence,
scheduling, and event publication do not belong in `DocumentSummarizer`.

#### In-Process Executor

A process-local bounded executor runs summary jobs. Default concurrency is low
and configurable. Section-level concurrency is also bounded.

The executor is suitable for the current single-instance application. Its
interface is isolated so a future Celery/RQ adapter can replace it without
changing API or frontend contracts.

On Django startup, jobs left in active states are marked `interrupted`. They can
be retried from the UI. The system does not claim to resume the interrupted LLM
call.

#### Event Publisher

Pipeline stages append `SummaryEvent` records transactionally. SSE subscribers
receive persisted events in order. Persisting events enables replay after a
temporary connection loss.

## Data Model

### `SummaryJob`

Fields:

- `id`: UUID
- `status`: `estimating`, `awaiting_confirmation`, `queued`, `running`,
  `completed`, `failed`, `interrupted`, or `cancelled`
- `stage`: current pipeline stage
- `progress`: integer from 0 to 100
- `document_ids`: JSON list of indexed document identifiers
- `document_count`
- `configuration`: validated JSON configuration
- `detected_language`
- `workload_estimate`: JSON estimate
- `title`: user-facing history title
- `active_version`: nullable foreign key
- `active_attempt`: nullable foreign key
- `cancel_requested`
- `created_at`, `confirmed_at`, `started_at`, `completed_at`, `updated_at`

### `SummaryAttempt`

Fields:

- `id`: UUID
- `job`: foreign key
- `sequence`: increasing attempt number within the job
- `kind`: `initial`, `retry`, or `refinement`
- `source_version`: nullable foreign key
- `refinement_instruction`: nullable text
- `status`: `queued`, `running`, `completed`, `failed`, `interrupted`, or
  `cancelled`
- `stage`
- `progress`
- `configuration`: resolved provider, model, preset, and generation parameters
- `error_code`
- `error_message`
- `created_at`, `started_at`, `completed_at`, `updated_at`

Attempts preserve the settings and diagnostics from failed, interrupted, retried,
and refined runs. `SummaryJob` exposes the state of its active attempt for
convenient client rendering.

### `SummaryVersion`

Fields:

- `id`: UUID
- `job`: foreign key
- `attempt`: foreign key
- `parent_version`: nullable self-reference
- `kind`: `initial` or `refinement`
- `refinement_instruction`: nullable text
- `title`
- `markdown`
- `structured_output`: JSON
- `citations`: JSON
- `provider`
- `model`
- `generation_parameters`: JSON
- `token_usage`: JSON
- `created_at`

Generated versions are immutable.

### `SummaryCheckpoint`

Fields:

- `id`: UUID
- `job`: foreign key
- `source_version`: foreign key
- `name`
- `markdown`
- `created_at`, `updated_at`

Checkpoint Markdown is mutable through an explicit update action. A checkpoint
is never created automatically from unsaved editor state.

### `SummaryEvent`

Fields:

- `id`: monotonically increasing database identifier
- `job`: foreign key
- `event_type`: `stage`, `progress`, `partial`, `warning`, `completed`,
  `failed`, `interrupted`, or `cancelled`
- `stage`
- `payload`: JSON
- `created_at`

The database event ID is used as the SSE `id`.

## API

### Jobs

#### `POST /api/summary/jobs`

Request:

```json
{
  "document_ids": ["lecture-4.pdf", "paper.pdf"],
  "configuration": {
    "format": "academic",
    "length": "medium",
    "language": "auto",
    "provider": "local_llm",
    "model": "configured-model",
    "quality_preset": "balanced",
    "temperature": 0.3,
    "max_output_tokens": 2048,
    "include_citations": true,
    "include_comparison": true
  }
}
```

The response contains the job, workload estimate, and whether confirmation is
required. Normal jobs are queued immediately. Large jobs remain
`awaiting_confirmation`.

#### `POST /api/summary/jobs/{id}/confirm`

Confirms and queues an estimated large job. Reconfirmation is rejected once work
has started.

#### `GET /api/summary/jobs`

Returns shared job history with status, document names, active version summary,
and pagination.

#### `GET /api/summary/jobs/{id}`

Returns the complete job state, active version, estimate, partial-output
snapshot, and available actions.

#### `GET /api/summary/jobs/{id}/events`

SSE endpoint. Supports `Last-Event-ID` and replays later persisted events before
subscribing for new events. The client uses status polling if SSE is unavailable.

#### `POST /api/summary/jobs/{id}/cancel`

Sets `cancel_requested`. The worker stops scheduling new calls and ignores late
results after cancellation.

#### `POST /api/summary/jobs/{id}/retry`

Creates a new `SummaryAttempt` under the same job identity, preserving prior
attempt settings, events, and diagnostics.
Retry may use updated provider/model settings supplied in the request.

#### `DELETE /api/summary/jobs/{id}`

Deletes the job and dependent versions, checkpoints, and events after validation.
Running jobs must be cancelled before deletion.

### Versions and Refinement

#### `POST /api/summary/jobs/{id}/refine`

Request:

```json
{
  "source_version_id": "uuid",
  "instruction": "Focus on methodology and shorten the conclusion.",
  "configuration_override": {
    "model": "another-model"
  }
}
```

Creates a background refinement attempt and eventually a child
`SummaryVersion`. The completed job remains readable while the refinement
attempt runs; the new version becomes active only after successful completion.

### Checkpoints

#### `POST /api/summary/versions/{id}/checkpoints`

Creates a named Markdown checkpoint.

#### `PATCH /api/summary/checkpoints/{id}`

Renames or explicitly updates a checkpoint.

#### `DELETE /api/summary/checkpoints/{id}`

Deletes a checkpoint without deleting its source generated version.

## Hierarchical Summarization Pipeline

### Document Loading

Document identifiers are resolved only against indexed chunks. Matching uses a
canonical document identifier rather than substring path matching.

Chunks are loaded in document order and sorted by page plus stable chunk order.
The pipeline uses the complete indexed content, not only RAG-selected passages.

### Section Grouping

Chunks are grouped into token-bounded sections while preserving paragraph chunk
boundaries. Group sizing depends on the selected model context window and quality
preset.

The grouping output records all source chunk IDs and page ranges used by each
section.

### Section Summaries

Each section call returns structured JSON containing:

- Section heading
- Main ideas
- Definitions and terminology
- Methods or evidence
- Findings or conclusions
- Candidate claims with supporting chunk IDs

Section calls run concurrently up to a configurable per-job limit. Completed
sections emit partial events.

### Document Synthesis

Section summaries are synthesized into one structured summary per document.
When the intermediate content exceeds the model context window, synthesis uses
additional reduction levels rather than truncating content.

### Combined Synthesis

The final synthesis produces:

- Title
- Combined overview
- Key concepts
- Agreements and differences
- Complementary points
- Per-document sections
- Conclusions
- Claim-to-evidence references

The selected output format changes presentation and emphasis, not the evidence
requirements.

### Language

Language is detected from representative text across the selected documents.
If a dominant language is clear, output uses that language. Mixed or ambiguous
sets default to English and emit a warning. The setup estimate displays the
detected choice and permits manual override before confirmation.

### Model Controls

The provider/model catalogue comes from existing runtime provider discovery.
Quality presets configure defaults:

- **Fast**: larger sections, lower section concurrency cost, compact output
- **Balanced**: moderate section sizes and synthesis depth
- **Best**: smaller sections, stronger synthesis model settings, and deeper
  citation verification

Temperature and output-token controls are validated against server limits.

## Output Contract

Canonical structured output:

```json
{
  "title": "string",
  "combined_overview": "string",
  "key_concepts": [
    {
      "term": "string",
      "explanation": "string",
      "claim_ids": ["claim-1"]
    }
  ],
  "agreements_and_differences": {
    "agreements": [],
    "differences": [],
    "complementary_points": []
  },
  "per_document_sections": [
    {
      "document_id": "string",
      "title": "string",
      "summary": "string",
      "key_points": [],
      "claim_ids": []
    }
  ],
  "conclusions": "string",
  "claims": [
    {
      "id": "claim-1",
      "text": "string",
      "evidence": [
        {
          "chunk_id": "string",
          "source": "string",
          "page": 8,
          "quote": "string",
          "highlight_text": "string"
        }
      ],
      "verified": true
    }
  ],
  "markdown": "string"
}
```

The server renders canonical Markdown from validated structured output. It does
not trust model-generated HTML.

## Citation Verification

Every citation must resolve to indexed source content.

Verification:

1. Resolve referenced chunk IDs.
2. Confirm source and page metadata.
3. Check the candidate quote against normalized chunk text.
4. Measure lexical support between the claim and evidence.
5. Retain citations meeting the configured threshold.
6. Mark claims without sufficient support as unverified.

Unsupported citations are removed. The UI labels unverified claims and does not
make them clickable.

Quotes and highlight text are escaped and length-limited.

## Background Execution and Recovery

- The executor uses configurable global and per-job concurrency.
- Jobs are claimed atomically before running.
- Progress is persisted after each meaningful step.
- Closing the drawer has no effect on execution.
- Cancellation prevents new work and suppresses late result commits.
- On application startup, stale `queued` or `running` jobs become `interrupted`.
- Retry preserves the failed/interrupted attempt's events and diagnostics.
- A single application instance is assumed for the initial executor.

## Error Handling

The system never silently substitutes extractive output.

Failures include stable codes for:

- Invalid document selection
- Missing indexed content
- Invalid provider/model
- Provider unavailable
- Timeout
- Context or token limit exceeded
- Malformed structured output
- Citation verification failure
- Cancellation
- Server interruption

Completed partial results remain visible after a failure and are labeled
incomplete. Users can retry with the same or changed model settings.

If citation verification fails for only some claims, the job may complete with a
warning and unverified claims. If the structured result cannot be validated or
rendered, the job fails.

## Security and Content Safety

- Provider credentials never leave the backend.
- Document IDs resolve through indexed metadata; arbitrary paths are rejected.
- Document text is clearly delimited as untrusted content in prompts.
- System instructions explicitly ignore instructions found inside documents.
- Markdown preview is sanitized.
- Model output is parsed as structured data before rendering.
- Citation quotes are escaped and bounded.
- API values are validated against provider, model, token, temperature, and
  workload limits.

## Migration

The existing `data/summary_history.json` history is migrated through a one-time
Django data migration or explicit management command.

Migration rules:

- Create completed jobs for valid history entries.
- Create one initial generated version per entry.
- Preserve documents, timestamps, configuration, summary Markdown, citations,
  and comparison data where available.
- Skip malformed entries with a logged warning.
- Keep the JSON file as a backup; new writes use the database only.

The legacy `/api/summary/generate`, history, delete, and regenerate endpoints may
temporarily delegate to the new services or return compatibility responses. They
are removed only after the Vue frontend no longer calls them.

## Testing Strategy

### Unit Tests

- Configuration validation and preset resolution
- Workload estimation and confirmation thresholds
- Canonical document resolution
- Token-bounded section grouping
- Multi-level reduction without truncation
- Language detection and override
- Output parsing and Markdown rendering
- Citation verification
- Job state transitions
- Cancellation checks
- Startup interruption recovery

### Service Tests

Use mocked LLM calls to test:

- Successful single- and multi-document jobs
- Partial event publication
- Malformed JSON
- Provider timeout
- Invalid model
- Retry with changed settings
- Cancellation during section generation
- Refinement version creation
- Unsupported citation removal

### Django API Tests

- Job creation and estimation
- Large-job confirmation
- History pagination
- Job detail
- SSE replay with `Last-Event-ID`
- Polling fallback data
- Cancel, retry, and delete
- Refinement
- Checkpoint create, update, and delete
- Legacy-history migration

### Frontend Tests

- Drawer open and restore behavior
- Generation continuing after drawer close
- Provider/model and advanced controls
- Large-job confirmation
- Stage progress and partial output
- SSE reconnect and polling fallback
- Split Markdown editor and preview
- Unsaved-edit warning
- Checkpoint saving
- Refinement with unsaved edits
- Shared history actions
- Citation navigation and highlighting
- Accessible keyboard and focus behavior

### End-to-End Test

Select multiple PDFs, configure a model, confirm a large estimate if required,
observe streamed section progress, receive combined and per-document output,
open a citation at the correct PDF page, refine the summary, edit Markdown, save
a checkpoint, close and reopen the drawer, and restore the saved result.

## Acceptance Criteria

- Entire indexed PDFs are summarized through a hierarchical pipeline without
  fixed document-count truncation.
- Large workloads require explicit confirmation and show an estimate.
- The user can select provider, model, preset, temperature, and token limit.
- A completed result contains combined and per-document sections.
- Key claims expose verified page-level citations.
- Citation selection opens and highlights the source PDF passage.
- Progress and partial results stream while work runs.
- Closing the drawer does not cancel the job.
- Generated versions are auto-saved in shared database history.
- Conversational refinement creates a child generated version.
- Direct Markdown edits are saved only through explicit checkpoints.
- LLM failures show retryable errors and never silently produce extractive output.
- Interrupted jobs are identified after restart and can be retried.
