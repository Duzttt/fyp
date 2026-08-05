# frontend/src/services/ — API Services

HTTP client and API communication layer.

## Files

| File | Purpose |
|------|---------|
| `api.js` | Axios instance with backend base URL; all API call functions |

## Usage

```javascript
import api from '@/services/api'
const response = await api.post('/api/ask/', { question: '...' })
```

## Base URL

Configured to `http://localhost:8000` (Django backend).
