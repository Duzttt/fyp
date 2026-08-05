# 检索策略升级实施计划

**Goal:** 修正 Hybrid 检索被 Dense 阈值削弱的问题，并建立可配置、可评测、支持技术课程文本的检索流水线。

**Architecture:** 以持久化 FAISS 作为唯一 Dense 候选来源；BM25 与 Dense 各取候选后使用 RRF 融合，Cross-Encoder 对融合候选重排序，最后以 MMR 和来源上限减少重复上下文。生产检索配置统一由 `config/retrieval_config.py` 驱动。

**Tech Stack:** Python、FAISS、rank-bm25、sentence-transformers、Cross-Encoder、pytest。

---

### Task 1: 统一配置与检索接口

**Files:**
- Modify: `config/retrieval_config.py`
- Modify: `app/services/local_rag.py`
- Test: `tests/test_local_rag.py`

- [ ] 扩展 `RetrievalConfig`，加入并设定默认值：

  ```python
  fusion_method = "rrf"
  bm25_top_k = 50
  dense_top_k = 50
  rerank_candidate_top_k = 30
  reranker_enabled = True
  reranker_score_threshold = None
  diversity_lambda = 0.7
  max_chunks_per_source = 2
  final_top_k = 5
  ```

- [ ] 保留 `retrieve_with_faiss()` 的现有调用兼容性；新增 `minimum_relevance_score: Optional[float] = None`。

- [ ] 停止将 `SIMILARITY_THRESHOLD=0.6` 作为 Hybrid 结果的 Dense cosine 阈值；仅当明确提供 `minimum_relevance_score` 时，才按最终 reranker 分数过滤。

- [ ] 更新所有 QA 调用点，不再传递默认 Dense 相似度阈值。

- [ ] 添加测试：默认 Hybrid 结果不会因 Dense 分数低于 `0.6` 被移除；显式设置最终分数阈值时才过滤。

- [ ] 提交：

  ```bash
  git add config/retrieval_config.py app/services/local_rag.py tests/test_local_rag.py
  git commit -m "fix: decouple hybrid acceptance from dense similarity"
  ```

### Task 2: 改进 BM25 技术英文分词

**Files:**
- Modify: `retrieval/bm25_index.py`
- Test: `tests/test_hybrid_retrieval.py`

- [ ] 以技术英文 tokenizer 替换仅 `[a-z0-9]+` 的默认规则。

- [ ] 对复合技术词同时索引原词及组成词。例如：

  ```text
  "C++, A*, OAuth2, foo_bar, deep-learning, Python 3.10"
  → c++, a*, oauth2, foo_bar, deep-learning, deep, learning, python, 3.10
  ```

- [ ] 保留 `not`、`no`、`nor` 等否定词；保留自定义 tokenizer 覆盖默认 tokenizer 的现有行为。

- [ ] 添加测试：`C++`、`C#`、`A*`、版本号、下划线标识符、连字符术语和否定查询均能被 BM25 正确匹配。

- [ ] 提交：

  ```bash
  git add retrieval/bm25_index.py tests/test_hybrid_retrieval.py
  git commit -m "feat: support technical terms in bm25 tokenization"
  ```

### Task 3: 使用持久化 FAISS 的 Hybrid 候选与重排序

**Files:**
- Modify: `retrieval/hybrid_retriever.py`
- Modify: `app/services/hybrid_retriever_service.py`
- Modify: `app/services/vector_store.py`
- Test: `tests/test_hybrid_retriever_service.py`

- [ ] 为 `HybridRetriever` 增加可选 `dense_search_provider(query, top_k)` 接口；未提供时保留当前内存 `DenseRetriever` 行为，保障独立测试和管理工具兼容。

- [ ] 在 `HybridRetrieverService` 中实现 provider：

  1. 用现有 `EmbeddingService` 编码 query。  
  2. 调用持久化 `VectorStore.search_with_metadata()`。  
  3. 使用 FAISS chunk index 映射为 `chunk_<index>` ID。  
  4. 返回 `(chunk_id, cosine_score)` 候选。

- [ ] 服务初始化时仅构建 BM25，不再对所有 chunk 重复 embedding 或创建第二个 FAISS index。

- [ ] 固定生产候选流程：

  ```text
  BM25 top 50 + FAISS top 50
  → RRF(k=60)
  → top 30
  → Cross-Encoder rerank
  → optional final-score threshold
  → diversity selection
  → top 5
  ```

- [ ] RRF 作为默认融合；保留 weighted fusion 供管理员实验，但不作为默认生产策略。

- [ ] 修正 `candidate_top_k` 语义：它只控制内部候选数量，公开 `retrieve(top_k=N)` 必须最多返回 `N` 条。

- [ ] 添加测试：服务不会实例化 `DenseRetriever`；FAISS 返回的 chunk ID 与 BM25 ID 可正确融合；BM25-only 命中能进入 rerank；`top_k` 和候选数量语义正确。

- [ ] 提交：

  ```bash
  git add retrieval/hybrid_retriever.py app/services/hybrid_retriever_service.py app/services/vector_store.py tests/test_hybrid_retriever_service.py
  git commit -m "refactor: use persisted faiss for hybrid candidates"
  ```

### Task 4: 重排序、去重与可观测性

**Files:**
- Modify: `app/services/local_rag.py`
- Modify: `app/services/cross_encoder_reranker.py`
- Test: `tests/test_local_rag.py`

- [ ] Cross-Encoder 默认启用，且只处理 RRF 融合后的前 30 条候选。

- [ ] 重排序输出必须保留：

  ```python
  {
      "text": str,
      "source": str,
      "page": Optional[int],
      "bm25_score": float,
      "dense_score": float,
      "fusion_score": float,
      "rerank_score": float,
  }
  ```

- [ ] 增加 MMR 多样性选择：使用持久化 FAISS 向量计算 chunk 间相似度，`diversity_lambda=0.7`。

- [ ] 限制最终上下文中同一 source 最多 2 个 chunk；无其他可用候选时允许放宽该限制以返回足够上下文。

- [ ] 记录 BM25、Dense、融合、rerank、MMR 各阶段耗时和候选数量，供现有 analytics/trace 页面展示。

- [ ] 添加测试：reranker 排名优先于 RRF 排名；同页/同来源重复 chunk 被限制；候选不足时系统安全返回较少结果而非失败。

- [ ] 提交：

  ```bash
  git add app/services/local_rag.py app/services/cross_encoder_reranker.py tests/test_local_rag.py
  git commit -m "feat: rerank and diversify hybrid retrieval results"
  ```

### Task 5: 建立检索基准与发布门槛

**Files:**
- Create: `data/evaluation/retrieval_benchmark.jsonl`
- Create: `scripts/evaluate_retrieval.py`
- Modify: `evaluation/retrieval_evaluator.py`
- Test: `tests/test_retrieval_evaluator.py`

- [ ] 定义 benchmark 记录格式：

  ```json
  {
    "id": "q001",
    "query": "What is the contract net protocol?",
    "relevant_chunk_ids": ["chunk_14", "chunk_15"],
    "ground_truth": "..."
  }
  ```

- [ ] 初始收集至少 30 个真实课程问题，覆盖定义题、关键词题、同义改写题、代码/符号题、否定题和跨页综合题。

- [ ] 评测脚本必须在同一数据集、同一 `top_k` 下分别运行 `bm25`、`dense`、`hybrid`，输出 Recall@5、Recall@10、MRR、nDCG@5、p95 latency 和每题结果。

- [ ] 将 reranker 阈值保持为 `None`，直到 benchmark 验证可确定稳定阈值；不得根据单次 RAGAS 分数设定阈值。

- [ ] 发布验收标准：

  ```text
  Hybrid Recall@5 ≥ Dense Recall@5
  Hybrid MRR ≥ Dense MRR
  Hybrid nDCG@5 ≥ Dense nDCG@5
  结果中无 BM25-only 精确命中被 dense 阈值错误删除
  rerank 后 p95 延迟符合部署环境允许值
  ```

- [ ] 提交：

  ```bash
  git add data/evaluation/retrieval_benchmark.jsonl scripts/evaluate_retrieval.py evaluation/retrieval_evaluator.py tests/test_retrieval_evaluator.py
  git commit -m "test: add benchmark for retrieval strategy comparison"
  ```

## Test Plan

- 运行针对性测试：

  ```bash
  pytest tests/test_hybrid_retrieval.py tests/test_hybrid_retriever_service.py tests/test_local_rag.py tests/test_retrieval_evaluator.py -v
  ```

- 运行完整回归：

  ```bash
  pytest tests/ --tb=short
  ```

- 在同一 benchmark 上比较三种模式，并保存结果作为上线前基线。

## Assumptions

- 第一阶段仅优化英文技术课程资料，不引入中文分词依赖。
- Cross-Encoder `cross-encoder/ms-marco-MiniLM-L6-v2` 默认启用，但保留配置开关。
- RRF 是默认生产融合方式；weighted fusion 仅用于实验。
- 不迁移或重建现有 PDF/FAISS 数据；升级后直接复用现有持久化向量索引。
