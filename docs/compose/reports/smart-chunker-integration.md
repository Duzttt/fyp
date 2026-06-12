---
feature: smart-chunker-integration
status: delivered
specs: []
plans:
  - docs/compose/plans/2026-06-13-smart-chunker-integration.md
branch: main
commits: pending
---

# SmartChunker Integration — Final Report

## What Was Built

A `CHUNK_STRATEGY` configuration option (`"sentence"` or `"paragraph"`) that lets the production PDF indexing pipeline use the existing `SmartChunker` instead of the default sentence-level chunker. When set to `"paragraph"`, the system uses paragraph-aware splitting with bilingual sentence-boundary detection, boundary-respecting overlap, heading extraction, and keyword extraction. The default `"sentence"` behavior is unchanged.

The integration is wired end-to-end: `.env` → `Settings.CHUNK_STRATEGY` → `index_pdf_directory()` → `index_pdf_file()` → `chunk_pdf_with_metadata()` → routes to either `split_text_into_chunks()` or `split_text_into_chunks_smart()`.

## Architecture

### Components

| File | Change |
|------|--------|
| `app/config.py:27` | Added `CHUNK_STRATEGY: str = "sentence"` with validator |
| `app/services/pdf_chunking.py:183-200` | Added `split_text_into_chunks_smart()` adapter wrapping `SmartChunker` |
| `app/services/pdf_chunking.py:414` | `chunk_pdf_with_metadata()` now accepts `chunk_strategy` param and routes |
| `app/services/pdf_indexing.py:65-72,152-159` | `index_pdf_file()` and `index_pdf_directory()` accept and pass `chunk_strategy` |
| `django_app/views/helpers.py:111-117` | Passes `settings.CHUNK_STRATEGY` to `index_pdf_directory()` |

### Data Flow

```
.env (CHUNK_STRATEGY=paragraph)
  → Settings.validate_chunk_strategy() → normalizes to "sentence"|"paragraph"
    → helpers._run_indexing_worker()
      → index_pdf_directory(chunk_strategy=settings.CHUNK_STRATEGY)
        → index_pdf_file(chunk_strategy=chunk_strategy)
          → chunk_pdf_with_metadata(chunk_strategy=chunk_strategy)
            → if "paragraph": split_text_into_chunks_smart()
            → else: split_text_into_chunks()
```

### Design Decisions

- **Adapter pattern over direct import**: `split_text_into_chunks_smart()` wraps `SmartChunker` to return `List[str]` matching the existing `split_text_into_chunks()` interface, keeping `chunk_pdf_with_metadata()` output format unchanged.
- **No breaking changes**: Default is `"sentence"` — existing behavior is preserved without any config changes.
- **Validator rejects invalid values**: Falls back to `"sentence"` for unknown strategies, matching the pattern used by `UPLOAD_INDEXING_STRATEGY`.

## Usage

Set in `.env`:

```
CHUNK_STRATEGY=sentence    # default — sentence-level splitting
CHUNK_STRATEGY=paragraph   # SmartChunker — paragraph-aware splitting
```

Or pass programmatically:

```python
index_pdf_file("doc.pdf", chunk_strategy="paragraph")
index_pdf_directory("data/", chunk_strategy="paragraph")
chunk_pdf_with_metadata("doc.pdf", chunk_strategy="paragraph")
```

## Verification

- **32/32 tests pass** across 3 test files: `test_config_chunk_strategy.py` (4), `test_pdf_chunking.py` (24), `test_pdf_indexing.py` (9)
- **368/369 full suite** — 1 pre-existing flaky failure in `test_citation_rag.py` (LLM output-dependent, unrelated)
- **Ruff lint: 0 errors** on modified files
- **Black format: all 4 modified files clean**

New tests cover:
- Config validation (default, valid, invalid fallback, case insensitivity)
- Smart chunker adapter (basic, empty, returns strings)
- Strategy routing (sentence, paragraph, default)
- Parameter passthrough (signature inspection for both functions)

## Journey Log

- [lesson] Existing `test_pdf_indexing.py` mocks used bare lambdas without `**kwargs` — adding a new keyword argument to production code broke 6 existing tests. Fixed by updating mock signatures to accept `chunk_strategy`.
- [lesson] `SmartChunker` already existed in `chunking/smart_chunker.py` with full test coverage but was never wired into production. The integration required only ~40 lines of adapter + routing code.

## Source Materials

| File | Role | Notes |
|------|------|-------|
| `docs/compose/plans/2026-06-13-smart-chunker-integration.md` | Implementation plan | 5 tasks, executed inline |
| `chunking/smart_chunker.py` | Pre-existing SmartChunker | 512 lines, paragraph-aware, bilingual |
| `app/services/pdf_chunking.py` | Production chunking | Contains both sentence and smart adapters |
