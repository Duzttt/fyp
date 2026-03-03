# AI-Based Lecture Note Q&A System (RAG)

An end-to-end Retrieval-Augmented Generation (RAG) application for asking
questions over lecture notes in PDF format.

The system lets you:
- Upload lecture PDFs
- Parse and split content into chunks (LangChain-powered)
- Embed chunks into vectors
- Retrieve relevant chunks for a question
- Generate grounded answers using Gemini or OpenRouter models

## Architecture Overview

### Backend pipeline
1. `POST /api/upload` receives a PDF.
2. `PDFLoader` parses the PDF text using LangChain `PyPDFLoader`.
3. `TextChunker` splits text with LangChain
   `RecursiveCharacterTextSplitter`.
4. `EmbeddingService` creates embeddings with
   `sentence-transformers/all-MiniLM-L6-v2`.
5. `VectorStore` stores vectors in a FAISS index (`data/faiss_index`).
6. `POST /api/ask` retrieves top chunks and sends context + question to the
   configured LLM provider.

### Frontend flow
- React + Vite UI for file upload, chat, and provider settings.
- Calls backend at `VITE_API_BASE_URL` (defaults to `http://localhost:8000`).

## Tech Stack

- Backend: Django, Pydantic, Requests
- RAG:
  - Parsing: LangChain Community (`PyPDFLoader`) + `pypdf`
  - Chunking: LangChain Text Splitters (`RecursiveCharacterTextSplitter`)
  - Embeddings: Sentence Transformers
  - Vector DB: FAISS
- Frontend: React, Vite, TailwindCSS, Lucide Icons
- Testing/Linting: Pytest, Ruff, Black, MyPy

## Repository Structure

```text
django_backend/
├── settings.py
├── urls.py
├── asgi.py
├── wsgi.py
└── middleware.py

django_app/
├── apps.py
└── views.py

app/
├── services/
│   ├── chunker.py
│   ├── embedding.py
│   ├── pdf_loader.py
│   ├── rag_pipeline.py
│   └── vector_store.py
└── config.py

frontend/
├── src/
│   ├── components/
│   └── services/api.js
└── package.json

tests/
└── test_services.py
```

## Prerequisites

- Python 3.11+ recommended
- Node.js 18+ (for frontend)
- pip / virtual environment

## Setup

### 1. Backend dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

Create `.env` in the project root:

```env
# App
APP_NAME=Lecture Note Q&A System
APP_VERSION=1.0.0
DJANGO_SECRET_KEY=change-me-in-production
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Chunking
CHUNK_SIZE=400
CHUNK_OVERLAP=50

# Embeddings / Vector store
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384
FAISS_INDEX_PATH=data/faiss_index
DOCUMENTS_PATH=data/documents
MAX_UPLOAD_SIZE=10485760

# LLM provider config
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta

OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

Notes:
- `DEBUG` accepts `true/false`, and also `dev/debug` or `release/prod`.
- You can also set provider/model/API key from the UI settings panel.

### 3. Run backend

```bash
python manage.py runserver 0.0.0.0:8000
```

Backend endpoints:
- API root: `http://localhost:8000/`
- Health: `http://localhost:8000/health`

### 4. Run frontend (optional)

```bash
cd frontend
npm install
npm run dev
```

Set frontend API target (optional):

```bash
# frontend/.env
VITE_API_BASE_URL=http://localhost:8000
```

## API Reference

### `POST /api/upload`

Upload a PDF and index it for retrieval.

- Content type: `multipart/form-data`
- Field: `file` (PDF only, max 10MB by default)

Success response:

```json
{
  "success": true,
  "message": "PDF uploaded and processed successfully",
  "filename": "uuid_original.pdf",
  "chunks_created": 42
}
```

### `POST /api/ask`

Ask a question against indexed lecture content.

Request:

```json
{
  "question": "What is gradient descent?"
}
```

Response:

```json
{
  "answer": "Gradient descent is ...",
  "sources": [
    "chunk text 1 ...",
    "chunk text 2 ..."
  ]
}
```

### `GET /api/settings`

Returns persisted UI settings (provider/model, API key presence).

### `POST /api/settings`

Update LLM settings.

Request:

```json
{
  "provider": "gemini",
  "model": "gemini-2.0-flash",
  "api_key": "optional_key"
}
```

## Development Commands

### Tests

```bash
pytest tests/
pytest tests/test_services.py
pytest tests/test_services.py::TestTextChunker::test_chunk_text_returns_list
```

### Lint / format / type-check

```bash
ruff check app/ django_app/ django_backend/ manage.py
black app/ django_app/ django_backend/ manage.py
mypy app/ django_app/ django_backend/
```

Combined:

```bash
ruff check app/ django_app/ django_backend/ manage.py && black --check app/ django_app/ django_backend/ manage.py && mypy app/ django_app/ django_backend/
```

## Data and Persistence

- Uploaded files are saved to `data/documents`.
- Vector index/chunks are stored in `data/faiss_index`:
  - `index.faiss`
  - `chunks.npy`
- Re-uploading adds more chunks to the same index unless you clear it.

## Notes and Limitations

- Current ingestion expects text-based PDFs.
- If LangChain PDF dependencies are missing, upload parsing will fail with a
  clear install message.
- Retrieval currently uses top-`k` cosine-like nearest vectors in FAISS
  (`IndexFlatL2` distance).
- `ask` uses provider/model/API key from persisted `/api/settings` when present,
  and falls back to environment variables.

## License

Add your project license here (for example, MIT).
