# app/models/ — Data Schemas

Pydantic models and data schemas used across the application for validation and serialization.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Re-exports public models |
| `schemas.py` | Pydantic models for API request/response, RAG results, document metadata |

## Usage

Import from `app.models.schemas`:
```python
from app.models.schemas import SomeModel
```
