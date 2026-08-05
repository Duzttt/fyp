# frontend/src/ — Frontend Source Code

Vue 3 application source: components, services, stores, and styles.

## Files

| File | Purpose |
|------|---------|
| `main.js` | App bootstrap — creates Vue app, mounts to `#app` |
| `App.vue` | Root component — layout shell, router-like view switching |
| `style.css` | Global Tailwind CSS imports and custom styles |

## Directories

| Directory | Purpose |
|-----------|---------|
| `services/api.js` | Axios instance configured with backend URL; all API call functions |
| `stores/` | Pinia/Vuex stores for state management (documents, embeddings, summaries) |
| `components/` | All Vue components organized by feature area |

## Component Organization

Components follow a feature-based folder structure:
- `admin/` — Admin dashboard panels & tabs
- `chat/` — Chat input, messages, citations, suggestions
- `dashboard/` — Analytics charts, stats, indexing progress
- `documents/` — PDF viewer, comparison view
- `layout/` — Topbar, sources panel, studio panel
- `settings/` — Settings modal, embedding model selector
- `shared/` — Reusable components (bidirectional citations)
- `studio/` — Summary modal & viewer
