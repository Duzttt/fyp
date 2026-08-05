# AI-Based Lecture Note Q&A System (RAG) - Project Context

## Project Overview

This is an end-to-end **Retrieval-Augmented Generation (RAG)** application for asking questions over lecture notes in PDF format. The system enables users to:

- Upload lecture PDFs
- Parse and split content into chunks (LangChain-powered)
- Embed chunks into vectors using Sentence Transformers
- Retrieve relevant chunks for questions via FAISS vector search
- Generate grounded answers using Gemini, OpenRouter, or llama.cpp with a configurable local model

### Architecture

**Backend Pipeline:**
1. `POST /api/upload` receives a PDF
2. `PDFLoader` parses PDF text using LangChain `PyPDFLoader`
3. `TextChunker` splits text with `RecursiveCharacterTextSplitter`
4. `EmbeddingService` creates embeddings with `sentence-transformers/all-MiniLM-L6-v2`
5. `VectorStore` stores vectors in FAISS index (`data/faiss_index`)
6. `POST /api/ask` retrieves top chunks and sends context + question to LLM

**Frontend:**
- React + Vite + TailwindCSS
- Components: Header, PDFUpload, QAChat, SettingsPanel
- API client in `frontend/src/services/api.js`

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Django 5.2, Pydantic, Requests |
| **RAG** | LangChain, Sentence Transformers, FAISS |
| **Frontend** | React 19, Vite, TailwindCSS, Lucide Icons |
| **LLM** | Gemini, OpenRouter, llama.cpp (Qwen is one supported model family) |
| **Testing** | Pytest, Ruff, Black, MyPy |
| **WebSocket** | Django Channels, Channels-Redis |

## Project Structure

```
AI-Based-Lecture-Note-Question-Answering-System-Using-RAG/
├── app/                          # Core RAG services
│   ├── config.py                 # Pydantic settings
│   └── services/
│       ├── chunker.py            # Text chunking
│       ├── embedding.py          # Sentence Transformers
│       ├── pdf_loader.py         # PDF parsing
│       ├── pdf_indexing.py       # PDF indexing pipeline
│       ├── rag_pipeline.py       # RAG orchestration
│       └── vector_store.py       # FAISS vector store
│
├── django_app/                   # Django app
│   ├── templates/                # HTML templates
│   ├── views.py                  # API endpoints
│   └── consumers.py              # WebSocket handlers (for dashboard)
│
├── django_backend/               # Django project config
│   ├── settings.py               # Django settings
│   ├── urls.py                   # URL routing
│   ├── asgi.py                   # ASGI/WebSocket entry
│   ├── wsgi.py                   # WSGI entry
│   ├── middleware.py             # CORS middleware
│   └── routing.py                # WebSocket routing
│
├── frontend/                     # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx
│   │   │   ├── PDFUpload.jsx
│   │   │   ├── QAChat.jsx
│   │   │   ├── SettingsPanel.jsx
│   │   │   └── Dashboard/        # Dashboard components
│   │   ├── services/
│   │   │   └── api.js            # API client
│   │   ├── App.jsx               # Main app component
│   │   └── main.jsx              # Entry point
│   └── package.json
│
├── data/                         # Runtime data
│   ├── faiss_index/              # FAISS index files
│   ├── rag_config.json           # RAG configuration
│   ├── settings.json             # UI settings
│   └── db.sqlite3                # SQLite database
│
├── media/data_source/            # Uploaded PDFs
├── tests/                        # Pytest tests
├── .env                          # Environment variables
├── .env.example                  # Environment template
├── requirements.txt              # Python dependencies
└── manage.py                     # Django management
```

## Configuration

### Environment Variables (.env)

```bash
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
DOCUMENTS_PATH=media/data_source
MAX_UPLOAD_SIZE=10485760
UPLOAD_INDEXING_STRATEGY=full_rebuild
UPLOAD_INDEXING_ASYNC=true

# LLM provider config
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta

OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Local LLM through llama.cpp
# Qwen is an example model family, not a fixed backend requirement.
LOCAL_LLM_MODEL=Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M
LOCAL_LLM_BASE_URL=http://localhost:8080
LOCAL_LLM_TIMEOUT_SECONDS=300
```

### RAG Configuration (data/rag_config.json)

```json
{
  "llm_model": "local-model",
  "top_k": 3,
  "temperature": 0.7
}
```

## Building and Running

### Backend Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env from template
cp .env.example .env
# Edit .env with your API keys

# Run development server
python manage.py runserver 0.0.0.0:8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env (optional)
cp .env.example .env

# Run development server
npm run dev
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Root page |
| `GET` | `/health` | Health check |
| `POST` | `/api/upload` | Upload PDF |
| `GET` | `/api/upload/status` | Check indexing status |
| `POST` | `/api/ask` | Ask question (basic) |
| `POST` | `/api/chat` | Ask question using the active LLM provider |
| `GET` | `/api/settings` | Get LLM settings |
| `POST` | `/api/settings` | Update LLM settings |
| `GET` | `/api/rag-config` | Get RAG config |
| `POST` | `/api/rag-config/update` | Update RAG config |
| `POST` | `/api/index/reset` | Reset FAISS index |
| `GET` | `/api/files` | List uploaded files |
| `POST` | `/api/summarize` | Summarize document |
| `POST` | `/api/podcast` | Generate podcast (placeholder) |

### Development Commands

```bash
# Tests
pytest tests/
pytest tests/test_services.py

# Lint
ruff check app/ django_app/ django_backend/ manage.py

# Format
black app/ django_app/ django_backend/ manage.py

# Type check
mypy app/ django_app/ django_backend/
```

## Key Components

### VectorStore (`app/services/vector_store.py`)

```python
class VectorStore:
    def __init__(self, index_path: str, embedding_dim: int = 384)
    def add_embeddings(self, embeddings: np.ndarray, chunks: List)
    def search(self, query_embedding: np.ndarray, top_k: int = 3)
    def search_with_metadata(self, query_embedding, top_k)
    def save(self)
    def clear(self)
    def get_total_chunks(self) -> int
```

### EmbeddingService (`app/services/embedding.py`)

```python
class EmbeddingService:
    def __init__(self, model_name: str)
    def embed_texts(self, texts: List[str]) -> np.ndarray
    def embed_query(self, query: str) -> np.ndarray
    def get_embedding_dimension(self) -> int
```

### PDF Indexing (`app/services/pdf_indexing.py`)

```python
def index_pdf_file(pdf_path, chunk_size, index_path, model_name, clear_existing) -> Dict
def index_pdf_directory(data_source_dir, chunk_size, index_path, model_name, clear_existing) -> Dict
```

## Data Flow

### Upload Flow
```
User → POST /api/upload → Save PDF → Index PDF → FAISS Index
                                    ↓
                            (chunking → embedding → storage)
```

### Query Flow
```
User → POST /api/chat → Embed query → FAISS search → Get chunks
                                              ↓
                                    Build context → LLM → Answer
```

## Development Conventions

### Python
- **Type hints**: Use typing module for function signatures
- **Error handling**: Custom exception classes per service
- **Style**: Black formatting, Ruff linting
- **Testing**: Pytest with async support

### JavaScript/React
- **Components**: Functional components with hooks
- **Styling**: TailwindCSS utility classes
- **State**: useState, useEffect for local state
- **API**: Async/await with fetch

### Git
- Conventional commits preferred
- Feature branches for new functionality

## Notes and Limitations

- PDFs must be text-based (no image-only PDFs)
- FAISS uses `IndexFlatL2` for cosine-like similarity
- Default indexing strategy: full rebuild on upload
- Async indexing supported via background thread
- WebSocket support via Django Channels for real-time updates

## Redis Configuration (for WebSocket)

For production WebSocket support, configure Redis:

```bash
# Install Redis (Ubuntu)
sudo apt install redis-server

# Start Redis
sudo systemctl start redis

# Configure in Django settings
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}
```

## Dashboard Feature (In Progress)

The RAG Index Status Dashboard provides:

- **Stats Cards**: Document count, total pages, chunk count, vector info
- **Real-time Updates**: WebSocket progress for uploads/reindexing
- **Charts**: Chunk distribution, similarity scores, document timeline
- **Config Panel**: Adjust chunk_size, overlap, embedding model

### Dashboard API Endpoints (Planned)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dashboard/stats` | Dashboard statistics |
| `GET` | `/api/dashboard/metrics` | Performance metrics |
| `GET` | `/api/dashboard/chunks/distribution` | Chunk length distribution |
| `GET` | `/api/dashboard/similarity/distribution` | Similarity score distribution |
| `GET` | `/api/dashboard/documents/timeline` | Document upload timeline |
| `POST` | `/api/dashboard/config` | Update RAG configuration |
| `POST` | `/api/dashboard/reindex` | Trigger reindexing |
| `WS` | `/ws/dashboard/` | WebSocket for real-time updates |

## Development Notes
- Always run tests after implementing RAG-related features, especially similarity thresholds and retrieval logic
- Before modifying frontend files, confirm the current architecture (Vue 3 vs Django templates) and check if files are locked or required by build system
- When implementing dashboard or UI components, reference existing design patterns from main interface for consistency
- For multi-file RAG features, create a todo list first and confirm the integration approach before writing code
