# django_app/ — Django Application Layer

Django app handling HTTP views, WebSocket consumers, templates, static assets, and database models. This is the API and UI entry point.

## Structure

```
django_app/
├── __init__.py
├── apps.py                 # Django app config
├── models.py               # Django ORM models (ConfigHistory, QueryLog, SystemMetric, etc.)
├── admin_utils.py          # Admin dashboard utilities & health checks
├── consumers.py            # WebSocket consumers (chat, indexing progress)
├── chat_demo.html          # Standalone chat demo page
├── views/                  # All HTTP view functions (see below)
├── templates/              # Django HTML templates
│   ├── index.html          # Main app shell
│   ├── app.html            # App template
│   └── _chat_message.html  # Chat message partial
├── static/frontend/        # Built Vue.js frontend assets
└── migrations/             # Database migrations
    ├── 0001_initial.py
    └── 0002_confighistory_querylog_systemmetric_and_more.py
```

## Views (`views/`)

| View File | Endpoints |
|-----------|-----------|
| `rag.py` | `/api/ask/`, `/api/chat/`, `/api/chat/citations/` — Question answering |
| `documents.py` | `/api/upload/`, `/api/files/`, `/api/documents/` — Document operations |
| `dashboard.py` | `/api/dashboard/` — Dashboard stats |
| `rag.py` | `/api/settings/`, `/api/rag-config/`, `/api/health/llm/` — LLM and RAG settings |
| `suggestions.py` | `/api/suggestions/` — Question suggestions |
| `summaries.py` | `/api/summary/` — Document summarization |
| `embeddings.py` | `/api/settings/embedding-models/` — Embedding model info |
| `admin.py` | `/api/admin/` — Admin operations |
| `ops.py` | Health, podcast, and operational utility endpoints |
| `helpers.py` | Shared request, configuration, and indexing helpers |

## WebSocket

`consumers.py` implements Django Channels consumers for real-time chat and indexing progress notifications via `/ws/` routes.

## Static Assets

`static/frontend/` contains the built Vue.js production bundle (from `frontend/` build).
