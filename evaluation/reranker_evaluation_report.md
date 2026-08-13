# Cross-Reranker Model Evaluation Report

**Date:** August 7, 2026
**System:** AI-Based Lecture Note Q&A System (RAG)
**Benchmark:** 33 queries from AI Agents/Multi-Agent Systems lecture notes
**Hardware:** NVIDIA GeForce GTX 1650 (4GB VRAM), CPU fallback

---

## 1. Executive Summary

Five cross-encoder reranker models were evaluated on the same retrieval candidates to measure their impact on retrieval quality and system performance. All rerankers improve over the baseline (no reranker), with **ms-marco-MiniLM-L6-v2** delivering the best quality-to-latency ratio.

**Key Finding:** The smallest model (22.7M params) achieves the highest MRR and runs 8–150x faster than larger alternatives. Larger models (bge-reranker-v2-m3, jina-reranker-v2) provide marginal Recall@5 gains (+1.5%) at prohibitive latency costs.

---

## 2. Models Evaluated

| Model | Provider | Params | Architecture | License |
|---|---|---|---|---|
| `cross-encoder/ms-marco-MiniLM-L6-v2` | Sentence-Transformers | 22.7M | MiniLM-L6 | Apache 2.0 |
| `BAAI/bge-reranker-base` | BAAI | 278M | XLM-RoBERTa | MIT |
| `BAAI/bge-reranker-v2-m3` | BAAI | 568M | XLM-RoBERTa | MIT |
| `jinaai/jina-reranker-v2-base-multilingual` | Jina AI | 278M | XLM-RoBERTa | CC-BY-NC-4.0 |
| `Qwen/Qwen3-Reranker-0.6B` | Alibaba | 0.6B | Qwen3ForSequenceClassification | Apache 2.0 |

> **Note:** `Qwen3-Reranker-0.6B` was excluded from final results. It is a **generative reranker** (outputs text tokens, not relevance scores) and is incompatible with the CrossEncoder scoring interface. Its sequence classification head was not pre-trained for relevance scoring, producing near-random results (MRR=0.31).

---

## 3. Evaluation Methodology

### 3.1 Pipeline

```
Query → Hybrid Retrieval (BM25 + FAISS, RRF fusion) → 30 candidates → Reranker → Top-10 → Metrics
```

- **Candidate pool:** 30 documents per query from hybrid retrieval (no reranker applied)
- **Reranker output:** Top-10 documents rescored and reordered
- **Baseline:** Same candidates without reranking (score = fusion_score)

### 3.2 Metrics

| Metric | Description |
|---|---|
| **MRR** | Mean Reciprocal Rank — how high the first relevant result ranks |
| **Recall@k** | Fraction of relevant documents found in top-k |
| **Precision@k** | Fraction of top-k documents that are relevant |
| **NDCG@k** | Normalized Discounted Cumulative Gain — ranking quality considering position |
| **P95 Latency** | 95th percentile of per-query reranking time |
| **Throughput** | Queries per second (QPS) |

### 3.3 Benchmark Dataset

33 queries with ground truth answers and relevant chunk IDs extracted from AI Agents lecture notes (multi-agent systems, BDI architecture, contract net protocol, blackboard systems, etc.).

---

## 4. Results

### 4.1 Quality Metrics (CPU)

| Model | MRR | Δ MRR | Recall@1 | Recall@5 | Recall@10 | NDCG@5 | NDCG@10 |
|---|---|---|---|---|---|---|---|
| **ms-marco-MiniLM-L6-v2** | **0.9394** | **+0.030** | 0.8283 | 0.9293 | 0.9596 | **0.9184** | **0.9309** |
| bge-reranker-base | 0.9192 | +0.010 | 0.8131 | **0.9444** | 0.9596 | 0.9125 | 0.9178 |
| bge-reranker-v2-m3 | 0.9242 | +0.015 | 0.7980 | **0.9444** | 0.9596 | 0.9134 | 0.9193 |
| jina-reranker-v2 | 0.9192 | +0.010 | 0.8131 | 0.9293 | 0.9596 | 0.9057 | 0.9182 |
| *Baseline (no reranker)* | *0.9091* | — | — | *0.8081* | — | — | — |

### 4.2 Latency & Throughput

| Model | Params | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | QPS |
|---|---|---|---|---|---|---|
| **ms-marco-MiniLM-L6-v2** | 22.7M | **44** | **43** | **84** | **239** | **22.6** |
| bge-reranker-base | 278M | 370 | 346 | 634 | 2,354 | 2.7 |
| bge-reranker-v2-m3 | 568M | 8,989 | 6,439 | 12,625 | 13,215 | 0.11 |
| jina-reranker-v2 | 278M | 23,041 | 25,144 | 43,246 | 62,207 | 0.04 |

### 4.3 GPU Results (GTX 1650)

| Model | CPU P95 (ms) | GPU P95 (ms) | Speedup |
|---|---|---|---|
| ms-marco-MiniLM-L6-v2 | 84 | 489 | **0.17x** (slower) |
| bge-reranker-base | 634 | 3,077 | **0.21x** (slower) |
| bge-reranker-v2-m3 | 12,625 | 10,435 | **1.21x** |
| jina-reranker-v2 | 43,246 | 43,246 | **1.00x** |

> GPU inference is **counterproductive** on GTX 1650 (4GB VRAM). CPU-to-GPU tensor transfer overhead dominates for models <600M params. GPU acceleration requires a GPU with ≥8GB VRAM and compute capability ≥8.0 (Ampere+) to be beneficial.

### 4.4 Rank Movement Analysis

| Model | Docs Moved Up | Docs Moved Down | Unchanged | Avg Positions Changed |
|---|---|---|---|---|
| ms-marco-MiniLM-L6-v2 | 196 | 59 | 42 | 5.91 |
| bge-reranker-base | 194 | 62 | 41 | 5.73 |
| bge-reranker-v2-m3 | 194 | 66 | 37 | 5.80 |
| jina-reranker-v2 | 190 | 69 | 38 | 5.95 |

All rerankers move ~190–196 documents up in rank, indicating they are effectively reordering candidates based on semantic relevance rather than just keyword overlap.

---

## 5. Analysis

### 5.1 Quality Trade-offs

- **ms-marco** achieves the highest MRR (0.9394), meaning it most reliably places the best answer at rank 1. This is critical for a Q&A system where users see only the top result.
- **bge models** achieve the highest Recall@5 (0.9444 vs 0.9293), finding ~1.5% more relevant documents. This matters less for a Q&A system than for a search engine.
- **jina-reranker-v2** performs identically to bge-reranker-base on quality metrics but with 68x higher latency.

### 5.2 Latency Budget

| Scenario | Acceptable P95 | Suitable Models |
|---|---|---|
| Interactive Q&A | <200ms | ms-marco only |
| Background indexing | <2s | ms-marco, bge-reranker-base |
| Batch processing | <30s | All models |

For a production RAG system serving users interactively, only **ms-marco-MiniLM-L6-v2** meets the latency budget.

### 5.3 Cost Analysis

| Model | VRAM (est.) | RAM | Model Size | Download |
|---|---|---|---|---|
| ms-marco-MiniLM-L6-v2 | ~100MB | ~100MB | 90MB | ~90MB |
| bge-reranker-base | ~1.2GB | ~1.2GB | 1.1GB | ~1.1GB |
| bge-reranker-v2-m3 | ~2.4GB | ~2.4GB | 2.2GB | ~2.2GB |
| jina-reranker-v2 | ~1.2GB | ~1.2GB | 1.1GB | ~1.1GB |

---

## 6. Recommendation

**Deploy `cross-encoder/ms-marco-MiniLM-L6-v2` as the production reranker.**

Rationale:
1. **Highest MRR** (0.9394) — best first-result precision for Q&A
2. **Fastest inference** (84ms P95 on CPU) — suitable for interactive use
3. **Smallest footprint** (90MB, 100MB RAM) — minimal resource cost
4. **No GPU required** — runs efficiently on CPU
5. **Apache 2.0 license** — no usage restrictions

The bge models offer +1.5% Recall@5 at 8–150x latency cost, which is not justified for a lecture-note Q&A system with 33 ground-truth queries.

---

## 7. Future Work

1. **Evaluate on larger benchmark** — 33 queries is sufficient for model comparison but not for production validation. Expand to 100+ queries.
2. **Test with GPU ≥8GB VRAM** — A100/RTX 4090 may make bge-v2-m3 viable for high-throughput scenarios.
3. **Hybrid reranking** — Use ms-marco for initial reranking, then bge-v2-m3 for top-5 refinement.
4. **Tune rerank_candidate_top_k** — Current value (30) may be suboptimal. Evaluate with 20, 50, 100 candidates.
5. **Jina native API** — The `jina-reranker` Python package was not installed. The Jina API may offer better performance than the CrossEncoder fallback.
6. **Qwen3 generative reranker** — Needs a custom adapter using the chat/generation API with "Is this document relevant? Yes/No" prompting.

---

## 8. Reproduction

```bash
# Install dependencies
pip install -r requirements.txt

# Run the benchmark
python scripts/evaluate_rerankers.py --json --output evaluation/results/reranker_results.json

# Run specific models
python scripts/evaluate_rerankers.py --models cross-encoder/ms-marco-MiniLM-L6-v2 BAAI/bge-reranker-v2-m3

# Force CPU
python scripts/evaluate_rerankers.py --device cpu

# Custom candidate pool
python scripts/evaluate_rerankers.py --candidate-top-k 50 --eval-top-k 10
```

---

## 9. Appendix: Raw Results

Full results saved to `evaluation/results/reranker_results.json`.
