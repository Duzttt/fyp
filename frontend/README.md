# frontend/ — Vue.js Frontend

Single-page application built with Vue 3 + Vite + Tailwind CSS. Communicates with the Django backend via REST API and WebSocket.

## Structure

```
frontend/
├── index.html              # HTML entry point
├── package.json            # Dependencies & scripts
├── vite.config.js          # Vite build config
├── tailwind.config.js      # Tailwind CSS config
├── postcss.config.js       # PostCSS config
├── public/                 # Static public assets
└── src/
    ├── main.js             # App bootstrap
    ├── App.vue             # Root component
    ├── style.css           # Global styles
    ├── services/
    │   └── api.js          # Axios HTTP client for backend API
    ├── stores/
    │   ├── documentStore.js    # Document state management
    │   ├── embeddingStore.js   # Embedding model state
    │   └── summaryStore.js     # Summary state
    └── components/
        ├── admin/          # Admin dashboard
        ├── chat/           # Chat interface
        ├── dashboard/      # Analytics dashboard
        ├── documents/      # Document viewer & comparison
        ├── layout/         # Layout panels (topbar, sources, studio)
        ├── settings/       # Settings modal & embedding selector
        ├── shared/         # Shared components (citations)
        └── studio/         # Summary viewer
```

## Dev Server

```bash
cd frontend && npm run dev
```

## Build

```bash
cd frontend && npm run build
```

Output goes to `django_app/static/frontend/` for production serving.

## API Communication

All API calls go through `src/services/api.js` which wraps Axios with the backend base URL (`http://localhost:8000`).
