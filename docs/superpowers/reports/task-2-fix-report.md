# Task 2 Fix Report: Embedding Model Evaluation Script

## Summary

Fixed critical issues in `scripts/evaluate_embedding_models.py` related to API mismatches and data loading.

## Issues Fixed

### 1. DenseRetriever API Mismatch (Critical)

**Problem:** The evaluator called `retriever.retrieve(query_text, top_k=top_k)` expecting `List[Dict]` with an `'id'` key, but `DenseRetriever` only exposes `search()` which returns `List[Tuple[str, float]]`.

**Solution:** Created `DenseRetrieverAdapter` class that wraps `DenseRetriever` and provides the `retrieve()` method expected by the evaluator:
```python
class DenseRetrieverAdapter:
    def __init__(self, retriever: DenseRetriever):
        self.retriever = retriever

    def retrieve(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        search_results = self.retriever.search(query, top_k=top_k)
        return [{"id": doc_id, "score": score} for doc_id, score in search_results]
```

### 2. Data Source Mismatch (Critical)

**Problem:** Script loaded from `data/faiss_index/chunks.npy`, but spec requires loading from `data/chunks/` or `data/faiss_index/chunk_metadata.json`.

**Solution:** Updated `load_chunks()` function to implement the spec's fallback logic:
1. First try loading from `data/chunks/*.json` files
2. Fallback to `data/faiss_index/chunk_metadata.json`
3. Raise `FileNotFoundError` with descriptive message if neither exists

### 3. Typo Fix (Important)

**Problem:** Line 186 had `"NCDG@10"` instead of `"NDCG@10"`.

**Solution:** Corrected to `"NDCG@10"`.

### 4. Unused Imports (Important)

**Problem:** `os` and `AggregateMetrics` were imported but not used.

**Solution:** Removed unused imports:
- Removed `import os`
- Removed `AggregateMetrics` from the import statement

## Files Changed

- `scripts/evaluate_embedding_models.py`

## Testing

- Syntax verification: `python -m py_compile scripts/evaluate_embedding_models.py` passed
- Linter check: `ruff check scripts/evaluate_embedding_models.py` shows only expected E402 warnings (module level import not at top of file due to sys.path modification)

## Notes

- The E402 warnings are expected and acceptable for this script pattern (modifying sys.path before imports)
- The adapter pattern maintains backward compatibility while providing the expected API
- Data loading now follows the spec's declared fallback logic