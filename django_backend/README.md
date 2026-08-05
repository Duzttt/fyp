# django_backend/ — Django Project Configuration

Django project-level settings, URL routing, ASGI/WSGI entry points, and middleware.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Empty init |
| `settings.py` | Django settings: installed apps, middleware, database, channels, static files |
| `urls.py` | Root URL configuration — maps API routes to `django_app.views` |
| `asgi.py` | ASGI entry point (for Channels/WebSocket support) |
| `wsgi.py` | WSGI entry point (for traditional deployment) |
| `middleware.py` | Custom middleware (CORS, request logging, etc.) |
| `routing.py` | WebSocket URL routing for Django Channels |

## Key Settings

- **Database**: SQLite at `data/db.sqlite3`
- **Static files**: Served from `django_app/static/`
- **Channels**: Enabled for WebSocket support (chat, indexing progress)
- **CORS**: Configured for frontend dev server

## Entry Point

```bash
python manage.py runserver 0.0.0.0:8000
```
