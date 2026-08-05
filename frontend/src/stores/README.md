# frontend/src/stores/ — State Management

Pinia/Vuex stores for managing application state across components.

## Files

| Store | Purpose |
|-------|---------|
| `documentStore.js` | Document list, selection, upload state |
| `embeddingStore.js` | Embedding model selection and status |
| `summaryStore.js` | Document summary generation state |

## Usage

```javascript
import { useDocumentStore } from '@/stores/documentStore'
const store = useDocumentStore()
```
