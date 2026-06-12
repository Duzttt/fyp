# SmartChunker Integration Plan

> [!NOTE]
> This document may not reflect the current implementation.
> See the final report for up-to-date state:
> [Final Report](../reports/smart-chunker-integration.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `CHUNK_STRATEGY` config option that lets the production pipeline use the existing `SmartChunker` (paragraph-aware, bilingual, metadata-rich) instead of the default sentence-level chunker.

**Architecture:** Add `CHUNK_STRATEGY` to `Settings`, create a `chunk_pdf_with_metadata_smart()` adapter that wraps `SmartChunker` into the same output format as `split_text_into_chunks()`, then route through `chunk_pdf_with_metadata()` based on the strategy. The rest of the pipeline (embedding, FAISS storage) is unchanged.

**Tech Stack:** Python, pydantic-settings, existing `chunking.smart_chunker.SmartChunker` class.

---

### Task 1: Add CHUNK_STRATEGY config option

**Files:**
- Modify: `app/config.py:26-27`

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_chunk_strategy.py`:

```python
import pytest


class TestChunkStrategyConfig:
    def test_default_chunk_strategy(self):
        from app.config import Settings

        s = Settings(_env_file=None)
        assert s.CHUNK_STRATEGY == "sentence"

    def test_valid_strategy_paragraph(self):
        from app.config import Settings

        s = Settings(CHUNK_STRATEGY="paragraph", _env_file=None)
        assert s.CHUNK_STRATEGY == "paragraph"

    def test_invalid_strategy_falls_back_to_sentence(self):
        from app.config import Settings

        s = Settings(CHUNK_STRATEGY="invalid", _env_file=None)
        assert s.CHUNK_STRATEGY == "sentence"

    def test_case_insensitive_strategy(self):
        from app.config import Settings

        s = Settings(CHUNK_STRATEGY="PARAGRAPH", _env_file=None)
        assert s.CHUNK_STRATEGY == "paragraph"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_chunk_strategy.py -v`
Expected: FAIL — `Settings` has no attribute `CHUNK_STRATEGY`

- [ ] **Step 3: Implement config change**

In `app/config.py`, after line 27 (`CHUNK_OVERLAP`), add:

```python
CHUNK_STRATEGY: str = "sentence"
```

Add a validator after the `UPLOAD_INDEXING_STRATEGY` validator:

```python
@field_validator("CHUNK_STRATEGY", mode="before")
@classmethod
def validate_chunk_strategy(cls, value):
    strategy = str(value).strip().lower()
    allowed = {"sentence", "paragraph"}
    if strategy not in allowed:
        return "sentence"
    return strategy
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_chunk_strategy.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_config_chunk_strategy.py
git commit -m "feat: add CHUNK_STRATEGY config option (sentence|paragraph)"
```

---

### Task 2: Create SmartChunker adapter in pdf_chunking.py

**Files:**
- Modify: `app/services/pdf_chunking.py:109-180` (add new function after `split_text_into_chunks`)
- Test: `tests/test_pdf_chunking.py` (add tests)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pdf_chunking.py`:

```python
class TestSmartChunkAdapter:
    def test_split_text_into_chunks_smart_basic(self):
        from app.services.pdf_chunking import split_text_into_chunks_smart

        text = "This is paragraph one.\n\nThis is paragraph two.\n\nThis is paragraph three."
        chunks = split_text_into_chunks_smart(text, chunk_size=50, overlap=10)

        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)

    def test_split_text_into_chunks_smart_empty(self):
        from app.services.pdf_chunking import split_text_into_chunks_smart

        assert split_text_into_chunks_smart("") == []
        assert split_text_into_chunks_smart("   ") == []

    def test_split_text_into_chunks_smart_returns_strings(self):
        from app.services.pdf_chunking import split_text_into_chunks_smart

        text = "Hello world. " * 100
        chunks = split_text_into_chunks_smart(text, chunk_size=100, overlap=20)

        for chunk in chunks:
            assert isinstance(chunk, str)
            assert len(chunk) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pdf_chunking.py::TestSmartChunkAdapter -v`
Expected: FAIL — `ImportError: cannot import name 'split_text_into_chunks_smart'`

- [ ] **Step 3: Implement the adapter**

In `app/services/pdf_chunking.py`, add after line 180 (end of `split_text_into_chunks`):

```python
def split_text_into_chunks_smart(
    text: str, chunk_size: int = 500, overlap: int = 100
) -> List[str]:
    """
    Split text using the SmartChunker (paragraph-aware, boundary-respecting).

    Returns plain strings to match the interface of split_text_into_chunks().
    """
    from chunking.smart_chunker import SmartChunker

    if not text or not text.strip():
        return []

    chunker = SmartChunker(chunk_size=chunk_size, overlap=overlap)
    result = chunker.chunk_document(text, extract_keywords=False)
    return [chunk["text"] for chunk in result]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pdf_chunking.py::TestSmartChunkAdapter -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/pdf_chunking.py tests/test_pdf_chunking.py
git commit -m "feat: add split_text_into_chunks_smart adapter wrapping SmartChunker"
```

---

### Task 3: Route chunking strategy in chunk_pdf_with_metadata

**Files:**
- Modify: `app/services/pdf_chunking.py:399-451` (modify `chunk_pdf_with_metadata`)
- Modify: `app/services/pdf_indexing.py:65-96` (pass strategy through)
- Modify: `django_app/views/helpers.py:111-116` (pass strategy from settings)
- Test: `tests/test_pdf_chunking.py` (add integration test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pdf_chunking.py`:

```python
class TestChunkStrategyRouting:
    def test_chunk_pdf_with_metadata_sentence_strategy(self):
        from app.services.pdf_chunking import chunk_pdf_with_metadata

        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        # Mock read_pdf_pages to return our test text
        import app.services.pdf_chunking as mod
        original = mod.read_pdf_pages
        mod.read_pdf_pages = lambda path: [{"page": 1, "text": text}]
        try:
            chunks = chunk_pdf_with_metadata(
                "fake.pdf", chunk_size=50, overlap=10, chunk_strategy="sentence"
            )
            assert len(chunks) > 0
            assert all("text" in c for c in chunks)
        finally:
            mod.read_pdf_pages = original

    def test_chunk_pdf_with_metadata_paragraph_strategy(self):
        from app.services.pdf_chunking import chunk_pdf_with_metadata

        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        import app.services.pdf_chunking as mod
        original = mod.read_pdf_pages
        mod.read_pdf_pages = lambda path: [{"page": 1, "text": text}]
        try:
            chunks = chunk_pdf_with_metadata(
                "fake.pdf", chunk_size=50, overlap=10, chunk_strategy="paragraph"
            )
            assert len(chunks) > 0
            assert all("text" in c for c in chunks)
        finally:
            mod.read_pdf_pages = original

    def test_chunk_pdf_with_metadata_default_strategy(self):
        from app.services.pdf_chunking import chunk_pdf_with_metadata

        text = "First paragraph.\n\nSecond paragraph."
        import app.services.pdf_chunking as mod
        original = mod.read_pdf_pages
        mod.read_pdf_pages = lambda path: [{"page": 1, "text": text}]
        try:
            chunks = chunk_pdf_with_metadata("fake.pdf", chunk_size=50, overlap=10)
            assert len(chunks) > 0
        finally:
            mod.read_pdf_pages = original
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pdf_chunking.py::TestChunkStrategyRouting -v`
Expected: FAIL — `TypeError: chunk_pdf_with_metadata() got an unexpected keyword argument 'chunk_strategy'`

- [ ] **Step 3: Modify chunk_pdf_with_metadata**

In `app/services/pdf_chunking.py`, modify the function signature at line 399:

```python
def chunk_pdf_with_metadata(
    pdf_path: str,
    chunk_size: int = 500,
    overlap: int = 100,
    source_name: Optional[str] = None,
    prepend_course_metadata: bool = True,
    chunk_strategy: str = "sentence",
) -> List[Dict[str, Any]]:
```

At line 429, replace the chunking call:

```python
        if chunk_strategy == "paragraph":
            page_chunks = split_text_into_chunks_smart(
                page_text, chunk_size=chunk_size, overlap=overlap
            )
        else:
            page_chunks = split_text_into_chunks(
                page_text, chunk_size=chunk_size, overlap=overlap
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pdf_chunking.py::TestChunkStrategyRouting -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/pdf_chunking.py tests/test_pdf_chunking.py
git commit -m "feat: route chunk_pdf_with_metadata through chunk_strategy param"
```

---

### Task 4: Wire config through pdf_indexing.py and helpers.py

**Files:**
- Modify: `app/services/pdf_indexing.py:65-96` (add `chunk_strategy` param to `index_pdf_file`)
- Modify: `app/services/pdf_indexing.py:152-200` (add `chunk_strategy` param to `index_pdf_directory`)
- Modify: `django_app/views/helpers.py:111-116` (pass `settings.CHUNK_STRATEGY`)
- Test: `tests/test_pdf_indexing.py` (verify param passes through)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pdf_indexing.py`:

```python
class TestChunkStrategyPassthrough:
    def test_index_pdf_file_accepts_chunk_strategy(self):
        from app.services.pdf_indexing import index_pdf_file

        import inspect
        sig = inspect.signature(index_pdf_file)
        assert "chunk_strategy" in sig.parameters
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pdf_indexing.py::TestChunkStrategyPassthrough -v`
Expected: FAIL — `AssertionError`

- [ ] **Step 3: Modify index_pdf_file signature and body**

In `app/services/pdf_indexing.py`, modify `index_pdf_file` at line 65:

```python
def index_pdf_file(
    pdf_path: str,
    chunk_size: int = 500,
    index_path: Optional[str] = None,
    model_name: Optional[str] = None,
    clear_existing: bool = False,
    chunk_strategy: str = "sentence",
) -> Dict[str, int]:
```

At line 92, pass `chunk_strategy` to the chunker:

```python
    chunk_records = parser["chunk_with_metadata"](
        pdf_path=cleaned_pdf_path,
        chunk_size=chunk_size,
        source_name=source_name,
        chunk_strategy=chunk_strategy,
    )
```

- [ ] **Step 4: Modify index_pdf_directory signature and body**

In `app/services/pdf_indexing.py`, modify `index_pdf_directory` at line 152:

```python
def index_pdf_directory(
    data_source_dir: str,
    chunk_size: int = 500,
    index_path: Optional[str] = None,
    model_name: Optional[str] = None,
    clear_existing: bool = True,
    chunk_strategy: str = "sentence",
) -> Dict[str, int]:
```

At line 184, pass `chunk_strategy` through:

```python
        stats = index_pdf_file(
            pdf_path=str(pdf_file),
            chunk_size=chunk_size,
            index_path=index_path,
            model_name=model_name,
            clear_existing=clear_existing and idx == 0,
            chunk_strategy=chunk_strategy,
        )
```

- [ ] **Step 5: Modify helpers.py to pass CHUNK_STRATEGY**

In `django_app/views/helpers.py`, at line 111, add `chunk_strategy`:

```python
            index_stats = index_pdf_directory(
                data_source_dir=settings.DOCUMENTS_PATH,
                chunk_size=settings.CHUNK_SIZE,
                index_path=settings.FAISS_INDEX_PATH,
                model_name=rt["model_id"],
                clear_existing=True,
                chunk_strategy=settings.CHUNK_STRATEGY,
            )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_pdf_indexing.py::TestChunkStrategyPassthrough -v`
Expected: 1 passed

- [ ] **Step 7: Commit**

```bash
git add app/services/pdf_indexing.py django_app/views/helpers.py tests/test_pdf_indexing.py
git commit -m "feat: wire CHUNK_STRATEGY config through indexing pipeline to chunker"
```

---

### Task 5: Run full test suite and lint

**Files:** None (verification only)

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass, including the new ones

- [ ] **Step 2: Run lint**

Run: `ruff check app/ django_app/ django_backend/ manage.py`
Expected: No errors

- [ ] **Step 3: Run format check**

Run: `black --check app/ django_app/ django_backend/ manage.py`
Expected: All files formatted

- [ ] **Step 4: Fix any issues if found**

Fix lint/format issues and re-run until clean.

- [ ] **Step 5: Final commit if needed**

```bash
git add -A
git commit -m "fix: lint and format after smart chunker integration"
```
