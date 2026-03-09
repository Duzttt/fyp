# RAG Feature Implementation Skill

## Standard RAG Implementation Checklist

Use this checklist for all RAG-related feature implementations to ensure consistency, quality, and proper integration.

---

### Phase 1: Architecture & Planning

- [ ] **Confirm current architecture**
  - [ ] Identify frontend framework (Vue 3 vs Django templates)
  - [ ] Review existing RAG pipeline components
  - [ ] Check for locked files or build system requirements
  - [ ] Document integration points with existing code

- [ ] **Create detailed todo list**
  - [ ] Break down feature into discrete tasks
  - [ ] Identify backend vs frontend work
  - [ ] Estimate complexity per task
  - [ ] Confirm integration approach before writing code

- [ ] **Review design patterns**
  - [ ] Check existing UI components for consistency
  - [ ] Review API endpoint conventions
  - [ ] Confirm error handling patterns
  - [ ] Check logging/monitoring standards

---

### Phase 2: Backend Implementation

- [ ] **Implement core RAG services**
  - [ ] Create/modify retrieval logic (BM25, Dense, Hybrid)
  - [ ] Implement chunking strategy if needed
  - [ ] Add embedding service integration
  - [ ] Configure vector store operations

- [ ] **Build API endpoints**
  - [ ] Define request/response schemas (Pydantic)
  - [ ] Implement endpoint handlers in Django views
  - [ ] Add input validation and error handling
  - [ ] Document API in API_DOCUMENTATION.md

- [ ] **Add configuration management**
  - [ ] Update retrieval_config.py with new parameters
  - [ ] Add environment variables to .env.example
  - [ ] Ensure JSON config persistence if needed

- [ ] **Implement similarity thresholds**
  - [ ] Define threshold constants in config
  - [ ] Add threshold logic to retrieval pipeline
  - [ ] Document threshold impact on recall/precision

---

### Phase 3: Frontend Implementation

- [ ] **Verify architecture** (re-confirm before changes)
  - [ ] Confirm Vue 3 component structure
  - [ ] Check Django template requirements
  - [ ] Verify API client location (services/api.js)

- [ ] **Implement UI components**
  - [ ] Reference existing design patterns
  - [ ] Use TailwindCSS for styling consistency
  - [ ] Add loading states and error handling
  - [ ] Implement real-time updates if needed (WebSocket)

- [ ] **Integrate with backend**
  - [ ] Add API calls to frontend services
  - [ ] Handle async responses properly
  - [ ] Add error toast/notification handling
  - [ ] Test end-to-end flow

---

### Phase 4: Testing & Verification

- [ ] **Write unit tests**
  - [ ] Test retrieval logic (recall, precision, MRR, NDCG)
  - [ ] Test chunking boundaries and overlap
  - [ ] Test similarity threshold behavior
  - [ ] Test fusion methods (RRF, Weighted)

- [ ] **Write integration tests**
  - [ ] Test API endpoints end-to-end
  - [ ] Test frontend-backend integration
  - [ ] Test error scenarios

- [ ] **Run performance benchmarks**
  - [ ] Execute tests/benchmark.py
  - [ ] Verify latency <200ms p95
  - [ ] Check Recall@5 >75% target
  - [ ] Monitor cache hit rates

- [ ] **Run full test suite**
  - [ ] `pytest tests/ -v` for all tests
  - [ ] `ruff check` for linting
  - [ ] `black` for formatting
  - [ ] `mypy` for type checking

---

### Phase 5: Documentation & Deployment

- [ ] **Update documentation**
  - [ ] Add to API_DOCUMENTATION.md
  - [ ] Update EVALUATION_REPORT.md if metrics changed
  - [ ] Add usage examples
  - [ ] Document configuration options

- [ ] **Prepare for deployment**
  - [ ] Check .gitignore for new files
  - [ ] Update requirements.txt if new dependencies
  - [ ] Verify migration requirements
  - [ ] Test in development environment

- [ ] **Monitor post-deployment**
  - [ ] Check PerformanceMonitor logs
  - [ ] Verify cache behavior
  - [ ] Monitor error rates
  - [ ] Collect user feedback

---

## Quick Reference

### Test Commands
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_hybrid_retrieval.py -v

# Run benchmark
python tests/benchmark.py

# Check retrieval quality for a query
python tests/check_retrieval_quality.py "your query here"

# Lint and format
ruff check app/ django_app/ retrieval/ chunking/ evaluation/
black app/ django_app/ retrieval/ chunking/ evaluation/
mypy app/ django_app/ retrieval/ chunking/ evaluation/
```

### Vector-DB MCP Integration

For external vector database queries via MCP:

```bash
# Add vector-db MCP server
qwen mcp add --transport http vector-db http://localhost:6333/mcp/

# Then ask Qwen to:
# "check retrieval quality for query X using the vector-db MCP"
```

For local FAISS-based retrieval (current project setup):

```python
from retrieval.hybrid_retriever import HybridRetriever, FusionMethod

retriever = HybridRetriever(documents, fusion_method=FusionMethod.RRF)
results = retriever.retrieve_with_scores(query, top_k=5)
```

### Key Files
- `retrieval/` - BM25, Dense, Hybrid retrievers
- `chunking/` - SmartChunker implementation
- `evaluation/` - Metrics and performance monitoring
- `config/` - Configuration management
- `django_app/views.py` - API endpoints
- `data/rag_config.json` - Runtime configuration

### Performance Targets
- **Recall@5**: >75%
- **Latency p95**: <200ms
- **Cache hit rate**: >60%

---

## When to Use This Skill

Invoke this skill when:
- Implementing new RAG retrieval methods
- Adding chunking strategies
- Modifying similarity thresholds
- Building RAG-related UI components
- Integrating new LLM providers
- Optimizing retrieval performance
