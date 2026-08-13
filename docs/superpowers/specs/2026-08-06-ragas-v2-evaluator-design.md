# RAGAS V2 Evaluator Design

**Date:** 2026-08-06
**Status:** Draft
**Goal:** Fresh modular RAGAS evaluation using the v0.4.x API with OpenAI-compatible judge LLM, integrated with the existing RAG pipeline.

---

## Problem

The current `evaluation/ragas/ragas_evaluator.py` and `scripts/ragas_baseline.py` use the old RAGAS v0.1.x API (`LangchainLLMWrapper`, `from ragas.metrics import faithfulness`, `RunConfig`). RAGAS v0.4.x has a completely different API surface. We need a new evaluator that follows the official v0.4.x documentation.

## Goals

1. Use RAGAS v0.4.x API (`llm_factory()`, `EvaluationDataset`, `SingleTurnSample`, modern metrics from `ragas.metrics.collections`)
2. OpenAI-compatible judge LLM only (no Anthropic/Gemini direct integration)
3. Reuse existing RAG pipeline (`retrieve_with_faiss()` + `generate_with_local_llm()`)
4. JSONL-only input: `{question, ground_truth}` per line (no PDF/QA generation in scope)
5. Clean separation: config, dataset builder, evaluator, reporter
6. CLI script with a single `evaluate` subcommand

## Non-Goals

- Replacing the old evaluator (old code stays for backward compatibility)
- Multi-provider judge LLM support (only OpenAI-compatible)
- Testset generation (can be added later)
- Django view integration (out of scope)
- QA pair generation from PDFs (user decision: JSONL-only input)
- PDF processing (user decision: simplified scope)

## Design Decisions (2026-08-06 review)

1. Target RAGAS `>=0.4.0,<0.5.0` (upgrade from installed 0.3.2) - docs-aligned
2. Simplify to JSONL-only: input is `{question, ground_truth}`, the evaluator runs the RAG pipeline to produce `answer` + `contexts`, then scores
3. Metrics imported from `ragas.metrics.collections` (modern v0.4.x location); `ragas.metrics` direct imports are deprecated in 0.4.x
4. Judge LLM via `llm_factory(model, provider="openai", client=OpenAI(...))`
5. Embeddings: use RAGAS `BaseRagasEmbedding` interface, NOT langchain - keep the new module langchain-free
6. Defer Django setup to CLI main() so module import is safe for tests

---

## Architecture

### New Files

```
app/services/ragas_v2.py          # Core evaluator class
scripts/ragas_v2_eval.py          # CLI entry point
```

### Modified Files

```
requirements.txt                  # Update ragas pin, add openai
```

### Existing Files (unchanged)

```
evaluation/ragas/ragas_evaluator.py   # Old evaluator, kept as-is
scripts/ragas_baseline.py             # Old CLI, kept as-is
```

---

## Class Design: `RAGASEvaluatorV2`

**Location:** `app/services/ragas_v2.py`

```python
class RAGASEvaluatorV2:
    """RAGAS v0.4.x evaluator for RAG pipeline quality."""

    def __init__(
        self,
        judge_base_url: Optional[str] = None,
        judge_model: Optional[str] = None,
        judge_api_key: Optional[str] = None,
    ):
        """
        Initialize with judge LLM config.

        Resolution priority:
        1. Explicit args
        2. RAGAS_JUDGE_BASE_URL, RAGAS_JUDGE_MODEL, RAGAS_JUDGE_API_KEY env vars
        3. OPENROUTER_API_KEY + deepseek/deepseek-v4-flash
        4. Local llama.cpp at settings.LOCAL_LLM_BASE_URL
        """

    def _resolve_judge_config(self) -> dict[str, str]:
        """Resolve judge LLM config with fallback chain."""

    def _build_judge_llm(self):
        """Create llm_factory()-based judge LLM.

        llm = llm_factory(judge_model, provider="openai", client=OpenAI(base_url=..., api_key=...))
        """

    def _build_ragas_embeddings(self):
        """Build a BaseRagasEmbedding wrapping the existing EmbeddingService.

        Implements embed_text()/aembed_text() (RAGAS modern interface), no langchain import.
        """

    def run_rag(
        self,
        questions: list[str],
        ground_truths: list[str],
        top_k: int = 5,
    ) -> list[dict]:
        """Run RAG pipeline for each question.

        Returns list of {question, answer, contexts, ground_truth}.
        Uses retrieve_with_faiss() + generate_with_local_llm().
        """

    def evaluate(
        self,
        dataset_path: str,
        top_k: int = 5,
        ragas_timeout: int = 300,
        ragas_max_workers: int = 4,
    ) -> dict:
        """Full evaluation: load JSONL -> run RAG -> score with RAGAS -> save CSV.

        Returns {num_questions, scores, csv_path, detailed}.
        """

    @staticmethod
    def format_report(result: dict) -> str:
        """Format evaluation result as readable report."""
```

Removed: `generate_qa_pairs()` and `evaluate_from_pdfs()` (JSONL-only scope).

---

## Judge LLM Configuration

**Resolution priority:**

1. Explicit constructor args (`judge_base_url`, `judge_model`, `judge_api_key`)
2. Environment variables: `RAGAS_JUDGE_BASE_URL`, `RAGAS_JUDGE_MODEL`, `RAGAS_JUDGE_API_KEY`
3. Fallback to OpenRouter with `OPENROUTER_API_KEY` + `deepseek/deepseek-v4-flash`
4. Final fallback to local llama.cpp at `settings.LOCAL_LLM_BASE_URL`

**Implementation with `llm_factory()`:**

```python
from ragas.llms import llm_factory
from openai import OpenAI

client = OpenAI(base_url=judge_base_url, api_key=judge_api_key)
judge_llm = llm_factory(judge_model, provider="openai", client=client)
```

**Embeddings:** Implement a `BaseRagasEmbedding` subclass that wraps the existing `EmbeddingService` with `embed_text()`/`aembed_text()`. No langchain import in the new module. The `evaluate()` call passes `embeddings=` and metrics that need embeddings (`AnswerRelevancy`) receive them at construction.

---

## Metrics & Dataset

**Metrics (RAGAS v0.4.x):**

```python
from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall

metrics = [
    Faithfulness(),
    AnswerRelevancy(),
    ContextPrecision(),
    ContextRecall(),
]
```

Important (verified against ragas 0.4.3): the top-level `ragas.evaluate()` validates metrics with `isinstance(m, Metric)` against the legacy `ragas.metrics.base.Metric` base class. The modern `ragas.metrics.collections` classes use their own `score()/ascore()` micro-API and are **rejected** by `evaluate()` with "All metrics must be initialised metric objects". Therefore the legacy `ragas.metrics` import is used. Metrics are constructed **without** `llm`/`embeddings`; `evaluate(llm=..., embeddings=...)` auto-fills metric-level values. This produces deprecation warnings (acceptable, since collections does not integrate with `evaluate()` in 0.4.x).

**Dataset construction:**

```python
from ragas import EvaluationDataset, SingleTurnSample

samples = [
    SingleTurnSample(
        user_input=q["question"],
        retrieved_contexts=q["contexts"],
        response=q["answer"],
        reference=q["ground_truth"],
    )
    for q in rag_results
]
dataset = EvaluationDataset(samples=samples)
```

Note: `EvaluationDataset` and `SingleTurnSample` are exported from the top-level `ragas` package in v0.4.x (also available at `ragas.dataset_schema`).

**Result handling:**

```python
from ragas import evaluate as ragas_evaluate

result = ragas_evaluate(
    dataset=dataset,
    metrics=metrics,
    llm=judge_llm,
    embeddings=ragas_embeddings,
)
df = result.to_pandas()
df.to_csv(out_path, index=False)
return {
    "num_questions": len(samples),
    "scores": {col: float(df[col].mean()) for col in metric_cols},
    "csv_path": out_path,
    "detailed": df.to_dict(orient="records"),
}
```

---

## CLI Script

**Location:** `scripts/ragas_v2_eval.py`

Single `evaluate` subcommand (JSONL input only):

```bash
python scripts/ragas_v2_eval.py evaluate \
    --dataset eval_baseline.jsonl \
    --out results/ragas_v2_result.csv \
    --judge-base-url http://localhost:8080/v1 \
    --judge-model deepseek/deepseek-v4-flash \
    --judge-api-key local \
    --top-k 5 \
    --timeout 300 \
    --max-workers 4
```

JSONL format (one object per line):
```json
{"question": "...", "ground_truth": "..."}
```

Django setup is deferred to `main()` (lazy import), so importing the module in tests does not trigger `django.setup()`.

The `judge-base-url` is normalized to end in `/v1` if missing (OpenAI SDK requirement).

---

## Error Handling

- Custom exception: `RAGASEvaluatorError`
- Catch specific exceptions, never bare `except:`
- Log warnings for failed questions, continue with remaining
- Return JSON errors with `detail` field using `_error_response()` pattern

---

## Dependencies

Update `requirements.txt`:

```
ragas>=0.4.0,<0.5.0
datasets>=2.14.0,<3.0.0
openai>=1.0.0
```

---

## Testing

- Unit tests in `tests/test_ragas_v2.py`
- Mock `retrieve_with_faiss()`, `generate_with_local_llm()`, `call_llm()`
- Test judge config resolution (env vars, fallbacks)
- Test dataset construction with `SingleTurnSample`
- Integration test with mock RAGAS `evaluate`
- CLI test imports the module WITHOUT triggering `django.setup()` (deferred to `main()`)

---

## Migration Notes

- Old `evaluation/ragas/ragas_evaluator.py` stays as-is (no breaking changes)
- Old `scripts/ragas_baseline.py` stays as-is
- New code lives in `app/services/ragas_v2.py` and `scripts/ragas_v2_eval.py`
- Users can run both old and new evaluators side by side
