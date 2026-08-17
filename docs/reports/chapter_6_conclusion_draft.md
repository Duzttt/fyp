# Chapter 6 — Conclusion

> **状态：草稿（Draft）**
> Aligned to the UTeM PSM Report template structure (`Template PSM Report 2025 v2 -
> Product-based.docx`). Written in formal academic English. Data referenced are all
> drawn from the evaluation artifacts in this repository (no fabricated numbers).
> Items flagged `<!-- TODO -->` need confirmation before finalisation.

---

## 6.1 Introduction

This chapter concludes the project by summarising the work carried out across the
development of an AI-based lecture-note Question-Answering (Q&A) system using
Retrieval-Augmented Generation (RAG). It revisits the objectives established in
Chapter 1, reviews the extent to which they were achieved against the evaluation
evidence presented in Chapter 5, discusses the limitations of the implemented
system, and proposes directions for future work.

---

## 6.2 Fulfilment of Objectives

The system was designed to answer natural-language questions over lecture-note
PDFs by combining hybrid retrieval with large-language-model generation. Drawing
on the evaluation results in Chapter 5, the extent of objective fulfilment is
summarised below.

| Objective | Evidence | Status |
|-----------|----------|--------|
| Build a RAG pipeline over lecture-note PDFs (PDF ingestion → chunking → embedding → vector store → generation) | Functional end-to-end pipeline (Chapter 4); RAGAS end-to-end metrics (Chapter 5.3.4) | ✅ Achieved |
| Improve retrieval quality over a dense-only baseline | Hybrid retrieval (BM25 + dense + RRF) raised Recall@5 by ~13% and MRR by ~17% vs dense-only (Chapter 5.3.1) | ✅ Achieved |
| Support multiple LLM providers (Gemini / OpenRouter / local) | Unified `llm_client` with runtime provider switching (Chapter 4) | ✅ Achieved |
| Provide citation-aware answers grounded in sources | Citation-aware RAG pipeline; source snippets returned with answers | ✅ Achieved |
| Evaluate system quality quantitatively | Two-layer evaluation: retrieval metrics (Recall/MRR/NDCG) + RAGAS end-to-end (Faithfulness, Answer Relevancy, Context Precision/Recall) | ✅ Achieved |

<!-- TODO: Align the right-hand objective column with the exact objective list /
     numbering used in Chapter 1. -->

---

## 6.3 Conclusions Reached

1. **Retrieval quality governs overall answer quality.** The largest measurable
   gains in this project came from the retrieval side — hybrid RRF fusion and
   smart chunking — which is consistent with the general finding in RAG research
   that answer quality is bounded by retrieval quality.

2. **Small models are the cost-effective choice for lecture-note corpora.** In a
   corpus where documents are topically distinct, even a lightweight embedding
   model (`all-MiniLM-L6-v2`) achieved complete document recall (Recall@5 and MRR
   of 1.0 with the stronger models, and ~0.98 with the baseline). Pairing the
   baseline embedding with the `ms-marco-MiniLM-L6-v2` reranker delivered the
   highest MRR (0.9394) within an interactive latency budget (84 ms p95). Larger
   models (e.g. `bge-v2-m3`, `jina-reranker-v2`) offered only marginal retrieval
   gains at 8–150× the latency, and were therefore not adopted.

3. **Answer generation remains the weaker link.** RAGAS evaluation showed
   Faithfulness at ~0.65 and Context Recall at ~0.58, both in the Acceptable-to-Poor
   range. Answer Relevancy (~0.80) was healthier, but the moderate Faithfulness
   score indicates residual hallucination risk that should be addressed in future
   work.

4. **The system meets interactive latency targets.** Hybrid retrieval remained
   below 200 ms p95, satisfying the latency requirement for interactive Q&A.

---

## 6.4 Recommendations

Based on the findings in Chapter 5, the following recommendations are made:

1. **Retain `all-MiniLM-L6-v2` as the embedding model.** Given the corpus size and
   the empirical evidence that recall is already saturated, the cost of switching
   to a 1024-dimension model (full FAISS index rebuild and ~1.2 GB additional
   memory) is not justified. This keeps the system lightweight and fast.

2. **Deploy `cross-encoder/ms-marco-MiniLM-L6-v2` as the production reranker.**
   It offers the best quality-to-latency ratio and runs efficiently on CPU.

3. **Strengthen source-grounded prompting** to improve Faithfulness, and expand
   the evaluation benchmark beyond the current query counts to increase
   statistical confidence in the results.

---

## 6.5 Limitations

The following limitations were identified during the project:

1. **Small evaluation benchmark.** The retrieval benchmark uses 33 queries and the
   RAGAS end-to-end benchmark 25 QA pairs. While adequate for comparing components
   internally, the scale limits the statistical generalisability of the results.

2. **Context Recall is the weakest metric.** The Poor rating for Context Recall
   indicates that relevant passages are sometimes missed, which in turn caps the
   ceiling on answer faithfulness.

3. **Judge-LLM dependence.** End-to-end metrics depend on the quality of the judge
   LLM; a weaker local judge can under-state or bias the reported scores.

4. **Hardware constraint.** GPU-accelerated reranking was counterproductive on the
   evaluation hardware (GTX 1650, 4 GB VRAM) owing to transfer overhead, so
   conclusions about GPU scaling are limited.

<!-- TODO: Extend with any additional limitations your supervisor wants to see. -->

---

## 6.6 Future Work

Several directions can build on this work:

1. **Larger and more diverse evaluation data.** Expand the ground-truth query set
   to 100+ queries spanning more lecture modules to improve statistical confidence
   in both retrieval and RAGAS metrics.

2. **Improve Context Recall.** Apply query expansion, multi-stage retrieval
   (candidate generation followed by re-ranking), and tuned chunking parameters to
   reduce missed relevant passages.

3. **Reduce hallucination.** Strengthen source-grounding prompts, add post-hoc
   faithfulness checks, and evaluate stronger generation/judge models to push
   Faithfulness into the Good range.

4. **Multi-document and multi-turn reasoning.** Extend the system to support
   cross-document synthesis and conversational follow-ups, which are natural
   extensions for lecture-note study support.

5. **Adaptive model selection.** Investigate learned/adaptive fusion and query
   routing so that simple queries use lightweight retrieval while complex queries
   invoke deeper reasoning, optimising the latency–quality trade-off.

6. **GPU-optimised deployment.** Re-evaluate large rerankers on hardware with
   ≥8 GB VRAM and Ampere-or-later compute capability, where GPU acceleration
   becomes beneficial.

---

## 6.7 Summary

This chapter restated the project objectives and confirmed their achievement
against the quantitative evidence in Chapter 5. The system fulfils its core remit:
an AI-based lecture-note Q&A system that retrieves relevant passages accurately and
answers questions within interactive latency, with retrieval quality as its
strongest aspect and answer faithfulness its clearest area for improvement. The
limitations identified and the future-work proposals set a concrete agenda for
follow-up research.

<!-- TODO: Optional closing paragraph thanking the supervisor / acknowledging scope,
     matching your supervisor's expectations. -->
