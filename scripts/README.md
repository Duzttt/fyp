# scripts/ — Utility Scripts

Standalone scripts for benchmarking, quality checks, and demo purposes.

## Files

| Script | Purpose |
|--------|---------|
| `benchmark.py` | Performance benchmarking for retrieval and generation |
| `check_retrieval_quality.py` | Evaluate retrieval quality against known answers |
| `faiss_query_demo.py` | Interactive FAISS query demo |
| `pdf_to_faiss_with_metadata.py` | Standalone PDF → FAISS indexing with metadata extraction |

## Usage

```bash
python scripts/benchmark.py
python scripts/check_retrieval_quality.py
python scripts/faiss_query_demo.py
python scripts/pdf_to_faiss_with_metadata.py
```

These are development/debugging tools, not part of the main application runtime.
