# Chapter 5 — System Evaluation

> **状态：草稿（Draft）**
> 说明：本章为 FYP2 论文评测章的草稿。所有数据均来自仓库内已落盘的评估产物
> （`evaluation/` 下的 RAGAS CSV、`docs/EVALUATION_REPORT.md`、
> `docs/embedding_model_evaluation_report.md`、`evaluation/reranker_evaluation_report.md`）。
> 写作前请补齐以下【待办】标记处，并与 Chapter 3 的功能/非功能需求逐条对应验收结果。

---

## 5.1 Introduction

本章对系统进行系统性评测，回答三个核心问题：

1. **检索质量**（`retrieval`）：混合检索（BM25 + 稠密向量 + RRF 融合）与智能分块
   相比基线稠密检索，在 Recall、MRR、NDCG 上是否带来可测量的提升。
2. **答案生成质量**（`generation`）：端到端 RAG 输出在 Faithfulness、
   Answer Relevancy、Context Precision、Context Recall 上的表现。
3. **质量 - 成本权衡**（`trade-off`）：embedding 模型与 reranker 的选择如何在
   检索精度与延迟 / 资源占用之间取得平衡。

评测采用三层递进结构：先孤立评估检索组件（分块策略、融合方法、embedding 模型、
reranker），再做端到端 RAGAS 评测，最后给出面向学lecture-note 场景的生产配置建议。

---

## 5.2 Evaluation Methodology

### 5.2.1 评测框架与指标

本章采用两类互补的评测手段：

1. **检索指标（离线、带 ground-truth）**
   - **Recall@k**：相关文档在前 k 个结果中被召回的比例
   - **Precision@k**：前 k 个结果中相关文档的比例
   - **MRR**（Mean Reciprocal Rank）：首个相关结果排名的倒数均值
   - **NDCG@k**（Normalized Discounted Cumulative Gain）：考虑位置权重的排序质量

2. **端到端 RAG 指标（RAGAS 框架）**

| 指标 | 含义 | Good 阈值 |
|------|------|-----------|
| Faithfulness | 答案是否忠于检索上下文（无幻觉） | > 0.80 |
| Answer Relevancy | 答案是否切题 | > 0.85 |
| Context Precision | 检索块的相关性 | > 0.70 |
| Context Recall | 相关信息的召回覆盖 | > 0.80 |

> 阈值取自项目 `evaluation/ragas/classify_metrics.py` 中的分级标准，
> 用于将每项指标划分为 Good / Acceptable / Poor 三档。

### 5.2.2 评测数据集

- **检索基准**：33 条带 ground-truth 文档标注的查询，语料来自
  AI Agents / Multi-Agent Systems 系列 lecture notes；
- **RAGAS 端到端基准**：25 条 PDF 自动生成的 QA 对（`eval_baseline.jsonl`）；
- **分块 / 融合评测**：12 份中文机器学习讲义，8 条已知相关文档的查询。

<!-- 【待办】确认最终论文采用的语料规模与来源，与 Chapter 3 需求表中的数据源一致。 -->

### 5.2.3 评测环境与 Judge LLM

- RAGAS 的 judge LLM 默认走 **OpenRouter + deepseek/deepseek-v4-flash**
  （配置见 `ragas_evaluator.py` 的 `_resolve_ragas_llm_config`）；
- DeepEval 通道复用项目统一的 `app/services/llm_client.call_llm` 作为 judge，
  支持 gemini / openrouter / local_llm 三种 provider；
- 全部评估本地运行，不依赖第三方评测平台。

---

## 5.3 Evaluation Results

### 5.3.1 混合检索与智能分块（Retrieval Optimization）

#### 5.3.1.1 混合检索 vs 基线

下表为 Phase 1 优化的核心结果（来源：`docs/EVALUATION_REPORT.md`）：

| Metric | Baseline（仅稠密） | 优化后（Hybrid RRF） | 提升 |
|--------|-------------------|----------------------|------|
| Recall@5 | ~65% | ~78% | +13% |
| Recall@10 | ~75% | ~85% | +10% |
| MRR | ~0.70 | ~0.82 | +17% |
| NDCG@5 | ~0.68 | ~0.79 | +16% |

**逐检索器对比**（12 份中文讲义、8 查询）：

| Retriever | Recall@1 | Recall@5 | Recall@10 | MRR | NDCG@5 |
|-----------|----------|----------|-----------|-----|--------|
| BM25 | 0.625 | 0.792 | 0.833 | 0.721 | 0.712 |
| Dense | 0.688 | 0.813 | 0.854 | 0.758 | 0.745 |
| **Hybrid (RRF)** | **0.750** | **0.875** | **0.917** | **0.829** | **0.798** |
| Hybrid (Weighted) | 0.729 | 0.854 | 0.896 | 0.808 | 0.781 |

**发现**：RRF 融合在所有检索指标上均优于单一路径；相比加权融合也更稳健
（无需分数归一化、超参数更少）。这验证了 keyword + semantic 双路互补的假设。

#### 5.3.1.2 分块策略对比

| Chunking | Recall@5 | Precision@5 | NDCG@5 |
|----------|----------|-------------|---------|
| Fixed（基线） | 0.813 | 0.725 | 0.745 |
| Smart | **0.875** | **0.788** | **0.798** |

- 智能分块带来 **+6.2% Recall@5**；
- 最优 overlap 为 100 字符（Recall@5 = 0.875），在召回与存储开销间取得平衡。

#### 5.3.1.3 延迟分析

| Retriever | Avg (ms) | P95 (ms) |
|-----------|----------|----------|
| BM25 | 12.5 | 18.3 |
| Dense | 145.8 | 178.2 |
| Hybrid (RRF) | 162.3 | 195.4 |

混合检索增加约 15–20ms 融合开销，但 P95 仍 <200ms，满足交互式问答的延迟预算。

---

### 5.3.2 Embedding 模型对比

来源：`docs/embedding_model_evaluation_report.md`（33 查询、5 模型）。

| Model | Recall@5 | MRR | NDCG@5 | p95 Latency |
|-------|----------|-----|--------|-------------|
| all-MiniLM-L6-v2（基线） | 0.9848 | 0.9697 | 0.9635 | 10.99 ms |
| jina-embeddings-v3 | 0.9848 | 0.9773 | 0.9706 | 49.10 ms |
| bge-large-en-v1.5 | **1.0000** | **1.0000** | 0.9837 | 35.27 ms |
| e5-large-v2 | **1.0000** | **1.0000** | **0.9904** | 28.83 ms |

> bge-m3 因 torch 版本约束（需 ≥2.6）未能加载，不计入结果。

**发现**：
- e5-large-v2 与 bge-large-en-v1.5 均达到 Recall@5 / MRR = 1.0；
- e5-large-v2 的 NDCG@5 最高（0.9904），排序质量最优；
- 但换用 1024 维模型需全量重建 FAISS 索引，内存升至约 1.2GB。

> **最终决策：维持 `all-MiniLM-L6-v2` 作为生产 embedding 模型。**
> 依据 2026-08-14 的复测（`docs/reports/2026-08-14-studio-summary-bugs-and-embedding-reeval.md`），
> 在当前语料（20 份 PDF、414 chunks、主题区分度高）下，即使最弱的 MiniLM-L6
> 也能达到 Recall@10 = 100%。换用 e5-large-v2 仅能进一步改善 MRR（0.81 → 0.92，
> 即正确 chunk 排名更靠前），属渐进式改进而非质变，却需全量重建索引并将内存
> 推至 ~1.2GB。鉴于语料规模小、召回已饱和，本系统选择维持 MiniLM-L6 以换取
> 轻量、快速的部署；仅在出现"明显召回不足"或"小 top_k 召错"的场景才考虑
> 换用 e5-large-v2。此决策与生产配置及 Chapter 6 的推荐保持一致。

---

### 5.3.3 Reranker 模型对比

来源：`evaluation/reranker_evaluation_report.md`（33 查询、5 模型，30 候选重排）。

| Model | MRR | Recall@5 | NDCG@5 | P95 (ms) | Params |
|-------|-----|----------|--------|----------|--------|
| **ms-marco-MiniLM-L6-v2** | **0.9394** | 0.9293 | **0.9184** | **84** | 22.7M |
| bge-reranker-base | 0.9192 | 0.9444 | 0.9125 | 634 | 278M |
| bge-reranker-v2-m3 | 0.9242 | 0.9444 | 0.9134 | 12,625 | 568M |
| jina-reranker-v2 | 0.9192 | 0.9293 | 0.9057 | 43,246 | 278M |
| *Baseline（无 reranker）* | 0.9091 | 0.8081 | — | — | — |

**发现**：
- 所有 reranker 均提升 MRR（最高 +0.030）；
- ms-marco-MiniLM-L6-v2 以最小的模型（22.7M）取得最高 MRR 与最快推理，
  是交互式 Q&A 场景唯一满足 <200ms P95 延迟预算的选择；
- 更大模型带来边际 Recall@5 提升（+1.5%），但延迟增加 8–150 倍，不具性价比；
- 在 GTX 1650（4GB）上 GPU 推理反而更慢（数据传输开销主导），结论是 CPU 部署更优。

---

### 5.3.4 端到端 RAG 生成质量（RAGAS）

来源：`evaluation/ragas/ragas_analysis_report.md`（baseline vs after-retrieval 两版对比）。

| Metric | v1（baseline） | v2（after retrieval） | Δ (v2 − v1) |
|--------|----------------|----------------------|-------------|
| Faithfulness | 0.6070 | 0.6512 | +0.0442 |
| Answer Relevancy | 0.8375 | 0.7977 | −0.0398 |
| Context Precision | 0.5402 | 0.5336 | −0.0067 |
| Context Recall | 0.5600 | 0.5800 | +0.0200 |

**分级**（依据 5.2.1 阈值）：

| Metric | v1 | v2 |
|--------|----|----|
| Faithfulness | Acceptable | Acceptable |
| Answer Relevancy | Acceptable | Acceptable |
| Context Precision | Acceptable | Acceptable |
| Context Recall | **Poor** | **Poor** |

**发现与讨论**：
1. **Context Recall 在两端均为 Poor**（0.56–0.58），是当前最弱项，说明检索仍有
   遗漏相关片段的空间；
2. Faithfulness 整体偏低（0.61–0.65），提示存在一定程度的幻觉，需更强的
   grounding prompt 或更高质量 judge；
3. v2 相对 v1 仅在 Faithfulness 与 Context Recall 上有小幅正向变化
   （均 <0.05），未出现 >0.1 的显著提升或退化；
4. 报告识别出 4/25 条查询存在空 `retrieved_contexts`，拖累了全部指标。

<!-- 【待办】论文需明确 v1/v2 所代表的"检索改进"具体是什么（hybrid retrieval /
     smart chunker 开闭？），并补一句为什么 Answer Relevancy 反而微降。
     若后续有 reranker 加入后的 RAGAS 重跑，应在此追加终版对比，作为
     "完整优化栈"的最终成绩。 -->

---

## 5.4 Acceptance Criteria Verification

将评测结果回溯到 Chapter 3 的功能/非功能需求验收（示例格式，请按实际需求 ID 对齐）：

| 需求类别 | 验收标准 | 实测结果 | 状态 |
|----------|----------|----------|------|
| 检索召回 | Recall@5 提升 >10% | +13% | ✅ |
| 检索排序 | MRR > 0.80 | 0.82 | ✅ |
| 交互延迟 | P95 < 200ms | 195ms（hybrid）/ 84ms（reranked） | ✅ |
| 生成忠实度 | Faithfulness 无幻觉 | 0.65（Acceptable，仍有提升空间） | ⚠️ |
| 代码质量 | 测试 + 类型标注 | 见 Chapter 4 | ✅ |

<!-- 【待办】用 Chapter 3 的真实需求 ID（如 FR-x / NFR-x）替换上表示例，
     并补齐所有关键需求。这是 FYP 验收表的核心，务必逐条核对。 -->

---

## 5.5 Discussion and Trade-offs

1. **检索优先于生成**：本系统最大的可量化收益来自检索侧（hybrid + chunking +
   reranker），而生成侧的 Faithfulness/Context Recall 仍是瓶颈；这符合 RAG
   系统"检索质量决定生成上限"的一般结论。
2. **小模型性价比原则**：在语料规模小、主题区分度高的 lecture-note 场景，
   MiniLM-L6（embedding）+ ms-marco-MiniLM-L6（reranker）的组合在精度与延迟间
   取得最佳平衡；换用 e5-large / bge-v2-m3 等大模型的边际收益有限，成本显著。
3. **局限性**：
   - 检索基准（33 查询）与 RAGAS 基准（25 查询）规模偏小，统计效力有限；
   - Context Recall 的 Poor 与 Faithfulness 的 Acceptable 提示仍有可优化空间；
   - 部分结果受本地 judge LLM 能力影响（小模型 judge 对评估质量有下偏风险）。

---

## 5.6 Summary

本章从检索、生成两个层面，对系统进行了分层评测：

- **检索层**：hybrid RRF + smart chunking 带来 Recall@5 +13%、MRR +17% 的显著
  提升；reranker 进一步将 MRR 提升至 0.94 并保持在 84ms P95 延迟内。
- **生成层**：RAGAS 端到端评测显示 Faithfulness（0.65）与 Context Recall（0.58）
  仍是主要短板，Answer Relevancy（0.80）相对健康。
- **权衡**：小模型（MiniLM 系列）在本场景以极低延迟换取接近饱和的召回，是
  投产的合理选择。

综合来看，系统在检索质量与延迟上达标，生成质量仍有改进空间，为 Chapter 6 的
结论与未来工作提供了直接依据。

---

## 附录：数据资产索引（供转 DOCX 时引用原始证据）

| 资产 | 路径 |
|------|------|
| 检索优化报告 | `docs/EVALUATION_REPORT.md` |
| Embedding 模型报告 | `docs/embedding_model_evaluation_report.md` |
| Reranker 报告 | `evaluation/reranker_evaluation_report.md` |
| RAGAS 分析报告 | `evaluation/ragas/ragas_analysis_report.md` |
| RAGAS 最新 CSV | `evaluation/ragas/results/ragas_v2_eval_20260806_191716.csv` |
| 检索重现脚本 | `scripts/evaluate_retrieval.py`、`scripts/evaluate_rerankers.py`、`scripts/evaluate_embedding_models.py` |
