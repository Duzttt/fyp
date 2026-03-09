# Frontend Development Guide

## Architecture

- **Frontend (Vue 3 + Vite)**: Main UI and user interactions
  - Runs on `http://localhost:5173` (dev) or served by Django (production)
  - Handles all user-facing pages and interactions
  - PDF viewing with PDF.js integration
  - Retrieval visualization with tooltips
  - Bidirectional citation tracing

- **Backend (Django)**: API server + static file hosting
  - Runs on `http://localhost:8000`
  - Provides REST API endpoints (`/api/*`)
  - Serves media files (`/media/*`)
  - Hosts built frontend static files

## Development Workflow

### Option 1: Development Mode (Recommended for active development)

1. **Start Django backend** (API server):
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

2. **Start Vite dev server** (in a separate terminal):
   ```bash
   cd frontend
   npm run dev
   ```

3. **Access the application**:
   - Open `http://localhost:5173` in your browser
   - Vite will proxy `/api` and `/media` requests to Django

### Option 2: Production Mode (Test the final build)

1. **Build the frontend**:
   ```bash
   cd frontend
   npm run build
   ```

2. **Start Django** (will serve both API and frontend):
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

3. **Access the application**:
   - Open `http://localhost:8000` in your browser
   - Django serves the built Vue app from `/static/frontend/`

## Features

### Retrieval Visualization
- Click on any retrieved chunk to view the source PDF
- Hover over chunks to see preview tooltips
- Right-click on chunks to see bidirectional citations

### PDF Viewer
- View PDF pages with navigation controls
- Zoom in/out for better readability
- Text highlighting for matched content

### Bidirectional Tracing
- Right-click on any retrieved chunk
- See all answers that cited this text
- Click to navigate back to the original answer

### Multi-Document Comparison
- Toggle compare mode with the ⚖ button in Sources panel
- Select 2-3 documents using checkboxes
- Enter a question to compare answers across documents
- View answers side-by-side in dynamic columns
- Automatic difference analysis highlighting:
  - **Common points** (blue) - information present in all answers
  - **Different points** (yellow) - unique information per document
- Save comparison results as notes
- Export comparison as Markdown file

### RAG Index Dashboard
- Click "📊 Dashboard" button in topbar
- Real-time statistics:
  - Document count, total pages, chunk count
  - Vector information (dimension, index type, total vectors)
  - Performance metrics (retrieval time, embedding time)
  - Storage information (FAISS index size, document storage size)
- Interactive charts:
  - Chunk length distribution histogram
  - Similarity score distribution chart
  - Document upload timeline
- Live WebSocket updates (every 5 seconds)
- Configuration panel:
  - Adjust chunk_size and chunk_overlap
  - Change top_k and temperature parameters
  - One-click rebuild index

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload PDF file |
| `POST` | `/api/chat` | Ask question (RAG) |
| `POST` | `/api/compare` | Compare answers across multiple documents |
| `GET` | `/api/files` | List uploaded files |
| `POST` | `/api/documents/delete` | Delete a file |
| `GET` | `/api/settings` | Get LLM settings |
| `POST` | `/api/settings` | Save LLM settings |
| `GET` | `/api/rag-config` | Get RAG config |
| `POST` | `/api/rag-config/update` | Update RAG config |
| `POST` | `/api/index/reset` | Reset FAISS index |
| `GET` | `/api/dashboard/stats` | Get dashboard statistics |
| `GET` | `/api/dashboard/metrics` | Get performance metrics |
| `GET` | `/api/dashboard/chunks/distribution` | Get chunk length distribution |
| `GET` | `/api/dashboard/similarity/distribution` | Get similarity score distribution |
| `GET` | `/api/dashboard/documents/timeline` | Get document upload timeline |
| `POST` | `/api/dashboard/reindex` | Rebuild entire index |
| `WS` | `/ws/dashboard/` | WebSocket for real-time dashboard updates |

## Project Structure

```
AI-Based-Lecture-Note-Question-Answering-System/
├── frontend/                    # Vue 3 frontend source
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatPanel.vue
│   │   │   ├── RetrievalChunks.vue
│   │   │   ├── PdfViewer.vue
│   │   │   └── BidirectionalCitations.vue
│   │   ├── App.vue
│   │   └── main.js
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
├── django_app/
│   ├── static/frontend/        # Built frontend (generated)
│   ├── templates/
│   └── views.py                # API handlers
│
├── django_backend/
│   ├── settings.py
│   └── urls.py
│
└── media/data_source/          # Uploaded PDFs
```

## Troubleshooting

### Frontend not loading
1. Make sure frontend is built: `npm run build`
2. Check that `django_app/static/frontend/` contains files
3. Restart Django server

### API requests failing
1. Ensure Django is running on port 8000
2. Check CORS settings in `django_backend/settings.py`
3. Verify API endpoint URLs in frontend API client

### PDF not displaying
1. Check that PDF.js is loaded (check browser console)
2. Verify PDF file exists in `media/data_source/`
3. Check browser console for CORS errors
