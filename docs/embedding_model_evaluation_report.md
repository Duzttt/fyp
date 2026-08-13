# Embedding Model Evaluation Report

## 1. Introduction

This report presents the evaluation results of 5 embedding models for the RAG-based Lecture Note Q&A System. The goal is to identify the best embedding model that balances retrieval quality and performance for our use case.

## 2. Models Evaluated

| # | Model | Dimension | Size | Description |
|---|-------|-----------|------|-------------|
| 1 | sentence-transformers/all-MiniLM-L6-v2 | 384 | ~80 MB | Original model (baseline) |
| 2 | BAAI/bge-m3 | 1024 | ~2.3 GB | Multilingual model with dense, sparse, and ColBERT retrieval |
| 3 | jinaai/jina-embeddings-v3 | 1024 | ~570 MB | Jina's latest multilingual embedding model |
| 4 | BAAI/bge-large-en-v1.5 | 1024 | ~1.2 GB | Large model with excellent retrieval accuracy |
| 5 | intfloat/e5-large-v2 | 1024 | ~1.3 GB | Microsoft E5 model for text embeddings |

## 3. Evaluation Setup

- **Benchmark Dataset:** retrieval_benchmark.jsonl (33 queries)
- **Evaluation Metrics:** Recall@k, Precision@k, MRR, NDCG@k, p95 Latency
- **Retrieval Method:** Dense retrieval with FAISS (IndexFlatIP + L2 normalization)
- **Top-k:** 5

## 4. Results

### 4.1 Per-Model Metrics

| Model | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | NDCG@5 | NDCG@10 | p95 Latency |
|-------|----------|----------|----------|-----------|-----|--------|---------|-------------|
| all-MiniLM-L6-v2 | 0.8535 | 0.9697 | 0.9848 | 0.9848 | 0.9697 | 0.9635 | 0.9635 | 10.99ms |
| bge-m3 | - | - | - | - | - | - | - | ERROR |
| jina-embeddings-v3 | 0.8687 | 0.9444 | 0.9848 | 0.9848 | 0.9773 | 0.9706 | 0.9706 | 49.10ms |
| bge-large-en-v1.5 | 0.8838 | 0.9596 | **1.0000** | **1.0000** | **1.0000** | 0.9837 | 0.9837 | 35.27ms |
| e5-large-v2 | 0.8838 | 0.9747 | **1.0000** | **1.0000** | **1.0000** | **0.9904** | **0.9904** | 28.83ms |

> Note: BAAI/bge-m3 failed to load due to torch version requirement (CVE-2025-32434 requires torch >= 2.6).

### 4.2 Key Findings

1. **Perfect Recall@5:** Both bge-large-en-v1.5 and e5-large-v2 achieved perfect Recall@5 (1.0), meaning they retrieved all relevant documents in the top 5 results.

2. **Best NDCG@5:** e5-large-v2 achieved the highest NDCG@5 (0.9904), indicating superior ranking quality.

3. **Fastest Model:** all-MiniLM-L6-v2 is the fastest (10.99ms p95 latency), but with slightly lower retrieval quality.

4. **jina-embeddings-v3:** Performance comparable to the original model, with slightly better MRR and NDCG@5.

## 5. Recommendation

### Recommended Model: intfloat/e5-large-v2

**理由：**

| Metric | e5-large-v2 | all-MiniLM-L6-v2 (原模型) | 提升 |
|--------|-------------|---------------------------|------|
| Recall@5 | 1.0000 | 0.9848 | +1.5% |
| MRR | 1.0000 | 0.9697 | +3.1% |
| NDCG@5 | 0.9904 | 0.9635 | +2.8% |
| p95 Latency | 28.83ms | 10.99ms | +162% |

**综合评估：**
- e5-large-v2 在检索质量上全面超越原模型
- 虽然延迟增加，但仍在可接受范围内（<30ms）
- 如果对延迟敏感，可以继续使用 all-MiniLM-L6-v2

## 6. Alternative Models

| 场景 | 推荐模型 | 理由 |
|------|----------|------|
| 追求最佳检索质量 | e5-large-v2 | NDCG@5最高，完美Recall@5 |
| 追求最快速度 | all-MiniLM-L6-v2 | 延迟最低（10.99ms） |
| 多语言需求 | jina-embeddings-v3 | 多语言支持，性能接近原模型 |
| 平衡性能与速度 | bge-large-en-v1.5 | 完美Recall@5，延迟适中 |

## 7. Conclusion

基于本次评估，推荐将 **intfloat/e5-large-v2** 作为主要的 embedding 模型。该模型在检索质量和排序准确性上均达到最优，适合对检索精度要求较高的 RAG 系统。

如需切换模型，可使用现有的 runtime embedding 系统进行切换。

---

**报告生成时间：** 2026-08-07 15:11  
**评估脚本：** scripts/evaluate_embedding_models.py  
**基准数据集：** data/evaluation/retrieval_benchmark.jsonl (33 queries)
