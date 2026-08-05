# django_app/templates/ — Django HTML Templates

Server-rendered HTML templates used by the Django backend.

## Files

| File | Purpose |
|------|---------|
| `index.html` | Main app shell — loads Vue.js SPA |
| `app.html` | Application template |
| `_chat_message.html` | Chat message partial (for server-rendered chat) |

## Notes

- The primary UI is the Vue.js SPA built to `django_app/static/frontend/`
- These templates serve as fallback or server-rendered pages
- `_chat_message.html` is a partial included by other templates
