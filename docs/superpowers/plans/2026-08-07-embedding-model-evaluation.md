# Embedding Model Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate 4 embedding models (bge-m3, jina-embeddings-v3, bge-large-en-v1.5, e5-large-v2) against the retrieval benchmark and generate a comparison report.

**Architecture:** Add jina-embeddings-v3 to the existing model registry, create a standalone evaluation script that builds FAISS indexes for each model, runs retrieval against the 33-query benchmark, computes metrics using the existing RetrievalEvaluator, and generates a text comparison report.

**Tech Stack:** Python, sentence-transformers, faiss-cpu, existing evaluation/retrieval_evaluator.py

## Global Constraints

- Python 3.9+ compatibility
- Use existing `evaluation/retrieval_evaluator.py` `RetrievalEvaluator` class
- Use existing `retrieval/dense_retriever.py` `DenseRetriever` class
- Benchmark data: `data/evaluation/retrieval_benchmark.jsonl` (33 queries)
- Document chunks must be loaded from FAISS index or rebuilt from source PDFs

---

### Task 1: Add jina-embeddings-v3 to Model Registry

**Files:**
- Modify: `app/services/embedding_manager.py:186-193`

**Interfaces:**
- Consumes: None
- Produces: Updated `AVAILABLE_MODELS` dict with jina-embeddings-v3 entry

- [ ] **Step 1: Add jina-embeddings-v3 to AVAILABLE_MODELS**

Open `app/services/embedding_manager.py` and add after the `BAAI/bge-m3` entry (line 193):

```python
        "jinaai/jina-embeddings-v3": {
            "name": "Jina Embeddings v3",
            "dimension": 1024,
            "speed": "Medium",
            "memory": "~570 MB",
            "description": "Jina's latest multilingual embedding model",
            "recommended": False,
        },
```

- [ ] **Step 2: Verify the registry loads**

Run: `python -c "from app.services.embedding_manager import EmbeddingModelManager; m = EmbeddingModelManager(); print('jinaai/jina-embeddings-v3' in m.AVAILABLE_MODELS)"`
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add app/services/embedding_manager.py
git commit -m "feat: add jina-embeddings-v3 to model registry"
```

---

### Task 2: Create Embedding Model Evaluation Script

**Files:**
- Create: `scripts/evaluate_embedding_models.py`

**Interfaces:**
- Consumes: `evaluation/retrieval_evaluator.py` (RetrievalEvaluator, load_benchmark)
- Consumes: `retrieval/dense_retriever.py` (DenseRetriever)
- Produces: `data/evaluation/embedding_model_comparison_report.txt`

- [ ] **Step 1: Create the evaluation script skeleton**

Create `scripts/evaluate_embedding_models.py`:

```python
"""
Evaluate 4 embedding models against retrieval benchmark.

Compares: BAAI/bge-m3, jinaai/jina-embeddings-v3, BAAI/bge-large-en-v1.5, intfloat/e5-large-v2

Usage:
    python scripts/evaluate_embedding_models.py
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.retrieval_evaluator import RetrievalEvaluator
from retrieval.dense_retriever import DenseRetriever


# Models to evaluate
MODELS_TO_EVALUATE = [
    "BAAI/bge-m3",
    "jinaai/jina-embeddings-v3",
    "BAAI/bge-large-en-v1.5",
    "intfloat/e5-large-v2",
]

# Paths
BENCHMARK_PATH = PROJECT_ROOT / "data" / "evaluation" / "retrieval_benchmark.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation"
OUTPUT_FILE = OUTPUT_DIR / "embedding_model_comparison_report.txt"


def load_documents_from_chunks(chunks_dir: str = None) -> List[Dict[str, Any]]:
    """
    Load document chunks for indexing.
    
    Looks for existing chunks in data/chunks/ or falls back to
    rebuilding from the vector store.
    """
    # Try loading from existing chunks directory
    chunks_path = PROJECT_ROOT / "data" / "chunks"
    if chunks_path.exists():
        documents = []
        for chunk_file in chunks_path.glob("*.json"):
            with open(chunk_file, "r", encoding="utf-8") as f:
                chunk_data = json.load(f)
                if isinstance(chunk_data, list):
                    documents.extend(chunk_data)
                else:
                    documents.append(chunk_data)
        if documents:
            return documents
    
    # Fallback: try loading from FAISS index metadata
    index_path = PROJECT_ROOT / "data" / "faiss_index"
    if index_path.exists():
        metadata_file = index_path / "chunk_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
    
    raise FileNotFoundError(
        "No document chunks found. Please ensure data/chunks/ or "
        "data/faiss_index/chunk_metadata.json exists."
    )


def build_retriever_for_model(
    model_id: str,
    documents: List[Dict[str, Any]],
) -> DenseRetriever:
    """
    Build a DenseRetriever for a specific embedding model.
    
    Args:
        model_id: HuggingFace model ID
        documents: List of document dicts with 'id' and 'text' keys
        
    Returns:
        DenseRetriever instance ready for retrieval
    """
    print(f"  Loading model: {model_id}")
    start = time.time()
    
    retriever = DenseRetriever(
        documents=documents,
        model_name=model_id,
    )
    
    elapsed = time.time() - start
    print(f"  Model loaded and indexed in {elapsed:.1f}s")
    
    return retriever


def evaluate_models(
    models: List[str],
    documents: List[Dict[str, Any]],
    top_k: int = 10,
) -> Dict[str, Any]:
    """
    Evaluate all models and return comparison results.
    
    Args:
        models: List of model IDs to evaluate
        documents: Document chunks for indexing
        top_k: Number of results to retrieve
        
    Returns:
        Dict with model results and comparison data
    """
    # Load benchmark
    print(f"Loading benchmark from {BENCHMARK_PATH}")
    benchmark_queries = RetrievalEvaluator.load_benchmark(str(BENCHMARK_PATH))
    print(f"Loaded {len(benchmark_queries)} queries")
    
    results = {}
    
    for model_id in models:
        print(f"\n{'='*60}")
        print(f"Evaluating: {model_id}")
        print(f"{'='*60}")
        
        # Build retriever
        retriever = build_retriever_for_model(model_id, documents)
        
        # Create evaluator
        evaluator = RetrievalEvaluator(test_queries=benchmark_queries)
        
        # Run evaluation
        print(f"  Running retrieval evaluation (top_k={top_k})...")
        aggregate, detail_results = evaluator.evaluate(retriever, top_k=top_k)
        
        # Generate report for this model
        report = evaluator.generate_report(aggregate, detail_results)
        print(report)
        
        results[model_id] = {
            "aggregate": aggregate.to_dict(),
            "report": report,
        }
    
    return results


def generate_comparison_report(results: Dict[str, Any]) -> str:
    """
    Generate a comparison report across all models.
    
    Args:
        results: Dict of model results from evaluate_models()
        
    Returns:
        Formatted comparison report string
    """
    lines = [
        "=" * 70,
        "EMBEDDING MODEL COMPARISON REPORT",
        "=" * 70,
        "",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Benchmark: {BENCHMARK_PATH.name} ({len(results)} models evaluated)",
        "",
        "Models Evaluated:",
        "-" * 40,
    ]
    
    # List models with their specs
    model_specs = {
        "BAAI/bge-m3": "1024d, ~2.3GB, Medium speed",
        "jinaai/jina-embeddings-v3": "1024d, ~570MB, Medium speed",
        "BAAI/bge-large-en-v1.5": "1024d, ~1.2GB, Medium speed",
        "intfloat/e5-large-v2": "1024d, ~1.3GB, Medium speed",
    }
    
    for i, model_id in enumerate(results.keys(), 1):
        spec = model_specs.get(model_id, "unknown")
        lines.append(f"{i}. {model_id} ({spec})")
    
    lines.extend(["", ""])
    
    # Results table header
    lines.append("Results Summary:")
    lines.append("-" * 70)
    header = f"{'Model':<35} {'Recall@5':>10} {'MRR':>10} {'NDCG@5':>10} {'p95(ms)':>10}"
    lines.append(header)
    lines.append("-" * 70)
    
    # Find best model
    best_model = None
    best_score = -1
    
    for model_id, data in results.items():
        agg = data["aggregate"]
        recall_5 = agg.get("recall_at_5", 0)
        mrr = agg.get("mrr", 0)
        ndcg_5 = agg.get("ndcg_at_5", 0)
        p95 = agg.get("p95_latency_ms", 0)
        
        # Combined score: weighted average of recall, MRR, NDCG
        combined_score = (recall_5 * 0.4) + (mrr * 0.3) + (ndcg_5 * 0.3)
        
        if combined_score > best_score:
            best_score = combined_score
            best_model = model_id
        
        # Truncate model name for display
        short_name = model_id.split("/")[-1][:33]
        lines.append(
            f"{short_name:<35} {recall_5:>10.4f} {mrr:>10.4f} {ndcg_5:>10.4f} {p95:>10.2f}"
        )
    
    lines.extend(["", ""])
    
    # Best model recommendation
    lines.append("=" * 70)
    lines.append("BEST MODEL RECOMMENDATION")
    lines.append("=" * 70)
    lines.append("")
    
    if best_model:
        best_agg = results[best_model]["aggregate"]
        lines.append(f"Recommended Model: {best_model}")
        lines.append(f"  Recall@5:   {best_agg.get('recall_at_5', 0):.4f}")
        lines.append(f"  MRR:        {best_agg.get('mrr', 0):.4f}")
        lines.append(f"  NDCG@5:     {best_agg.get('ndcg_at_5', 0):.4f}")
        lines.append(f"  p95 Latency: {best_agg.get('p95_latency_ms', 0):.2f}ms")
        lines.append("")
        lines.append(
            "This model achieves the best balance of retrieval quality "
            "(Recall, MRR, NDCG) across the benchmark queries."
        )
    
    lines.extend(["", "=" * 70])
    
    return "\n".join(lines)


def main():
    """Main entry point for embedding model evaluation."""
    print("=" * 60)
    print("Embedding Model Evaluation")
    print("=" * 60)
    
    # Load documents
    print("\nLoading document chunks...")
    try:
        documents = load_documents_from_chunks()
        print(f"Loaded {len(documents)} document chunks")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Evaluate models
    results = evaluate_models(MODELS_TO_EVALUATE, documents, top_k=5)
    
    # Generate comparison report
    print("\n" + "=" * 60)
    print("Generating comparison report...")
    comparison_report = generate_comparison_report(results)
    
    # Save report
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(comparison_report)
    
    print(f"\nReport saved to: {OUTPUT_FILE}")
    print("\n" + comparison_report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify script syntax**

Run: `python -m py_compile scripts/evaluate_embedding_models.py`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add scripts/evaluate_embedding_models.py
git commit -m "feat: add embedding model evaluation script"
```

---

### Task 3: Test Script Loads Correctly

**Files:**
- Test: `scripts/evaluate_embedding_models.py`

**Interfaces:**
- Consumes: None
- Produces: Verification that imports work

- [ ] **Step 1: Test imports work**

Run: `python -c "from scripts.evaluate_embedding_models import MODELS_TO_EVALUATE, load_documents_from_chunks; print('Models:', MODELS_TO_EVALUATE)"`
Expected: `Models: ['BAAI/bge-m3', 'jinaai/jina-embeddings-v3', 'BAAI/bge-large-en-v1.5', 'intfloat/e5-large-v2']`

- [ ] **Step 2: Test document loading**

Run: `python -c "from scripts.evaluate_embedding_models import load_documents_from_chunks; docs = load_documents_from_chunks(); print(f'Loaded {len(docs)} chunks')"`
Expected: `Loaded N chunks` (where N > 0)

If this fails, the script will exit with an error message about missing chunks.

- [ ] **Step 3: Commit**

```bash
git add scripts/evaluate_embedding_models.py
git commit -m "test: verify evaluation script imports and document loading"
```

---

### Task 4: Run Evaluation (Manual Execution)

**Files:**
- Execute: `scripts/evaluate_embedding_models.py`
- Output: `data/evaluation/embedding_model_comparison_report.txt`

**Interfaces:**
- Consumes: All 4 embedding models (downloads on first run)
- Consumes: Document chunks from data/chunks/ or data/faiss_index/
- Produces: Comparison report text file

- [ ] **Step 1: Run the evaluation script**

Run: `python scripts/evaluate_embedding_models.py`

**Note:** This will:
1. Download 4 embedding models (~4.5GB total) on first run
2. Build FAISS indexes for each model
3. Run 33 queries x 4 models = 132 retrieval operations
4. Generate comparison report

**Expected runtime:** 5-15 minutes depending on hardware.

- [ ] **Step 2: Verify output file exists**

Run: `Test-Path -LiteralPath "data\evaluation\embedding_model_comparison_report.txt"`
Expected: `True`

- [ ] **Step 3: View the report**

Run: `Get-Content -LiteralPath "data\evaluation\embedding_model_comparison_report.txt"`

- [ ] **Step 4: Commit results**

```bash
git add data/evaluation/embedding_model_comparison_report.txt
git commit -m "results: add embedding model comparison report"
```

---

## Summary

After completing all tasks:

1. **jina-embeddings-v3** added to model registry
2. **Evaluation script** created at `scripts/evaluate_embedding_models.py`
3. **Comparison report** generated at `data/evaluation/embedding_model_comparison_report.txt`
4. **Best model** identified and recommended for use in the RAG system

The report contains:
- Per-model metrics (Recall@5, Precision@5, MRR, NDCG@5, p95 latency)
- Side-by-side comparison table
- Best model recommendation with reasoning
