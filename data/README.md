# data/ — Runtime Data

Persistent application data: database, FAISS index, logs, and configuration.

## Files

| Path | Purpose |
|------|---------|
| `db.sqlite3` | Django ORM database (config history, query logs, system metrics) |
| `faiss_index/` | FAISS vector index files (persisted embeddings) |
| `documents/` | Uploaded PDF document metadata |
| `logs/` | Application log files |
| `settings.json` | Runtime settings cache |
| `rag_config.json` | Current RAG configuration |
| `reports.json` | Generated reports |
| `alerts.json` | System alerts |
| `retrieval_quality_results.json` | Retrieval quality evaluation results |

## Notes

- `faiss_index/` is auto-created by `app.config.get_settings()`
- `db.sqlite3` is the default Django database
- Do not commit large files in this directory
