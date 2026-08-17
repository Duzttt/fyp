# Studio Panel Summary 模块排查与修复报告

**日期：** 2026-08-14
**范围：** Studio Panel「Summarize PDF」摘要链路（主题发现 → 检索 → 摘要 → 页码引用），以及 embedding 模型并发加载 + 检索质量复测

---

## 1. 背景

用户提供了一份 PDF（L4.2 - Means-Ends Reasoning (1).pdf）及系统生成的 Markdown 摘要，要求排查摘要准确性。核对后定位到两类问题：

1. 页码引用错位——某句内容被标错页码（如 "goal as a set of formulae" 错标 p.14，实为 p.6）。
2. 虚构主题——摘要中出现文档不存在的 "SUMMARY and Conclusion" 主题，以及多个主题被误判为 "no matching content"。

## 2. 根因分析

### 2.1 页码错位（Bug A）

- 数据基础：PDF 共 14 页，chunk 的 page 字段按物理页 1:1 正确存储（pdf_chunking.py 中 enumerate(..., start=1)）。
- 真正根因：summarize_topic 把检索返回的 chunks 直接按混合检索 + MMR 的排名顺序编号后交给 LLM，而 parse_topic_summary_json 依赖 LLM 返回的 evidence_chunk 序号反推页码。
- 实测证据（查询 "blocksworld planning"，top_k=6）：

  ```
  修复前 RAW 顺序:   [5, 8, 14, 6, 7, 2]   <- 排名顺序，非文档顺序
  修复后 SORTED 顺序: [2, 5, 6, 7, 8, 14]   <- 文档页码顺序
  ```

  乱序时 LLM 看到的 [1]=第5页、[3]=第14页，填的 evidence_chunk 序号自然指错 chunk，导致页码错位。

### 2.2 虚构主题（Bug B）

- 根因：propose_topics 完全由 LLM 从抽样 chunk 自由发挥生成主题，无"主题必须来自文档真实标题"约束；且 importance 字段被收集却从未用于排序/截断。
- 另：summarize_topic 检索返回空时直接记入 skipped_topics，导致 "Learning Outcomes"、"Representation" 等真实章节被判"无匹配内容"。

## 3. 修复内容

### 3.1 app/services/topic_summarizer.py

| # | 修复 | 说明 |
|---|------|------|
| 1 | 检索结果按 page 排序 | summarize_topic 新增 _page_key()，对检索 chunk 按页码排序后再编号，evidence_chunk 变为稳定文档顺序引用 |
| 2 | evidence 严格校验 | parse_topic_summary_json 对非 int/bool 或越界的 evidence_chunk 返回空页码（不再静默错位），新增 _chunk_pages() |
| 3 | 主题真实性约束 | _build_topic_proposal_messages 的 system/user prompt 强化：主题标题必须是文档真实标题 verbatim，禁止合并/发明 |
| 4 | importance 排序 + 去重 + 截断 | propose_topics 按 importance 降序、标题去重、截断到 topic_count |
| 5 | 检索空命中降级 | summarize_topic 空结果时用主题标题 verbatim + 翻倍 top_k 重试一次 |

### 3.2 app/services/embedding.py（额外发现）

重跑验证时崩溃于 Cannot copy out of meta tensor。根因：_get_model() 无锁，run_pipeline 并发跑多个 topic 时多线程同时 SentenceTransformer(...) 触发 torch meta-device race。

- 修复：新增进程级 _MODEL_LOAD_LOCK（双重检查锁），序列化模型构造。

### 3.3 测试

tests/test_topic_summarizer.py：
- 更新 test_skipped_topic_on_empty_retrieval（修正 mock 大小写问题）
- 新增 test_heading_fallback_recovers_missed_topic

## 4. 验证结果

### 4.1 单元测试

```
pytest tests/test_topic_summarizer.py tests/test_runtime_embedding.py  -> 34 passed
ruff check  -> All checks passed
```

### 4.2 端到端重跑（同一 PDF）

用真实 PDF + 本地 llama.cpp LLM + 现有 FAISS 索引完整重跑 summary pipeline：

- skipped_topics 从旧的 [Learning Outcomes, Representation, SUMMARY and Conclusion] -> 空数组（无虚构主题、无误判 skipped）。
- 页码引用全部对齐真实页码：robot arm/blocks->p.5、ontology/closed world->p.6、action lists->p.7、STRIPS->p.4、deliberation 分解->p.12、options/filter->p.13、belief revision->p.10。
- 旧摘要错标 "Goal is represented as a set of formulae -> p.14"，现对应第 14 页 SUMMARY 的真句 "goal, state, action and plan can be represented using logic [p.14]"——已正确。

## 5. Embedding 模型检索质量复测

在修复之外，用户询问「换 embedding 模型会好一点吗」。做了纯 dense 检索对比（隔离 BM25/hybrid/reranker，只看 embedding 本身），15 个带 ground-truth 文档的查询，语料 20 个 PDF / 414 chunks：

| 模型 | 维度 | Recall@10 | MRR |
|------|------|-----------|-----|
| all-MiniLM-L6-v2（当前） | 384 | 1.000 | 0.8067 |
| BAAI/bge-large-en-v1.5 | 1024 | 1.000 | 0.8689 |
| intfloat/e5-large-v2 | 1024 | 1.000 | 0.9167 |

### 结论

- 三模型 Recall@10 全部 100%——当前语料（20 PDF、主题区分度高）下，连最弱的 MiniLM-L6 都能召回到正确文档。
- 换模型仅能改善 MRR（正确 chunk 排名更靠前）：MiniLM 0.81 -> bge-large 0.87 -> e5-large 0.92，属渐进改善，非质变。
- 换 1024 维模型必须全量重建 FAISS 索引 + 内存升至 ~1.2GB，投入产出比低。

### 建议

维持 all-MiniLM-L6-v2 不变。理由：语料量小、Recall 已 100%，真正影响体验的页码错位/虚构主题/并发崩溃均不靠换模型解决（已修复）。仅在出现"明显召回不足（某主题确存在却 skipped）"或"小 top_k 召错"时，再考虑 e5-large-v2（MRR 最高）。

---

## 6. 关联文档

- 历史完整评估：docs/embedding_model_evaluation_report.md（2026-08-07，33 查询、5 模型、含 latency）
- 相关 spec：docs/superpowers/specs/2026-08-13-retrieval-summarize-pdf-redesign.md

## 7. 待办（可选）

- [ ] 为 embedding.py 的并发锁补一个多线程单元测试
- [ ] 观察重跑暴露的 heading 污染（如 "BLOCKSWORLD ACTION" vs "BLOCKSWORLD ACTIONS" 重复），可在 parse_topic_summary_json 用 topic.title 兜底 heading
