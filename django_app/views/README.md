# django_app/views/ — HTTP API Views

All Django view functions handling HTTP requests. Each file maps to a group of related API endpoints.

## Files

| File | Description |
|------|-------------|
| `__init__.py` | Re-exports the split view modules |
| `_helpers.py` | Shared helpers: `_get_json_body()`, `_error_response()`, and default RAG configuration |
| `chat.py` | `ask_question`, `ask_chat`, and citation-aware question answering endpoints |
| `upload.py` | `upload_view` — PDF upload, validation, async indexing |
| `documents.py` | `documents_list_view`, `document_delete_view` — Document CRUD |
| `dashboard.py` | `dashboard_view` — System stats & metrics |
| `settings_views.py` | `settings_view`, `rag_config_view` — Get/update settings |
| `suggestions.py` | `suggestions_view` — Generate question suggestions |
| `summary.py` | `summary_view` — Document summarization |
| `embedding_views.py` | `embedding_info_view` — Embedding model details |
| `admin.py` | `admin_*` views — Admin operations & health checks |
| `misc.py` | Miscellaneous utility endpoints |

## Convention

- All views use `@require_http_methods(["GET"])` or `["POST"]`
- JSON responses via `JsonResponse`
- Errors via `_error_response(detail, status_code)` helper
- Request body parsed via `_get_json_body(request)` helper
