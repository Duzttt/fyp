# app/services/ — Business Logic Services

Core services implementing the RAG pipeline: embedding, vector search, LLM generation, chunking, and question suggestion.

## Files

| File | Purpose |
|------|---------|
| `embedding.py` | Sentence-transformer model loading & query/document embedding via `EmbeddingService` |
| `vector_store.py` | FAISS index CRUD: `VectorStore.get_cached()`, `search_with_metadata()`, `save()`, `load()` |
| `pdf_chunking.py` | Split extracted text into overlapping chunks (`chunk_text()`) |
| `pdf_indexing.py` | Full pipeline: PDF → extract text → chunk → embed → build FAISS index (`index_pdf()`) |
| `local_rag.py` | RAG orchestration: `retrieve_with_faiss()`, `generate_with_local_llm()`, `query_with_citations()` |
| `rag_pipeline.py` | High-level `RAGPipeline` class combining retrieval + generation |
| `question_suggestions.py` | `QuestionSuggestionService` — uses LLM to generate follow-up questions from context |
| `summarizer.py` | `SummarizerService` — LLM-based document summarization with citation support |

## LLM Integration

- **Provider**: Configurable via `settings.LLM_PROVIDER` (`local_llm` for llama.cpp)
- **Endpoint**: OpenAI-compatible API at `settings.LOCAL_LLM_BASE_URL` (default: `http://localhost:8080/v1`)
- **Model**: `settings.LOCAL_LLM_MODEL` (any model loaded by llama.cpp)
- **Timeout**: `settings.LOCAL_LLM_TIMEOUT_SECONDS` (default: 300s)

Local LLM calls use `httpx` to POST to `/chat/completions` on llama.cpp.

## Data Flow

```
PDF upload → pdf_indexing.index_pdf()
  → pdf_loader.extract_text() → pdf_chunking.chunk_text()
  → embedding.EmbeddingService.embed_documents()
  → vector_store.VectorStore.add_vectors() → save to FAISS

User query → local_rag.retrieve_with_faiss()
  → embedding.embed_query() → vector_store.search_with_metadata()
  → local_rag.generate_with_local_llm() → llama.cpp API → answer
```
