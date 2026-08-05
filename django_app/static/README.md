# django_app/static/ — Django Static Files

Collected static files served by Django in production.

## Structure

```
static/
└── frontend/     # Built Vue.js SPA (from `frontend/` build output)
    └── assets/   # JS, CSS, and media bundles
```

## Notes

- This directory contains the production build of the Vue.js frontend
- Built via `cd frontend && npm run build`
- Django serves these files when `DEBUG=False`
- Do not edit files here directly — modify source in `frontend/src/`
