# Studio Summary Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a durable Studio summary workflow that uses the configured LLM to hierarchically summarize complete selected PDFs, produces verified page-level citations, supports background jobs and live progress, and provides editable, refinable, shared summary history.

**Architecture:** Add database-backed summary jobs, attempts, generated versions, editable checkpoints, and persisted events. A bounded in-process executor runs a hierarchical summarization pipeline and publishes replayable Server-Sent Events, while the Vue Studio drawer consumes the API, restores background jobs, renders canonical Markdown, and routes verified citations into one shared PDF viewer.

**Tech Stack:** Python 3.9, Django, Pydantic, FAISS-backed `VectorStore`, existing `call_llm` provider router, pytest, Vue 3, Pinia, Vite, Vitest, Vue Test Utils, MarkdownIt, DOMPurify.

---

## File Map

### Backend

- Modify `app/config.py`: summary worker, sectioning, confirmation, and token-limit settings.
- Add `app/models/summary.py`: validated request, estimate, partial result, citation, and final output contracts.
- Modify `app/models/__init__.py`: export summary contracts.
- Add `app/services/summary_config.py`: presets, request validation, and deterministic workload estimation.
- Add `app/services/summary_documents.py`: canonical document resolution, chunk grouping, section creation, and language selection.
- Modify `app/services/summarizer.py`: strict structured LLM calls with explicit errors and no extractive fallback.
- Add `app/services/summary_citations.py`: resolve and verify model evidence references.
- Add `app/services/hierarchical_summarizer.py`: section, document, and collection synthesis pipeline.
- Add `app/services/summary_jobs.py`: state transitions, bounded executor, event persistence, cancellation, retry, refinement, and stale-job recovery.
- Modify `django_app/models.py`: durable summary entities.
- Add `django_app/migrations/0005_summary_jobs.py`: schema migration.
- Add `django_app/views/summary_jobs.py`: REST and SSE endpoints.
- Modify `django_app/views/summaries.py`: compatibility adapters backed by the new models.
- Modify `django_app/views/__init__.py`: export new handlers.
- Modify `django_backend/urls.py`: register summary job routes.
- Modify `django_app/apps.py` and `django_backend/settings.py`: guarded stale-job recovery at process startup.
- Add `django_app/management/commands/migrate_summary_history.py`: one-time JSON history import.

### Backend tests

- Add `tests/test_summary_models.py`
- Add `tests/test_summary_config.py`
- Add `tests/test_summary_documents.py`
- Modify `tests/test_summarizer.py`
- Add `tests/test_summary_citations.py`
- Add `tests/test_hierarchical_summarizer.py`
- Add `tests/test_summary_jobs.py`
- Add `tests/test_summary_job_views.py`
- Add `tests/test_summary_history_migration.py`

### Frontend

- Modify `frontend/package.json`, `frontend/package-lock.json`, and `frontend/vite.config.js`: add Vitest test harness.
- Add `frontend/src/test/setup.js`
- Add `frontend/src/services/summaryApi.js`: typed-in-practice summary job API and SSE client.
- Rewrite `frontend/src/stores/summaryStore.js`: job lifecycle, history, streaming, local drafts, and checkpoints.
- Add `frontend/src/stores/pdfViewerStore.js`: application-level PDF navigation state.
- Modify `frontend/src/App.vue`, `frontend/src/components/chat/ChatPanel.vue`, and `frontend/src/composables/useChatState.js`: use one shared PDF viewer.
- Add `frontend/src/components/studio/SummaryDrawer.vue`
- Add `frontend/src/components/studio/SummaryJobSetup.vue`
- Add `frontend/src/components/studio/SummaryProgress.vue`
- Add `frontend/src/components/studio/SummaryHistory.vue`
- Add `frontend/src/components/studio/SummaryResult.vue`
- Add `frontend/src/components/studio/SummaryMarkdownEditor.vue`
- Add `frontend/src/components/studio/SummaryRefinement.vue`
- Add `frontend/src/components/studio/SummaryCitation.vue`
- Modify `frontend/src/components/layout/StudioPanel.vue`: launch the drawer.
- Delete `frontend/src/components/studio/SummaryModal.vue` and `frontend/src/components/studio/SummaryViewer.vue` after replacement.

### Frontend tests

- Add `frontend/src/services/summaryApi.test.js`
- Add `frontend/src/stores/summaryStore.test.js`
- Add `frontend/src/stores/pdfViewerStore.test.js`
- Add `frontend/src/components/studio/SummaryDrawer.test.js`
- Add `frontend/src/components/studio/SummaryMarkdownEditor.test.js`
- Add `frontend/src/components/studio/SummaryCitation.test.js`

## API Contract

Use these routes consistently in backend and frontend work:

```text
POST   /api/summary/jobs
GET    /api/summary/jobs
GET    /api/summary/jobs/<job_id>
PATCH  /api/summary/jobs/<job_id>
DELETE /api/summary/jobs/<job_id>
GET    /api/summary/jobs/<job_id>/events
POST   /api/summary/jobs/<job_id>/confirm
POST   /api/summary/jobs/<job_id>/cancel
POST   /api/summary/jobs/<job_id>/retry
POST   /api/summary/jobs/<job_id>/refine
POST   /api/summary/versions/<version_id>/checkpoints
PATCH  /api/summary/checkpoints/<checkpoint_id>
DELETE /api/summary/checkpoints/<checkpoint_id>
```

Job statuses are:

```text
estimating, awaiting_confirmation, queued, running, completed, failed,
cancelled, interrupted
```

Event types are:

```text
job.created, job.confirmation_required, job.queued, job.started,
stage.started, stage.progress, partial.section, partial.document,
warning, version.created, job.completed, job.cancel_requested, job.cancelled,
job.failed, job.interrupted
```

## Task 1: Add Durable Summary Models

**Files:**
- Modify: `django_app/models.py`
- Create: `django_app/migrations/0005_summary_jobs.py`
- Test: `tests/test_summary_models.py`

- [ ] **Step 1: Write failing model lifecycle tests**

```python
from django.test import TestCase

from django_app.models import (
    SummaryAttempt,
    SummaryCheckpoint,
    SummaryEvent,
    SummaryJob,
    SummaryVersion,
)


class SummaryModelTests(TestCase):
    def test_job_attempt_version_and_checkpoint_relationships(self) -> None:
        job = SummaryJob.objects.create(
            status=SummaryJob.Status.QUEUED,
            title="Lecture summary",
            document_ids=["lecture-1.pdf"],
            configuration={"format": "study_notes"},
            estimate={"estimated_calls": 4},
        )
        attempt = SummaryAttempt.objects.create(
            job=job,
            sequence=1,
            kind=SummaryAttempt.Kind.INITIAL,
        )
        version = SummaryVersion.objects.create(
            job=job,
            attempt=attempt,
            kind=SummaryVersion.Kind.INITIAL,
            structured_output={"title": "Lecture summary"},
            markdown="# Lecture summary",
        )
        checkpoint = SummaryCheckpoint.objects.create(
            job=job,
            source_version=version,
            name="My edits",
            markdown="# Edited summary",
        )
        event = SummaryEvent.objects.create(
            job=job,
            event_type="version.created",
            payload={"version_id": str(version.id)},
        )

        self.assertEqual(job.attempts.get(), attempt)
        self.assertEqual(version.checkpoints.get(), checkpoint)
        self.assertGreater(event.id, 0)

    def test_generated_version_cannot_be_updated(self) -> None:
        job = SummaryJob.objects.create(
            status=SummaryJob.Status.COMPLETED,
            title="Summary",
            document_ids=["lecture.pdf"],
            configuration={},
            estimate={},
        )
        attempt = SummaryAttempt.objects.create(
            job=job,
            sequence=1,
            kind=SummaryAttempt.Kind.INITIAL,
        )
        version = SummaryVersion.objects.create(
            job=job,
            attempt=attempt,
            kind=SummaryVersion.Kind.INITIAL,
            structured_output={},
            markdown="Original",
        )
        version.markdown = "Mutated"

        with self.assertRaises(ValueError):
            version.save()
```

- [ ] **Step 2: Run the tests and confirm the models do not exist**

Run:

```bash
pytest tests/test_summary_models.py -v
```

Expected: collection fails with `ImportError` for `SummaryJob`.

- [ ] **Step 3: Add the models and immutable generated-version guard**

Add UUID-backed `SummaryJob`, `SummaryAttempt`, `SummaryVersion`, and
`SummaryCheckpoint` models plus an auto-incrementing `SummaryEvent` model.
Use `JSONField(default=dict)` and `JSONField(default=list)`, database indexes on
job status/creation time and event job/id, and `UniqueConstraint` entries for
`(job, sequence)` plus one generated version per attempt.

Use these exact fields:

- `SummaryJob`: UUID `id`; status choice; title; `document_ids`;
  document count; `configuration`; detected language; `workload_estimate`;
  `metadata`; progress; stage; active attempt; active version;
  `cancel_requested`; creation, confirmation, update, start, and completion
  timestamps.
- `SummaryAttempt`: UUID `id`; job; sequence; kind (`initial`, `retry`,
  `refinement`); source version; refinement instruction; status; stage;
  progress; resolved configuration; error code; error message; creation,
  update, start, and completion timestamps.
- `SummaryVersion`: UUID `id`; job; attempt; parent version; kind (`initial`,
  `refinement`); refinement instruction; title; canonical Markdown; structured
  output; verified citations; provider; model; generation parameters; token
  usage; creation timestamp.
- `SummaryCheckpoint`: UUID `id`; job; source version; name; mutable Markdown;
  creation and update timestamps.
- `SummaryEvent`: auto-increment `id`; job; event type; stage; JSON payload;
  creation timestamp.

The version guard must compare persisted fields for every `SummaryVersion`,
because checkpoints are stored in their own model:

```python
def save(self, *args: object, **kwargs: object) -> None:
    if self.pk:
        original = type(self).objects.get(pk=self.pk)
        immutable_fields = (
            "job_id",
            "attempt_id",
            "kind",
            "parent_version_id",
            "refinement_instruction",
            "title",
            "structured_output",
            "markdown",
            "citations",
            "provider",
            "model",
            "generation_parameters",
            "token_usage",
        )
        if any(
            getattr(original, field) != getattr(self, field)
            for field in immutable_fields
        ):
            raise ValueError("Generated summary versions are immutable")
    super().save(*args, **kwargs)
```

Keep mutable user text only in `SummaryCheckpoint`. Use cascade deletion from a
job to attempts, versions, checkpoints, and events. Use `SET_NULL` for active
attempt/version and parent/source-version references where cascade order would
otherwise create a cycle.

- [ ] **Step 4: Generate and inspect the migration**

Run:

```bash
python manage.py makemigrations django_app --name summary_jobs
python manage.py sqlmigrate django_app 0005
```

Expected: migration `0005_summary_jobs.py` contains five tables, two unique
constraints, and the expected indexes.

- [ ] **Step 5: Run the focused tests**

Run:

```bash
pytest tests/test_summary_models.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add django_app/models.py django_app/migrations/0005_summary_jobs.py tests/test_summary_models.py
git commit -m "feat: add durable summary job models"
```

## Task 2: Validate Summary Configuration and Estimate Work

**Files:**
- Modify: `app/config.py`
- Create: `app/models/summary.py`
- Modify: `app/models/__init__.py`
- Create: `app/services/summary_config.py`
- Test: `tests/test_summary_config.py`

- [ ] **Step 1: Write failing validation and estimate tests**

```python
import pytest

from app.services.summary_config import (
    SummaryConfigurationError,
    build_summary_configuration,
    estimate_summary_work,
)


def test_balanced_preset_applies_defaults_and_allows_overrides() -> None:
    config = build_summary_configuration(
        {
            "preset": "balanced",
            "format": "study_notes",
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "temperature": 0.3,
            "max_output_tokens": 5000,
        }
    )

    assert config.temperature == 0.3
    assert config.max_output_tokens == 5000
    assert config.format == "study_notes"


def test_invalid_temperature_is_rejected() -> None:
    with pytest.raises(SummaryConfigurationError, match="temperature"):
        build_summary_configuration({"temperature": 3.0})


def test_large_estimate_requires_confirmation() -> None:
    estimate = estimate_summary_work(
        document_token_counts=[30_000, 25_000],
        section_target_tokens=4_000,
        confirmation_call_threshold=10,
        confirmation_token_threshold=40_000,
    )

    assert estimate.estimated_calls > 10
    assert estimate.requires_confirmation is True
```

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
pytest tests/test_summary_config.py -v
```

Expected: import failure for `app.services.summary_config`.

- [ ] **Step 3: Add typed summary contracts**

Define Pydantic models in `app/models/summary.py`:

```python
class SummaryConfiguration(BaseModel):
    format: str = "study_notes"
    preset: str = "balanced"
    provider: str
    model: str
    temperature: float
    max_output_tokens: int
    language: str = "auto"
    include_citations: bool = True
    section_target_tokens: int
    citation_support_threshold: float


class SummaryEstimate(BaseModel):
    source_tokens: int
    section_count: int
    estimated_calls: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_seconds: int
    estimated_cost_usd: Optional[float] = None
    requires_confirmation: bool
```

Also define `SummaryCitation`, `SectionSummary`, `DocumentSummary`, and
`SummaryOutput`. `SummaryOutput` must include the exact approved fields:
title, combined overview, key concepts, an `agreements_and_differences` object
containing agreements, differences, and complementary points, per-document
sections, conclusions, claims, and canonical Markdown.
Each claim records evidence and a `verified` boolean. Use `List`, `Dict`, and
`Optional` imports for Python 3.9. Export all contracts from
`app/models/__init__.py`.

- [ ] **Step 4: Implement presets and deterministic estimates**

Use these preset defaults:

```python
PRESETS = {
    "fast": {
        "temperature": 0.1,
        "max_output_tokens": 2500,
        "section_target_tokens": 6000,
        "citation_support_threshold": 0.30,
    },
    "balanced": {
        "temperature": 0.2,
        "max_output_tokens": 5000,
        "section_target_tokens": 4000,
        "citation_support_threshold": 0.40,
    },
    "best": {
        "temperature": 0.2,
        "max_output_tokens": 8000,
        "section_target_tokens": 2500,
        "citation_support_threshold": 0.50,
    },
}
```

Supported formats are exactly `study_notes`, `academic`, `executive`, and
`bullets`. Reject unknown formats, presets, blank provider/model, temperatures
outside `0.0..2.0`, output tokens outside configured bounds, and unsupported
language codes. Estimate calls as section calls plus one per document plus one
combined call when more than one document is selected. Mark confirmation
required when either configured threshold is exceeded. Use an optional
provider/model pricing registry to calculate `estimated_cost_usd`; return
`None`, not a fabricated value, when pricing is unknown.

Resolve `section_target_tokens` against a provider/model context-window registry
so prompts, source text, and expected output fit the selected model. The preset
value is an upper bound, not permission to exceed the model context window.

Add settings to `app/config.py`:

```python
summary_max_workers: int = 2
summary_section_max_workers: int = 2
summary_section_target_tokens: int = 4000
summary_confirmation_call_threshold: int = 12
summary_confirmation_token_threshold: int = 50000
summary_max_output_tokens: int = 12000
summary_sse_poll_seconds: float = 0.5
```

- [ ] **Step 5: Run tests and formatting**

Run:

```bash
pytest tests/test_summary_config.py -v
black --check app/config.py app/models/summary.py app/services/summary_config.py
```

Expected: all tests and formatting checks pass.

- [ ] **Step 6: Commit**

```bash
git add app/config.py app/models/__init__.py app/models/summary.py app/services/summary_config.py tests/test_summary_config.py
git commit -m "feat: validate and estimate summary jobs"
```

## Task 3: Resolve Complete Documents and Create Token-Bounded Sections

**Files:**
- Create: `app/services/summary_documents.py`
- Test: `tests/test_summary_documents.py`

- [ ] **Step 1: Write failing document resolution tests**

```python
import pytest

from app.services.summary_documents import (
    SummaryDocumentError,
    load_summary_documents,
    split_document_sections,
)


def test_resolution_uses_exact_canonical_source_not_substring(monkeypatch) -> None:
    chunks = [
        {"source": "week-1.pdf", "page": 1, "text": "A", "chunk_id": "a"},
        {"source": "week-10.pdf", "page": 1, "text": "B", "chunk_id": "b"},
    ]
    monkeypatch.setattr(
        "app.services.summary_documents.VectorStore.get_all_chunks",
        lambda self: chunks,
    )

    documents = load_summary_documents(["week-1.pdf"])

    assert [chunk.chunk_id for chunk in documents[0].chunks] == ["a"]


def test_missing_document_is_explicit(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.summary_documents.VectorStore.get_all_chunks",
        lambda self: [],
    )

    with pytest.raises(SummaryDocumentError, match="not indexed"):
        load_summary_documents(["missing.pdf"])


def test_sections_preserve_chunk_order_and_overlap() -> None:
    sections = split_document_sections(
        chunks=[
            {"chunk_id": "a", "page": 1, "text": "one two three"},
            {"chunk_id": "b", "page": 2, "text": "four five six"},
            {"chunk_id": "c", "page": 3, "text": "seven eight nine"},
        ],
        target_tokens=5,
        overlap_chunks=1,
    )

    assert sections[0].chunk_ids == ["a", "b"]
    assert sections[1].chunk_ids[0] == "b"
```

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
pytest tests/test_summary_documents.py -v
```

Expected: import failure for `summary_documents`.

- [ ] **Step 3: Implement canonical loading**

Normalize only basename separators and Unicode/case for comparison; never use
substring matching and never accept filesystem paths from the request. Load all
indexed chunks once, group by canonical source, sort by page then stored chunk
order, and retain source, page, text, and chunk ID.

Expose these fully typed public functions:

- `load_summary_documents(document_ids: List[str]) -> List[SummaryDocument]`
- `split_document_sections(chunks: List[SummaryChunk], target_tokens: int,
  overlap_chunks: int = 1) -> List[SummarySection]`
- `choose_output_language(documents: List[SummaryDocument],
  requested_language: str) -> str`

Use the repository's tokenizer helper when available; otherwise use the
documented deterministic estimate `max(1, ceil(len(text) / 4))`. Language
auto-detection may use Unicode script counts and common-word heuristics, but
must return a supported language code and be overrideable.

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest tests/test_summary_documents.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/summary_documents.py tests/test_summary_documents.py
git commit -m "feat: load complete documents for summaries"
```

## Task 4: Make LLM Summarization Strict and Structured

**Files:**
- Modify: `app/services/summarizer.py`
- Modify: `tests/test_summarizer.py`

- [ ] **Step 1: Replace fallback expectations with explicit failure tests**

Remove tests that expect extractive output after an LLM error. Add:

```python
import pytest

from app.services.summarizer import DocumentSummarizer, SummarizerError


def test_llm_failure_is_reported(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.summarizer.call_llm",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("provider down")),
    )

    with pytest.raises(SummarizerError, match="provider down"):
        DocumentSummarizer().summarize_section(
            section_text="Complete section",
            chunk_ids=["chunk-1"],
            configuration={
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "temperature": 0.2,
                "max_output_tokens": 2000,
                "format": "study_notes",
                "language": "en",
            },
        )


def test_invalid_json_is_reported(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.summarizer.call_llm",
        lambda **kwargs: "not-json",
    )

    with pytest.raises(SummarizerError, match="valid JSON"):
        DocumentSummarizer().summarize_section(
            section_text="Text",
            chunk_ids=["chunk-1"],
            configuration=VALID_CONFIG,
        )
```

- [ ] **Step 2: Run and verify the old fallback behavior fails the new tests**

Run:

```bash
pytest tests/test_summarizer.py -v
```

Expected: new tests fail because errors are swallowed or output is extractive.

- [ ] **Step 3: Implement one strict structured-call helper**

Add:

```python
class SummarizerError(RuntimeError):
    pass


def _call_structured_llm(
    *,
    messages: List[Dict[str, str]],
    configuration: SummaryConfiguration,
) -> Dict[str, object]:
    try:
        response = call_llm(
            provider=configuration.provider,
            model=configuration.model,
            call_type="summarization",
            messages=messages,
            timeout=120,
            response_format="json",
            temperature=configuration.temperature,
            max_tokens=configuration.max_output_tokens,
        )
        parsed = json.loads(response)
    except (RuntimeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise SummarizerError(f"LLM summarization failed: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SummarizerError("LLM summarization did not return a JSON object")
    return parsed
```

Implement `summarize_section`, `synthesize_document`, and
`synthesize_collection`. Prompts must:

- Treat source text as untrusted data, not instructions.
- Require JSON only.
- Require every claim to reference one or more supplied chunk IDs.
- Include format and language instructions.
- Never truncate input silently.

Keep legacy `summarize_documents` and `compare_documents` only as thin adapters
that call the strict methods and propagate `SummarizerError`.

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_summarizer.py -v
```

Expected: strict structured tests pass and no fallback tests remain.

- [ ] **Step 5: Commit**

```bash
git add app/services/summarizer.py tests/test_summarizer.py
git commit -m "fix: make LLM summarization explicit and structured"
```

## Task 5: Verify Claim-Level Citations

**Files:**
- Create: `app/services/summary_citations.py`
- Test: `tests/test_summary_citations.py`

- [ ] **Step 1: Write failing evidence verification tests**

```python
import pytest

from app.services.summary_citations import (
    CitationVerificationError,
    verify_claim_citations,
)


def test_verified_citation_uses_indexed_page_and_passage() -> None:
    citations = verify_claim_citations(
        claims=[
            {
                "text": "Gradient descent follows the negative gradient.",
                "chunk_ids": ["chunk-7"],
            }
        ],
        chunks_by_id={
            "chunk-7": {
                "source": "ml.pdf",
                "page": 12,
                "text": "The update follows the negative gradient.",
            }
        },
    )

    assert citations[0].source == "ml.pdf"
    assert citations[0].page == 12
    assert "negative gradient" in citations[0].passage


def test_unknown_chunk_reference_marks_claim_unverified() -> None:
    result = verify_claim_citations(
        claims=[{"id": "claim-1", "text": "Claim", "chunk_ids": ["invented"]}],
        chunks_by_id={},
        support_threshold=0.4,
    )

    assert result.claims[0].verified is False
    assert result.claims[0].evidence == []
    assert result.warnings == ["claim-1 has no verified evidence"]
```

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
pytest tests/test_summary_citations.py -v
```

Expected: import failure.

- [ ] **Step 3: Implement deterministic verification**

For each claim, discard empty evidence and unknown chunk IDs. Resolve source,
page, and a bounded passage directly from indexed chunk data. Confirm a
candidate quote occurs in normalized chunk text, then use normalized lexical
support to retain evidence at or above the configured threshold. Do not invent
or rewrite evidence. Return citation IDs stable within the version:

```python
SummaryCitation(
    id=f"cite-{claim_index + 1}",
    claim=claim_text,
    source=chunk.source,
    page=chunk.page,
    chunk_id=chunk.chunk_id,
    passage=passage,
)
```

Return unverified claims with an empty evidence list and a warning. Raise
`CitationVerificationError` only when the model's entire claim structure is
invalid and cannot be parsed safely. This allows a job with some unsupported
citations to complete with warnings, as required by the approved design.

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_summary_citations.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/summary_citations.py tests/test_summary_citations.py
git commit -m "feat: verify summary claim citations"
```

## Task 6: Build the Hierarchical Summarization Pipeline

**Files:**
- Create: `app/services/hierarchical_summarizer.py`
- Test: `tests/test_hierarchical_summarizer.py`

- [ ] **Step 1: Write a failing orchestration test**

```python
from app.services.hierarchical_summarizer import HierarchicalSummarizer


def test_pipeline_summarizes_sections_documents_and_collection(
    monkeypatch,
) -> None:
    calls = []

    class FakeSummarizer:
        def summarize_section(self, **kwargs):
            calls.append(("section", kwargs["chunk_ids"]))
            return {"summary": "section", "claims": []}

        def synthesize_document(self, **kwargs):
            calls.append(("document", kwargs["document"].source))
            return {"summary": "document", "claims": []}

        def synthesize_collection(self, **kwargs):
            calls.append(("collection", len(kwargs["document_summaries"])))
            return {
                "title": "Combined",
                "combined_overview": "Overview",
                "key_concepts": [],
                "agreements_and_differences": [],
                "conclusions": [],
                "claims": [],
            }

    events = []
    result = HierarchicalSummarizer(
        summarizer=FakeSummarizer(),
        event_callback=lambda event_type, payload: events.append(
            (event_type, payload)
        ),
        cancellation_callback=lambda: False,
    ).run(documents=TWO_DOCUMENTS, configuration=CONFIG)

    assert [name for name, _ in calls].count("section") >= 2
    assert [name for name, _ in calls].count("document") == 2
    assert ("collection", 2) in calls
    assert result.title == "Combined"
    assert any(event[0] == "partial.document" for event in events)
```

Add a second test where `cancellation_callback` flips to `True` between
sections and assert `SummaryCancelledError`. Add a third test where document
intermediate summaries exceed the selected model budget and assert an
additional reduction call occurs before document synthesis. Add a fourth test
where one claim is unverified and assert the final result completes with a
warning and a non-clickable claim.

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
pytest tests/test_hierarchical_summarizer.py -v
```

Expected: import failure.

- [ ] **Step 3: Implement the pipeline**

Implement this sequence:

```python
for document_index, document in enumerate(documents):
    sections = split_document_sections(
        document.chunks,
        target_tokens=configuration.section_target_tokens,
    )
    section_summaries = summarize_sections_with_bounded_pool(sections)
    emit("partial.section", serialized_section_summary)
    reduced_summaries = recursively_reduce_to_context_budget(
        section_summaries,
        configuration=configuration,
    )
    document_summary = summarizer.synthesize_document(
        document=document,
        section_summaries=reduced_summaries,
        configuration=configuration,
    )
    emit("partial.document", serialized_document_summary)

collection = summarizer.synthesize_collection(
    document_summaries=document_summaries,
    configuration=configuration,
)
verification = verify_claim_citations(
    claims=all_claims,
    chunks_by_id=all_chunks_by_id,
    support_threshold=configuration.citation_support_threshold,
)
for warning in verification.warnings:
    emit("warning", {"detail": warning})
return render_canonical_summary_output(
    collection,
    document_summaries,
    verification.claims,
)
```

Use a section pool no larger than
`min(settings.summary_section_max_workers, remaining_sections)`. Preserve
section order after concurrent calls. Check cancellation before every LLM call
and before persistence callbacks. Recursively reduce intermediate summaries
until they fit the selected model's context budget; never truncate them. Render
canonical Markdown server-side from the structured output; do not accept
model-generated HTML.

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest tests/test_hierarchical_summarizer.py -v
```

Expected: orchestration, order, event, and cancellation tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/hierarchical_summarizer.py tests/test_hierarchical_summarizer.py
git commit -m "feat: add hierarchical summary pipeline"
```

## Task 7: Add Job State Machine, Executor, Retry, and Recovery

**Files:**
- Create: `app/services/summary_jobs.py`
- Modify: `django_app/apps.py`
- Modify: `django_backend/settings.py`
- Test: `tests/test_summary_jobs.py`

- [ ] **Step 1: Write failing service tests**

Cover these exact cases:

- `test_small_job_is_queued_and_submitted`: assert status `queued`, one attempt,
  one `job.queued` event, and exactly one executor submission.
- `test_large_job_waits_for_confirmation`: assert status
  `awaiting_confirmation`, a `job.confirmation_required` event, and zero
  executor submissions.
- `test_confirmed_job_is_submitted_once`: call confirmation twice and assert
  one submission and one queued transition.
- `test_retry_creates_new_attempt_and_preserves_failed_attempt`: assert attempt
  sequences `[1, 2]`, attempt 1 remains failed, and active attempt is 2.
- `test_cancel_sets_request_and_pipeline_observes_it`: assert
  `cancel_requested` becomes true, then the worker reaches cancelled, and both
  request/cancelled events are stored.
- `test_completion_creates_immutable_version_and_events`: assert active
  version, completed status, and ordered version/completion events.
- `test_failure_persists_error_and_failed_event`: assert exact error detail and
  terminal failed event.
- `test_recover_stale_active_jobs_marks_them_interrupted`: create queued and
  running jobs and assert both become interrupted.

Use `django.test.TestCase`, patch document loading and executor submission, and
assert exact state transitions and event order.

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
pytest tests/test_summary_jobs.py -v
```

Expected: import failure for `SummaryJobService`.

- [ ] **Step 3: Implement transactional job lifecycle**

Create a singleton service with a bounded `ThreadPoolExecutor`:

```python
class SummaryJobService:
    _instance: Optional["SummaryJobService"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=settings.summary_max_workers,
            thread_name_prefix="summary-job",
        )
```

Every state change and event insert must occur in one `transaction.atomic()`
block with `select_for_update()`. `create_job` validates document IDs,
configuration, and estimate; it creates an `estimating` record first, then saves
`awaiting_confirmation` or `queued` after the workload and detected language
are known. Estimation failure stores an explicit failed state and diagnostic.
`confirm_job` is idempotent. `retry_job` creates a new `SummaryAttempt` and
never overwrites prior attempts or versions and may merge validated
provider/model overrides into the new attempt configuration. `refine_job`
creates a refinement attempt linked to a source version and passes the original
structured result plus the user's refinement request to the pipeline.

The worker must call `django.db.close_old_connections()` at start and finish.
Cancellation is cooperative and represented by `cancel_requested_at`.

- [ ] **Step 4: Add guarded startup recovery**

Replace the existing `"django_app"` entry in `INSTALLED_APPS` with
`"django_app.apps.DjangoAppConfig"`; do not add a duplicate app entry.

In `DjangoAppConfig.ready()`, call a registration function that performs stale
recovery once per process and catches only `OperationalError` and
`ProgrammingError` for pre-migration startup. Recovery changes queued and
running jobs to interrupted and appends `job.interrupted`.

- [ ] **Step 5: Run focused tests**

Run:

```bash
pytest tests/test_summary_jobs.py -v
```

Expected: all state-machine tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/services/summary_jobs.py django_app/apps.py django_backend/settings.py tests/test_summary_jobs.py
git commit -m "feat: orchestrate persistent summary jobs"
```

## Task 8: Expose REST and Replayable SSE APIs

**Files:**
- Create: `django_app/views/summary_jobs.py`
- Modify: `django_app/views/__init__.py`
- Modify: `django_backend/urls.py`
- Test: `tests/test_summary_job_views.py`

- [ ] **Step 1: Write failing API tests**

Use `django.test.Client` to cover create, confirm, list, detail, retry, cancel,
refine, checkpoint CRUD, and authorization-by-existence for the single-user
deployment. Include:

```python
def test_create_job_returns_confirmation_payload(client, monkeypatch) -> None:
    response = client.post(
        "/api/summary/jobs",
        data=json.dumps(
            {
                "document_ids": ["large.pdf"],
                "configuration": VALID_CONFIG,
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "awaiting_confirmation"
    assert body["estimate"]["requires_confirmation"] is True


def test_events_replay_after_last_event_id(client, summary_job) -> None:
    SummaryEvent.objects.create(
        job=summary_job,
        event_type="stage.progress",
        payload={"progress": 50},
    )
    latest = SummaryEvent.objects.create(
        job=summary_job,
        event_type="job.completed",
        payload={},
    )

    response = client.get(
        f"/api/summary/jobs/{summary_job.id}/events",
        HTTP_LAST_EVENT_ID=str(latest.id - 1),
    )

    first_chunk = next(response.streaming_content).decode("utf-8")
    assert f"id: {latest.id}" in first_chunk
    assert "event: job.completed" in first_chunk
```

- [ ] **Step 2: Run and confirm 404 failures**

Run:

```bash
pytest tests/test_summary_job_views.py -v
```

Expected: endpoints return 404.

- [ ] **Step 3: Implement JSON serializers and handlers**

Use existing `_get_json_body` and `_error_response` patterns. Return:

- `202` for accepted queued/confirmation jobs.
- `200` for reads, confirmation, cancel, retry, refine, and checkpoint writes.
- `400` for validation or illegal transitions.
- `404` for missing entities.
- `409` for conflicting immutable-version edits.
- `503` when executor submission is unavailable.

Serialize job, attempts, active version, checkpoints, estimate, progress, and
error detail. Never expose arbitrary source paths or API keys.

`PATCH /api/summary/jobs/<id>` may rename only the user-facing job title.
Retry accepts optional validated provider, model, preset, temperature, and token
overrides. Checkpoint patch accepts only name and Markdown. Reject updates to
generated-version content.

- [ ] **Step 4: Implement replayable SSE with heartbeat**

Use `StreamingHttpResponse(content_type="text/event-stream")`. Start after
`Last-Event-ID` or `?after=`. Query persisted events in ascending ID order,
emit:

```text
id: 42
event: stage.progress
data: {"progress": 50}

```

When there is no event, emit `: heartbeat\n\n`. Stop after a terminal event and
all persisted events have been delivered. Set:

```python
response["Cache-Control"] = "no-cache"
response["X-Accel-Buffering"] = "no"
```

- [ ] **Step 5: Register all routes**

Add both slash and non-slash forms only where the existing project explicitly
does so. Preserve `APPEND_SLASH = False`.

- [ ] **Step 6: Run API tests**

Run:

```bash
pytest tests/test_summary_job_views.py -v
```

Expected: all API and SSE tests pass.

- [ ] **Step 7: Commit**

```bash
git add django_app/views/summary_jobs.py django_app/views/__init__.py django_backend/urls.py tests/test_summary_job_views.py
git commit -m "feat: expose summary job and event APIs"
```

## Task 9: Migrate Legacy JSON History and Preserve Old Endpoints

**Files:**
- Modify: `django_app/views/summaries.py`
- Create: `django_app/management/__init__.py`
- Create: `django_app/management/commands/__init__.py`
- Create: `django_app/management/commands/migrate_summary_history.py`
- Test: `tests/test_summary_history_migration.py`

- [ ] **Step 1: Write failing idempotent import tests**

Create a temporary `summary_history.json`, run:

```python
call_command("migrate_summary_history", path=str(history_path))
call_command("migrate_summary_history", path=str(history_path))
```

Assert exactly one completed job, one imported attempt, and one generated
version exist. Assert malformed entries are reported and skipped without
discarding valid entries.

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
pytest tests/test_summary_history_migration.py -v
```

Expected: unknown management command.

- [ ] **Step 3: Implement the import command**

Use a deterministic import key stored in `SummaryJob.metadata`, for example:

```python
legacy_key = hashlib.sha256(
    json.dumps(entry, sort_keys=True).encode("utf-8")
).hexdigest()
```

Import legacy summaries as completed jobs with an imported attempt and
generated version. Do not delete or rewrite the JSON file.

- [ ] **Step 4: Convert legacy views into adapters**

Keep old endpoints temporarily:

- `generate_summary` creates a job and returns `202` plus job ID.
- `get_summary_history` reads completed jobs/versions.
- `delete_summary` deletes the corresponding job.
- `regenerate_summary` calls retry.

Remove new writes to `data/summary_history.json`. Preserve a compatibility
shape only for current clients until the Vue migration lands.

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/test_summary_history_migration.py tests/test_summary_job_views.py -v
```

Expected: import and compatibility tests pass.

- [ ] **Step 6: Commit**

```bash
git add django_app/views/summaries.py django_app/management tests/test_summary_history_migration.py
git commit -m "feat: migrate legacy summary history"
```

## Task 10: Add Frontend Test Harness and Summary API Client

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/vite.config.js`
- Create: `frontend/src/test/setup.js`
- Create: `frontend/src/services/summaryApi.js`
- Test: `frontend/src/services/summaryApi.test.js`

- [ ] **Step 1: Install test dependencies and add the test script**

Run:

```bash
cd frontend
npm install --save-dev vitest @vue/test-utils jsdom
```

Add:

```json
"test": "vitest run"
```

Configure `test.environment = "jsdom"` and
`test.setupFiles = ["./src/test/setup.js"]` in `vite.config.js`.

- [ ] **Step 2: Write failing API tests**

Mock `fetch` and `EventSource`. Cover request JSON, non-2xx `detail` errors,
event parsing, last event ID tracking, terminal close, and polling fallback.

```javascript
it('throws the backend detail for a failed create', async () => {
  global.fetch.mockResolvedValue({
    ok: false,
    json: async () => ({ detail: 'No indexed chunks' }),
  })

  await expect(createSummaryJob({ document_ids: ['missing.pdf'] }))
    .rejects.toThrow('No indexed chunks')
})
```

- [ ] **Step 3: Run and confirm failure**

Run:

```bash
npm test -- src/services/summaryApi.test.js
```

Expected: module import failure.

- [ ] **Step 4: Implement the API module**

Export:

```javascript
createSummaryJob
listSummaryJobs
getSummaryJob
updateSummaryJob
deleteSummaryJob
confirmSummaryJob
cancelSummaryJob
retrySummaryJob
refineSummaryJob
createSummaryCheckpoint
updateSummaryCheckpoint
deleteSummaryCheckpoint
subscribeToSummaryEvents
```

`subscribeToSummaryEvents` must accept `afterEventId`, call `onEvent`,
`onDisconnected`, and `onTerminal`, and expose `close()`. Use native
`EventSource` for GET SSE. After repeated disconnects, let the store poll
`getSummaryJob`; do not hide errors.

- [ ] **Step 5: Run tests**

Run:

```bash
npm test -- src/services/summaryApi.test.js
```

Expected: all API tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.js frontend/src/test/setup.js frontend/src/services/summaryApi.js frontend/src/services/summaryApi.test.js
git commit -m "test: add summary frontend API harness"
```

## Task 11: Rewrite the Summary Store Around Durable Jobs

**Files:**
- Modify: `frontend/src/stores/summaryStore.js`
- Test: `frontend/src/stores/summaryStore.test.js`

- [ ] **Step 1: Write failing Pinia store tests**

Cover:

```javascript
it('stores a confirmation-required job without starting events')
it('subscribes after a queued job is created')
it('applies partial and completed events idempotently')
it('restores active jobs when the application reloads')
it('falls back to polling after stream disconnection')
it('keeps local markdown dirty until checkpoint save succeeds')
it('preserves local markdown when checkpoint save fails')
it('closes only the drawer while the job remains active')
```

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
cd frontend
npm test -- src/stores/summaryStore.test.js
```

Expected: tests fail against the synchronous legacy store.

- [ ] **Step 3: Implement store state and actions**

Use:

```javascript
state: () => ({
  drawerOpen: false,
  jobs: [],
  activeJobId: null,
  activeJob: null,
  lastEventIdByJob: {},
  streamByJob: {},
  partialSections: [],
  partialDocuments: [],
  draftMarkdown: '',
  draftDirty: false,
  loading: false,
  error: null,
})
```

Implement actions for create, confirm, select, stream, poll, cancel, retry,
refine, checkpoint save/update/delete, history refresh, and drawer close.
Ignore duplicate events by event ID. On terminal event, fetch authoritative job
detail before closing the stream. `initialize()` lists jobs, restores the most
recent non-terminal job, and reconnects.

- [ ] **Step 4: Run tests**

Run:

```bash
npm test -- src/stores/summaryStore.test.js
```

Expected: all store tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/summaryStore.js frontend/src/stores/summaryStore.test.js
git commit -m "feat: manage durable summary jobs in Pinia"
```

## Task 12: Share PDF Navigation Between Chat and Summary Citations

**Files:**
- Create: `frontend/src/stores/pdfViewerStore.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/components/chat/ChatPanel.vue`
- Modify: `frontend/src/composables/useChatState.js`
- Test: `frontend/src/stores/pdfViewerStore.test.js`

- [ ] **Step 1: Write failing viewer-store tests**

```javascript
it('opens a canonical media URL at the cited page and passage', () => {
  const store = usePdfViewerStore()
  store.openCitation({
    source: 'week 1.pdf',
    page: 7,
    passage: 'Key evidence',
  })

  expect(store.isOpen).toBe(true)
  expect(store.pdfUrl).toBe('/media/data_source/week%201.pdf')
  expect(store.page).toBe(7)
  expect(store.highlightText).toBe('Key evidence')
})
```

Also reject source values containing path separators or traversal components.

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
cd frontend
npm test -- src/stores/pdfViewerStore.test.js
```

Expected: store import failure.

- [ ] **Step 3: Implement the shared viewer store**

Expose `openCitation`, `openSource`, and `close`. Build URLs from encoded
canonical filenames only. Keep page and highlight in store state.

- [ ] **Step 4: Move the viewer to application scope**

Render one `PdfViewer` in `App.vue`, bound to the shared store. Remove the local
viewer instance and local PDF state from `ChatPanel.vue`. Update
`useChatState.js` citation handlers to call the shared store, preserving current
chat behavior.

- [ ] **Step 5: Run tests and build**

Run:

```bash
npm test -- src/stores/pdfViewerStore.test.js
npm run build
```

Expected: store tests and production build pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/stores/pdfViewerStore.js frontend/src/stores/pdfViewerStore.test.js frontend/src/App.vue frontend/src/components/chat/ChatPanel.vue frontend/src/composables/useChatState.js
git commit -m "feat: share PDF citation navigation"
```

## Task 13: Build the Studio Drawer, Setup, Progress, and History

**Files:**
- Create: `frontend/src/components/studio/SummaryDrawer.vue`
- Create: `frontend/src/components/studio/SummaryJobSetup.vue`
- Create: `frontend/src/components/studio/SummaryProgress.vue`
- Create: `frontend/src/components/studio/SummaryHistory.vue`
- Test: `frontend/src/components/studio/SummaryDrawer.test.js`

- [ ] **Step 1: Write failing drawer tests**

Mount with testing Pinia and stub child components. Assert:

- Setup form is shown with selected PDFs, format, provider, model, preset,
  temperature, token limit, and language.
- The create response displays the estimate immediately; large jobs remain
  unscheduled until confirmation.
- Confirmation state shows calls, tokens, and estimated time.
- Running state shows current stage, progress, cancel, and partial output.
- Closing the drawer does not call cancel.
- History can reopen completed, failed, cancelled, and interrupted jobs.
- Failed state exposes retry and the backend error detail.
- History rename calls the job patch endpoint.
- Export downloads the selected generated version or checkpoint as UTF-8
  Markdown with a sanitized filename.

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
cd frontend
npm test -- src/components/studio/SummaryDrawer.test.js
```

Expected: component import failure.

- [ ] **Step 3: Implement the drawer shell**

Use an accessible slide-over:

```vue
<aside
  v-if="store.drawerOpen"
  class="summary-drawer"
  role="dialog"
  aria-modal="true"
  aria-labelledby="summary-drawer-title"
>
```

Trap focus, close on Escape, restore focus to the trigger, and provide an
explicit close button. Use a responsive width around `min(920px, 100vw)` so the
split editor fits on desktop and stacks on narrow screens.

- [ ] **Step 4: Implement setup and confirmation**

Load provider/model choices from the existing LLM settings store. Keep preset
defaults visible while allowing all overrides. Show selected document count,
estimated source tokens, calls, output tokens, and duration. Submit creates the
job; confirmation calls the confirm endpoint; canceling confirmation deletes
or leaves the draft job according to the store action.

- [ ] **Step 5: Implement progress and history**

Progress renders stages and accumulated `partial.section` and
`partial.document` payloads. History groups by date, shows status and document
count, and supports open, rename, export, delete, and retry where valid. Export
uses a client-created Markdown `Blob`; it does not require a separate download
endpoint. Never present partial output as a completed summary. On failed or
interrupted jobs, preserve completed partials and label them incomplete.

- [ ] **Step 6: Run tests**

Run:

```bash
npm test -- src/components/studio/SummaryDrawer.test.js
```

Expected: drawer state tests pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/studio/SummaryDrawer.vue frontend/src/components/studio/SummaryJobSetup.vue frontend/src/components/studio/SummaryProgress.vue frontend/src/components/studio/SummaryHistory.vue frontend/src/components/studio/SummaryDrawer.test.js
git commit -m "feat: add Studio summary job drawer"
```

## Task 14: Add Result Rendering, Verified Citations, Editing, and Refinement

**Files:**
- Create: `frontend/src/components/studio/SummaryResult.vue`
- Create: `frontend/src/components/studio/SummaryMarkdownEditor.vue`
- Create: `frontend/src/components/studio/SummaryRefinement.vue`
- Create: `frontend/src/components/studio/SummaryCitation.vue`
- Test: `frontend/src/components/studio/SummaryMarkdownEditor.test.js`
- Test: `frontend/src/components/studio/SummaryCitation.test.js`

- [ ] **Step 1: Write failing editor tests**

Assert that:

- Generated Markdown initially populates the textarea and preview.
- Typing updates local draft only.
- Save creates a named checkpoint.
- Failed save retains dirty text and shows the error.
- Selecting a checkpoint does not mutate the generated version.
- Exporting generated or checkpoint Markdown preserves UTF-8 content.

- [ ] **Step 2: Write failing citation tests**

```javascript
it('opens the verified source page and highlight', async () => {
  const wrapper = mount(SummaryCitation, {
    props: {
      citation: {
        id: 'cite-1',
        source: 'ml.pdf',
        page: 12,
        passage: 'negative gradient',
      },
    },
  })

  await wrapper.get('button').trigger('click')

  expect(usePdfViewerStore().page).toBe(12)
  expect(usePdfViewerStore().highlightText).toBe('negative gradient')
})
```

- [ ] **Step 3: Run and confirm failure**

Run:

```bash
cd frontend
npm test -- src/components/studio/SummaryMarkdownEditor.test.js src/components/studio/SummaryCitation.test.js
```

Expected: component import failures.

- [ ] **Step 4: Implement safe result rendering**

Render canonical Markdown through the existing `MarkdownRenderer.vue`, which
uses MarkdownIt and DOMPurify. Render citation buttons from the separate
verified citation array; do not parse model-generated HTML or trust citation
links embedded in Markdown. Claims marked `verified: false` render a visible
unverified label and no clickable citation. If PDF highlighting fails, keep the
viewer on the cited page and show the escaped evidence passage in citation
details.

- [ ] **Step 5: Implement split editor and checkpoints**

Desktop layout is textarea left, live sanitized preview right. Mobile layout
stacks them. Add checkpoint name, save, update, and delete controls. Warn before
switching versions or closing with unsaved changes; do not auto-save direct
edits.

- [ ] **Step 6: Implement conversational refinement**

Provide a prompt input and submit button. Refinement creates a child summary job
from the selected generated version or checkpoint content. Show it in history
as a new version lineage and reuse the same progress/error UI.

- [ ] **Step 7: Run tests**

Run:

```bash
npm test -- src/components/studio/SummaryMarkdownEditor.test.js src/components/studio/SummaryCitation.test.js
```

Expected: editor and citation tests pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/studio/SummaryResult.vue frontend/src/components/studio/SummaryMarkdownEditor.vue frontend/src/components/studio/SummaryRefinement.vue frontend/src/components/studio/SummaryCitation.vue frontend/src/components/studio/SummaryMarkdownEditor.test.js frontend/src/components/studio/SummaryCitation.test.js
git commit -m "feat: edit and refine cited summaries"
```

## Task 15: Integrate Studio, Remove Legacy UI, and Verify End to End

**Files:**
- Modify: `frontend/src/components/layout/StudioPanel.vue`
- Delete: `frontend/src/components/studio/SummaryModal.vue`
- Delete: `frontend/src/components/studio/SummaryViewer.vue`
- Modify: `README.md`
- Modify: `docs/API.md`
- Modify: `docs/RAG_ARCHITECTURE.md`

- [ ] **Step 1: Integrate the drawer**

Replace modal and inline viewer state in `StudioPanel.vue` with:

```vue
<button type="button" @click="summaryStore.openDrawer()">
  Summarize
</button>
<SummaryDrawer />
```

Initialize the summary store once when the Studio panel/app mounts. Preserve
the current PDF selection flow and pass canonical selected document IDs into
the setup component.

- [ ] **Step 2: Remove obsolete components and API calls**

Delete `SummaryModal.vue` and `SummaryViewer.vue`. Remove old summary API
imports from `frontend/src/services/api.js` only after `rg` confirms there are
no remaining callers:

```bash
rg -n "SummaryModal|SummaryViewer|generateSummary|getSummaryHistory|regenerateSummary" frontend/src
```

Expected: no legacy UI references remain; only deliberate compatibility code
may remain in backend views.

- [ ] **Step 3: Document operation and limitations**

Document:

- Summary job API and SSE event types.
- In-process worker limits and the requirement for a single application
  process in this initial deployment.
- Interrupted-job behavior after restart.
- Explicit LLM failure behavior.
- Legacy history migration command.
- Configuration environment variables.

- [ ] **Step 4: Run backend verification**

Run:

```bash
pytest tests/test_summary_models.py tests/test_summary_config.py tests/test_summary_documents.py tests/test_summarizer.py tests/test_summary_citations.py tests/test_hierarchical_summarizer.py tests/test_summary_jobs.py tests/test_summary_job_views.py tests/test_summary_history_migration.py -v --tb=short
ruff check app/ django_app/ django_backend/ manage.py
black --check app/ django_app/ django_backend/ manage.py
```

Expected: focused tests pass and lint/format checks report no errors.

- [ ] **Step 5: Run full backend regression suite**

Run:

```bash
pytest tests/ -v --tb=short
```

Expected: all tests pass. If an unrelated existing failure is present, record
the exact failing test and confirm all summary-focused tests still pass.

- [ ] **Step 6: Run frontend verification**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: all Vitest tests pass and Vite production build succeeds.

- [ ] **Step 7: Perform local browser smoke test**

Run the backend and frontend using the repository's normal development
commands. In the in-app browser:

1. Select two indexed PDFs.
2. Open Studio Summary.
3. Configure provider/model/preset and create a job.
4. Confirm a large estimate if prompted.
5. Close and reopen the drawer while generation continues.
6. Observe stage and partial events.
7. Open a citation and verify PDF page/highlight.
8. Save a manual checkpoint.
9. Submit a refinement.
10. Reload and verify shared history restoration.
11. Simulate an LLM error and verify explicit retry UI.

Expected: all flows match the approved design and no silent extractive result
appears.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/layout/StudioPanel.vue frontend/src/components/studio frontend/src/services/api.js README.md docs/API.md docs/RAG_ARCHITECTURE.md
git commit -m "feat: integrate Studio summary workflow"
```

## Final Review Checklist

- [ ] All selected PDFs are summarized from all indexed chunks, not truncated prefixes.
- [ ] Canonical document matching cannot confuse similarly named files.
- [ ] Every visible citation resolves to an indexed chunk, source, page, and passage.
- [ ] LLM/provider failures remain explicit and retryable.
- [ ] Confirmation is required above configured work thresholds.
- [ ] Workload estimate reports token/time values and cost when pricing is known.
- [ ] Closing the drawer does not cancel a running job.
- [ ] SSE reconnect replays persisted events without duplicating UI state.
- [ ] Polling fallback reaches the same terminal state as SSE.
- [ ] Generated versions are immutable; direct edits exist only as checkpoints.
- [ ] Refinements create version lineage instead of overwriting history.
- [ ] Restart recovery marks stale active jobs interrupted.
- [ ] Only canonical Markdown is rendered and all rendered HTML is sanitized.
- [ ] Summary and chat citations use the same PDF viewer.
- [ ] Unsupported citations are removed and affected claims are visibly unverified.
- [ ] History supports reopen, rename, Markdown export, retry, and delete.
- [ ] Legacy JSON history import is idempotent.
- [ ] Focused tests, full pytest, frontend tests, lint, formatting, build, and browser smoke test are complete.
