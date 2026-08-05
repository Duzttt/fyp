# tests/ — Test Suite

Pytest-based tests covering services, views, chunking, retrieval, and integration.

## Files

| Test File | What It Tests |
|-----------|---------------|
| `conftest.py` | Shared fixtures (temp dirs, mock LLM, test client) |
| `test_services.py` | Core services: embedding, vector store, PDF loading |
| `test_rag.py` | RAG pipeline: retrieval + generation end-to-end |
| `test_citation_rag.py` | Citation generation and parsing |
| `test_chunking.py` | Text chunking logic |
| `test_pdf_indexing.py` | PDF → FAISS indexing pipeline |
| `test_hybrid_retrieval.py` | Hybrid (dense + BM25) retrieval |
| `test_source_grounding.py` | Source grounding validation |
| `test_question_suggestions.py` | Question suggestion generation |
| `test_django_ask_view.py` | `/api/ask/` endpoint |
| `test_django_chat_view.py` | Primary `/api/chat` endpoint |
| `test_django_upload.py` | `/api/upload/` endpoint |
| `test_django_documents_view.py` | `/api/documents/` endpoint |
| `test_django_files_view.py` | File management endpoints |

## Running Tests

```bash
pytest tests/                    # All tests
pytest tests/test_rag.py         # Specific file
pytest -v                        # Verbose output
```

## Conventions

- Use `monkeypatch` to mock external services (LLM API, FAISS)
- Test both success and error paths
- Fixtures in `conftest.py` for shared setup
