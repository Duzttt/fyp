# Embedding Model Evaluation Design

## Overview

Evaluate 4 embedding models using the existing retrieval evaluator, compare performance, and generate a report with the best model recommendation for the RAG system.

## Models to Evaluate

| Model | Dimension | Size | Speed |
|-------|-----------|------|-------|
| BAAI/bge-m3 | 1024 | ~2.3GB | Medium |
| jina-embeddings-v3 | 1024 | ~570MB | Medium |
| BAAI/bge-large-en-v1.5 | 1024 | ~1.2GB | Medium |
| intfloat/e5-large-v2 | 1024 | ~1.3GB | Medium |

## Evaluation Metrics

- Recall@5
- Precision@5
- MRR (Mean Reciprocal Rank)
- NDCG@5
- p95 latency (95th percentile retrieval time)

## Implementation Plan

### Step 1: Add jina-embeddings-v3 to Model Registry

**File:** `app/services/embedding_manager.py`

Add to `MODEL_REGISTRY`:
```python
"jinaai/jina-embeddings-v3": {
    "name": "Jina Embeddings v3",
    "dimension": 1024,
    "speed": "Medium",
    "memory": "~570 MB",
    "description": "Jina's latest multilingual embedding model",
    "recommended": False
}
```

### Step 2: Create Evaluation Script

**File:** `scripts/evaluate_embedding_models.py`

```python
"""
Evaluate 4 embedding models against retrieval benchmark.
Compares: bge-m3, jina-embeddings-v3, bge-large-en-v1.5, e5-large-v2
"""
```

**Logic:**
1. Load benchmark data from `data/evaluation/retrieval_benchmark.jsonl`
2. For each model:
   - Load SentenceTransformer model
   - Embed all document chunks
   - Build FAISS index (IndexFlatIP with L2 normalization)
   - Run retrieval for all 33 queries
   - Compute metrics using RetrievalEvaluator
3. Generate comparison report
4. Save to `data/evaluation/embedding_model_comparison_report.txt`

### Step 3: Generate Report

**Output format:**
```
Embedding Model Comparison Report
=================================
Date: 2026-08-07
Benchmark: 33 queries (retrieval_benchmark.jsonl)

Models Evaluated:
1. BAAI/bge-m3 (1024d, ~2.3GB)
2. jinaai/jina-embeddings-v3 (1024d, ~570MB)
3. BAAI/bge-large-en-v1.5 (1024d, ~1.2GB)
4. intfloat/e5-large-v2 (1024d, ~1.3GB)

Results:
| Model | Recall@5 | Precision@5 | MRR | NDCG@5 | p95 Latency |
|-------|----------|-------------|-----|--------|-------------|
| bge-m3 | 0.XXX | 0.XXX | 0.XXX | 0.XXX | X.XXms |
| ... | ... | ... | ... | ... | ... |

Best Model: [name]
Score: Recall@5=0.XXX, MRR=0.XXX, NDCG@5=0.XXX
```

## Files to Modify

1. `app/services/embedding_manager.py` — Add jina-embeddings-v3 to registry
2. `scripts/evaluate_embedding_models.py` — New evaluation script (create)

## Files to Reference

- `evaluation/retrieval_evaluator.py` — Existing evaluator with compare()
- `data/evaluation/retrieval_benchmark.jsonl` — 33-query benchmark dataset
- `app/services/vector_store.py` — FAISS index setup patterns

## Dependencies

No new dependencies required — uses existing:
- sentence-transformers
- faiss-cpu
- evaluation/retrieval_evaluator.py
