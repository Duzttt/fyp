# RAGAS Evaluation Comparison Report

## Metric Averages

| Metric             | v1 (baseline) | v2 (after retrieval) | Difference (v2 - v1) |
|--------------------|---------------|----------------------|----------------------|
| **Faithfulness**       | 0.6070        | 0.6512               | +0.0442              |
| **Answer Relevancy**   | 0.8375        | 0.7977               | -0.0398              |
| **Context Precision**  | 0.5402        | 0.5336               | -0.0067              |
| **Context Recall**     | 0.5600        | 0.5800               | +0.0200              |
| **Overall Average**    | 0.6362        | 0.6406               | +0.0044              |

## Performance Classification (per skill guidelines)

| Metric           | v1 Classification | v2 Classification |
|------------------|-------------------|-------------------|
| Faithfulness     | Acceptable (0.6070) | Acceptable (0.6512) |
| Answer Relevancy | Acceptable (0.8375) | Acceptable (0.7977) |
| Context Precision| Acceptable (0.5402) | Acceptable (0.5336) |
| Context Recall   | **Poor (0.5600)**   | **Poor (0.5800)**   |

## Which Version Is Better?

- **Overall**: v2 slightly better (0.6406 vs 0.6362), but difference is marginal (0.0044).
- **Per metric**:
  - v2 better: Faithfulness (+0.0442), Context Recall (+0.0200)
  - v1 better: Answer Relevancy (-0.0398), Context Precision (-0.0067)
- No metric shows >0.1 change, indicating **no significant improvements or regressions**.

## Key Observations

1. **Context Recall is Poor in both versions** (~0.56-0.58), meaning the retrieval system misses many relevant passages.
2. **Context Precision is Acceptable** (~0.53-0.54), indicating retrieved chunks have moderate relevance.
3. **Faithfulness is Acceptable** (~0.61-0.65), suggesting some LLM hallucination.
4. **Answer Relevancy is Acceptable** (~0.80-0.84), but slightly lower in v2.
5. Both versions have **4 rows with empty retrieved_contexts** (no context retrieved), which drags down all metrics.

## Weak Metrics Requiring Optimization

Both versions share the same weaknesses:
- **Context Recall (Poor)** – retrieval fails to capture all relevant information.
- **Context Precision (Acceptable, borderline)** – retrieved chunks contain some noise.
- **Faithfulness (Acceptable, borderline)** – LLM occasionally hallucinates.

## Actionable Recommendations

### 1. Improve Context Recall (Top Priority)
- **Adjust chunking parameters**: Increase `CHUNK_SIZE` from default 400 to 500-700 and `CHUNK_OVERLAP` from 50 to 100-120 to preserve semantic units.
- **Enable hybrid retrieval**: Set `"use_hybrid_retrieval": true` in `rag_config.json` to combine BM25 keyword search with dense vector search.
- **Rebuild FAISS index** after any chunking change:
  ```bash
  python scripts/pdf_to_faiss_with_metadata.py --pdf media/data_source/<file>.pdf
  ```

### 2. Improve Context Precision
- **Reduce top_k** (currently 5) to 3-4 to give the LLM less noisy context.
- **Apply hybrid retrieval** as above to improve signal-to-noise ratio.

### 3. Improve Faithfulness
- **Use a more capable judge LLM** (Gemini, DeepSeek, GPT-4o) if not already.
- **Add source grounding prompts** in the generation step to reduce hallucination.
- **Verify RAGAS judge LLM configuration** in `.env` (RAGAS_API_KEY, RAGAS_BASE_URL, RAGAS_MODEL).

### 4. Address Empty Contexts
- Investigate why 4/25 queries return empty contexts. These are likely due to:
  - Embedding model mismatch with lecture language (ensure `all-MiniLM-L6-v2` for English).
  - Index not built for certain PDFs.
  - Query too specific or vague.

### 5. Monitor Answer Relevancy
- v2 shows slight drop; ensure question generation uses English prompts and `--language en` flag is set.

## Next Steps

1. Apply chunking and hybrid retrieval changes.
2. Rebuild index.
3. Re-run RAGAS evaluation.
4. Compare new results with current baselines.
5. Iterate until all metrics reach "Good" range (Faithfulness >0.80, Context Recall >0.80, Context Precision >0.70, Answer Relevancy >0.85).