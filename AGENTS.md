# AGENTS.md - Development Guidelines

## Project Overview
This is an AI-based Lecture Note Question Answering System using Retrieval-Augmented Generation (RAG). The backend is built with FastAPI and uses sentence-transformers for embeddings, FAISS for vector storage, and integrates with LLM APIs via OpenRouter.

## Build / Lint / Test Commands

### Installation
```bash
pip install -r requirements.txt
```

### Running the Application
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests
```bash
pytest tests/                          # Run all tests
pytest tests/test_name.py              # Run specific test file
pytest tests/test_name.py::test_func   # Run single test
pytest -v                             # Verbose output
pytest --tb=short                     # Short traceback format
```

### Linting & Code Quality
```bash
ruff check app/                       # Lint the app directory
ruff check app/ --fix                 # Auto-fix linting issues
black app/                            # Format code
mypy app/                            # Type checking
```

### Combined Quality Check
```bash
ruff check app/ && black --check app/ && mypy app/
```

## Code Style Guidelines

### Imports
- Use absolute imports (e.g., `from app.services.pdf_loader import PDFLoader`)
- Group imports in order: standard library, third-party, local application
- Use `__all__` in modules to explicitly declare public API

### Formatting
- Line length: 88 characters (Black default)
- Use 4 spaces for indentation (no tabs)
- Add trailing commas in multi-line constructs
- Use f-strings for string formatting (no .format() or % formatting)

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

### Error Handling
- Use custom exception classes for domain-specific errors
- Always catch specific exceptions, never bare `except:`
- Log errors with appropriate severity levels
- Return meaningful HTTP status codes and error messages in API responses
- Use FastAPI's HTTPException for API-level errors

### Architecture Patterns
- Use dependency injection via FastAPI's Depends() for services
- Separate business logic from API routes (services layer)
- Use Pydantic models for request/response validation
- Keep configuration in config.py (no hardcoded values)
- Avoid global variables; use dependency injection instead

### Module Structure
```
app/
├── main.py           # FastAPI app factory, event handlers, middleware
├── config.py         # Settings and configuration
├── api/              # API route handlers
│   ├── upload.py     # POST /api/upload endpoint
│   └── ask.py        # POST /api/ask endpoint
├── services/         # Business logic (dependency injectable)
│   ├── pdf_loader.py     # PDF text extraction
│   ├── chunker.py        # Text chunking
│   ├── embedding.py      # Sentence embeddings
│   ├── vector_store.py   # FAISS vector storage
│   └── rag_pipeline.py   # RAG orchestration
└── models/           # Pydantic schemas
    └── schemas.py    # Request/response models
```

### Testing Guidelines
- Use pytest as the testing framework
- Place tests in `tests/` directory mirroring app structure
- Use fixtures for common test setup
- Mock external dependencies (LLM API, file system)
- Test both success and error paths
- Use descriptive test names: `test_<method>_<expected_behavior>`

### API Design Principles
- RESTful conventions: POST for create, GET for retrieve
- Return JSON responses with appropriate status codes
- Include source chunks in ask endpoint response for transparency
- Validate file uploads (PDF only, size limits)
- Handle async operations properly with asyncio

### Future Extensibility
- Prepare for OCR extension in pdf_loader (text-based PDFs first)
- Make LLM provider configurable (currently OpenRouter)
- Consider chunking strategy as configurable parameter
- Design vector store to support multiple document indices
