# app/ — Core Application Logic

Business logic layer for the RAG-based lecture note Q&A system. Contains configuration, data models, and all core services.

## Structure

```
app/
├── __init__.py
├── config.py          # Pydantic settings loaded from .env
├── utils.py           # Shared utility functions
├── models/
│   ├── __init__.py
│   └── schemas.py     # Pydantic data models / schemas
└── services/
    ├── __init__.py
    ├── embedding.py           # Sentence-transformer embeddings
    ├── vector_store.py        # FAISS vector store operations
    ├── pdf_chunking.py        # PDF text chunking logic
    ├── pdf_indexing.py        # PDF → FAISS index pipeline
    ├── local_rag.py           # RAG orchestration + local LLM calls
    ├── rag_pipeline.py        # High-level RAG pipeline
    └── question_suggestions.py # Auto-generate question suggestions
```

## Key Files

- **config.py** — All settings (`CHUNK_SIZE`, `EMBEDDING_MODEL`, `FAISS_INDEX_PATH`, `LLM_PROVIDER`, etc.) are defined here via `pydantic-settings`. Reads from `.env`.
- **services/local_rag.py** — Core RAG logic: FAISS retrieval, context building, llama.cpp generation, citation parsing.
- **services/embedding.py** — Wraps `sentence-transformers` for query/document embedding.
- **services/vector_store.py** — FAISS index load/save/search with metadata.
- **services/pdf_indexing.py** — Full pipeline: PDF → text extraction → chunking → embedding → FAISS index.
- **services/question_suggestions.py** — Uses LLM to generate follow-up questions from retrieved context.

## Dependencies

All services depend on `app.config.settings` for configuration. External deps: `sentence-transformers`, `faiss-cpu`, `httpx`, `pydantic-settings`.
