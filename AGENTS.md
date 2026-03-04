# AGENTS.md - Development Guidelines

## Project Overview
This is an AI-based Lecture Note Question Answering System using
Retrieval-Augmented Generation (RAG). The backend is built with Django and
uses sentence-transformers for embeddings, FAISS for vector storage, and
integrates with LLM APIs via Gemini/OpenRouter/Ollama.

## Build / Lint / Test Commands

### Installation
```bash
pip install -r requirements.txt
```

### Running the Application
```bash
python manage.py runserver 0.0.0.0:8000
```

### Running Tests
```bash
pytest tests/                          # Run all tests
pytest tests/test_name.py              # Run specific test file
pytest tests/test_name.py::test_func   # Run single test
pytest -v                              # Verbose output
pytest --tb=short                      # Short traceback format
```

### Linting & Code Quality
```bash
ruff check app/ django_app/ django_backend/ manage.py
ruff check app/ django_app/ django_backend/ manage.py --fix
black app/ django_app/ django_backend/ manage.py
mypy app/ django_app/ django_backend/
```

### Combined Quality Check
```bash
ruff check app/ django_app/ django_backend/ manage.py && black --check app/ django_app/ django_backend/ manage.py && mypy app/ django_app/ django_backend/
```

## Code Style Guidelines

### Imports
- Use absolute imports (e.g., `from app.services.pdf_loader import PDFLoader`)
- Group imports in order: standard library, third-party, local application
- Use `__all__` in modules to explicitly declare public API
- Example import order:
  ```python
  import json
  import os
  from typing import Any, Dict, List, Optional
  
  import httpx
  import requests
  from django.conf import settings
  
  from app.config import settings
  from app.services.pdf_loader import PDFLoader
  ```

### Formatting
- Line length: 88 characters (Black default)
- Use 4 spaces for indentation (no tabs)
- Add trailing commas in multi-line constructs
- Use f-strings for string formatting (no `.format()` or `%` formatting)
- Max line length: 88 characters (Black default)

### Types
- Always use type hints for function arguments and return values
- Use `Optional[X]` instead of `X | None` for Python 3.9 compatibility
- Use `List`, `Dict`, `Set` from typing module for Python 3.9 compatibility
- Add docstrings with parameter types for complex functions

### Naming Conventions
- Variables: `snake_case` (e.g., `pdf_file`, `embedding_dim`)
- Functions: `snake_case` (e.g., `extract_text`, `chunk_text`)
- Classes: `PascalCase` (e.g., `PDFLoader`, `RAGPipeline`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `CHUNK_SIZE`, `OVERLAP_SIZE`)
- Private methods/attributes: prefix with underscore (e.g., `_private_method`)
- Django views: suffix with `_view` or use descriptive names (e.g., `upload_pdf`, `ask_question`)

### Error Handling
- Use custom exception classes for domain-specific errors (e.g., `PDFIndexingError`, `LocalRAGError`)
- Always catch specific exceptions, never bare `except:`
- Log errors with appropriate severity levels
- Return meaningful HTTP status codes and error messages in API responses
- Use consistent JSON error payloads with a `detail` field
- Use helper function `_error_response(detail, status_code)` for API errors
- Follow this pattern in Django views:
  ```python
  try:
      # business logic
  except SpecificError as exc:
      return _error_response(str(exc), status=400)
  except Exception as exc:  # noqa: BLE001
      return _error_response(f"Failed to process: {str(exc)}", status=500)
  ```

### Architecture Patterns
- Keep business logic in `app/services` and call it from Django views
- Keep request parsing and HTTP responses in Django views
- Use Pydantic models where strict validation is needed
- Keep configuration in `app/config.py` (no hardcoded values)
- Avoid global mutable state; use module-level constants for configuration
- Use thread locks (`threading.Lock()`) for shared state across requests

### Module Structure
```text
django_backend/       # Django project settings/urls/asgi/wsgi
django_app/           # Django API views
app/
├── config.py         # Settings and configuration
├── api/             # API endpoints
├── models/          # Data models
└── services/         # Business logic
    ├── pdf_loader.py         # PDF text extraction
    ├── pdf_indexing.py      # PDF indexing to FAISS
    ├── chunker.py            # Text chunking
    ├── embedding.py          # Sentence embeddings
    ├── vector_store.py       # FAISS vector storage
    ├── local_rag.py          # RAG orchestration
    └── rag_pipeline.py       # RAG pipeline
```

### Django View Patterns
- Use decorators: `@require_http_methods(["GET"])`, `@csrf_exempt` when needed
- Use `_get_json_body(request)` helper to parse JSON payloads
- Use `_error_response(detail, status)` helper for consistent error responses
- Return `JsonResponse` for API endpoints, `HttpResponse` for HTML
- Validate file uploads early with clear error messages

### Configuration
- All settings in `app/config.py` via pydantic-settings
- Environment variables in `.env` file
- Key settings: `DOCUMENTS_PATH`, `FAISS_INDEX_PATH`, `CHUNK_SIZE`, `EMBEDDING_MODEL`
- LLM settings: `LLM_PROVIDER`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `LOCAL_QWEN_MODEL`

### Testing Guidelines
- Use pytest as the testing framework
- Place tests in `tests/` directory mirroring app structure
- Use fixtures for common test setup
- Mock external dependencies (LLM API, file system, FAISS)
- Test both success and error paths
- Use descriptive test names: `test_<method>_<expected_behavior>`
- Example test pattern:
  ```python
  def test_upload_pdf_valid_file(self):
      # Arrange
      fake_pdf = b"%PDF-1.4 fake pdf content"
      
      # Act
      response = self.client.post('/api/upload/', {'file': fake_pdf})
      
      # Assert
      assert response.status_code == 200
  ```

### API Design Principles
- RESTful conventions: POST for create, GET for retrieve
- Return JSON responses with appropriate status codes
- Include source chunks in ask endpoint response for transparency
- Validate file uploads (PDF only, size limits)
- Use 202 Accepted for async operations
- Use 400 for validation errors, 500 for server errors, 503 for service unavailable

### Future Extensibility
- Prepare for OCR extension in `pdf_loader` (text-based PDFs first)
- Keep LLM provider/model configurable
- Consider chunking strategy as configurable parameter
- Design vector store to support multiple document indices

### Common Development Patterns

#### Async PDF Indexing
- Use threading for background indexing jobs
- Use `threading.Lock()` to protect shared state
- Track indexing status: idle, queued, running, completed, failed

#### RAG Pipeline Flow
1. `retrieve_with_faiss(query, top_k, source_filter)` - search vector store
2. `build_context_from_sources(sources)` - format context for LLM
3. `generate_with_local_qwen(query, context)` or Ollama client - generate answer

#### File Upload Flow
1. Validate file type (PDF only) and size
2. Generate safe filename (handle duplicates)
3. Save PDF to documents directory
4. Index PDF to FAISS (full rebuild or append)
5. Return success response with stats
