# Task 2 Report: Embedding Model Evaluation Script

## What I Implemented

Created `scripts/evaluate_embedding_models.py` - a standalone script that evaluates 4 embedding models against the retrieval benchmark.

### Features:
1. **Model Loading**: Loads 4 embedding models via SentenceTransformer:
   - BAAI/bge-m3
   - jinaai/jina-embeddings-v3
   - BAAI/bge-large-en-v1.5
   - intfloat/e5-large-v2

2. **Document Loading**: Loads document chunks from `data/faiss_index/chunks.npy`

3. **FAISS Index Building**: Creates a FAISS index with document embeddings for each model

4. **Benchmark Evaluation**: Runs retrieval for all 33 queries from `data/evaluation/retrieval_benchmark.jsonl`

5. **Metrics Computation**: Uses existing `RetrievalEvaluator` to compute:
   - Recall@1, Recall@3, Recall@5, Recall@10
   - Precision@1, Precision@3, Precision@5, Precision@10
   - MRR (Mean Reciprocal Rank)
   - NDCG@5, NDCG@10
   - p95 latency

6. **Report Generation**: Generates a comprehensive report including:
   - Per-model metrics
   - Side-by-side comparison table
   - Best model recommendation

## What I Tested

1. **Syntax Verification**: Ran `python -m py_compile scripts/evaluate_embedding_models.py` - passed successfully
2. **Code Review**: Verified the script follows project conventions and uses existing APIs correctly

## Files Changed

- **Created**: `scripts/evaluate_embedding_models.py` (new file, ~350 lines)

## Issues/Concerns

1. **Chunk Metadata**: The benchmark references chunk IDs like "chunk_140", which correspond to indices in the `chunks.npy` file. The script correctly maps these to document IDs.

2. **Model Loading**: Each model requires downloading from HuggingFace, which may take time on first run. The script includes progress indicators.

3. **Dependencies**: The script requires:
   - `sentence-transformers` (already in project)
   - `faiss-cpu` (already in project)
   - `numpy` (already in project)

4. **Performance**: Building FAISS index for each model may be memory-intensive. Consider running models sequentially if memory is limited.

## Report File Path

`C:\Users\wongs\Documents\GitHub\AI-Based-Lecture-Note-Question-Answering-System-Using-Retrieval-Augmented-Generation-RAG-\docs\superpowers\reports\task-2-report.md`
