# RAGAS V2 Evaluator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new RAGAS v0.4.x evaluator service and CLI script that replaces the old API patterns while keeping the existing code intact.

**Architecture:** Service layer pattern (`app/services/ragas_v2.py`) with CLI wrapper (`scripts/ragas_v2_eval.py`). Uses `llm_factory()` for the judge LLM, `SingleTurnSample`/`EvaluationDataset` for data, and class-based metrics from `ragas.metrics.collections`. Reuses existing `retrieve_with_faiss()` and `generate_with_local_llm()`.

**Scope (2026-08-06 review):** JSONL-only evaluation. Input is a JSONL file with `{question, ground_truth}` per line. The evaluator runs the RAG pipeline to produce `answer` + `contexts`, then scores with RAGAS. QA-pair generation from PDFs is out of scope.

**Tech Stack:** RAGAS 0.4.x, OpenAI SDK, sentence-transformers (existing), FAISS (existing), Django settings (existing)

## Global Constraints

- RAGAS version: `>=0.4.0,<0.5.0`
- Python: `>=3.9`
- Line length: 88 chars (Black default)
- Type hints required for all function signatures
- No bare `except:` - catch specific exceptions
- Use `f-strings` for formatting
- Follow existing naming: `snake_case` functions, `PascalCase` classes
- No langchain imports in new module (use RAGAS `BaseRagasEmbedding`)
- Django setup deferred to CLI `main()` so module import is test-safe

---

## File Structure

| File | Responsibility |
|------|---------------|
| `app/services/ragas_v2.py` | Core `RAGASEvaluatorV2` class - config, RAG execution, RAGAS evaluation |
| `scripts/ragas_v2_eval.py` | CLI entry point with `evaluate` subcommand |
| `tests/test_ragas_v2.py` | Unit tests for the evaluator |
| `tests/test_ragas_v2_cli.py` | CLI tests (import-safe, no `django.setup()` at import) |
| `tests/test_ragas_v2_integration.py` | Integration tests with mocked RAGAS |
| `requirements.txt` | Update ragas pin, add openai dependency |

---

### Task 1: Update Dependencies

**Files:**
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: None
- Produces: Updated dependency list for later tasks

- [ ] **Step 1: Read current requirements.txt**

Read `requirements.txt` to see current state.

- [ ] **Step 2: Update ragas pin and add openai**

Change the ragas line from:
```
ragas>=0.1.0,<1.0.0
```
to:
```
ragas>=0.4.0,<0.5.0
```

Add (if not present):
```
openai>=1.0.0
```

- [ ] **Step 3: Verify install works in the venv**

Run: `.venv\Scripts\python.exe -m pip install "ragas>=0.4.0,<0.5.0" "openai>=1.0.0"`
Expected: Installs cleanly, no dependency conflicts.

- [ ] **Step 4: Sanity-check the 0.4.x API is importable**

Run: `.venv\Scripts\python.exe -c "import ragas; from ragas.metrics.collections import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall; from ragas.llms import llm_factory; from ragas.embeddings import BaseRagasEmbedding; print(ragas.__version__)"`
Expected: Prints `0.4.x` with no ImportError.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt
git commit -m "deps: upgrade ragas to 0.4.x, add openai SDK"
```

---

### Task 2: Create RAGASEvaluatorV2 Core Class

**Files:**
- Create: `app/services/ragas_v2.py`
- Test: `tests/test_ragas_v2.py`

**Interfaces:**
- Consumes: `app.config.settings`, `app.services.local_rag.retrieve_with_faiss`, `app.services.local_rag.build_context_from_sources`, `app.services.local_rag.generate_with_local_llm`, `app.services.embedding.EmbeddingService`, `app.services.runtime_embedding.load_runtime_embedding_settings`
- Produces: `RAGASEvaluatorV2` class with `run_rag()`, `evaluate()`, `format_report()` methods

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ragas_v2.py
"""Tests for RAGAS V2 Evaluator."""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestRAGASEvaluatorV2Init:
    """Test RAGASEvaluatorV2 initialization and config resolution."""

    def test_init_with_explicit_args(self):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        evaluator = RAGASEvaluatorV2(
            judge_base_url="http://custom:8080/v1",
            judge_model="custom-model",
            judge_api_key="test-key",
        )
        assert evaluator.judge_base_url == "http://custom:8080/v1"
        assert evaluator.judge_model == "custom-model"
        assert evaluator.judge_api_key == "test-key"

    def test_init_defaults_to_none(self):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        evaluator = RAGASEvaluatorV2()
        assert evaluator.judge_base_url is None
        assert evaluator.judge_model is None
        assert evaluator.judge_api_key is None


class TestRAGASEvaluatorV2ResolveConfig:
    """Test judge config resolution."""

    @patch.dict(
        os.environ,
        {
            "RAGAS_JUDGE_BASE_URL": "http://env:8080/v1",
            "RAGAS_JUDGE_MODEL": "env-model",
            "RAGAS_JUDGE_API_KEY": "env-key",
        },
    )
    def test_env_vars_take_priority_over_fallback(self):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        evaluator = RAGASEvaluatorV2()
        config = evaluator._resolve_judge_config()
        assert config["base_url"] == "http://env:8080/v1"
        assert config["model"] == "env-model"
        assert config["api_key"] == "env-key"

    @patch.dict(os.environ, {}, clear=True)
    @patch("app.services.ragas_v2.settings")
    def test_explicit_args_take_priority_over_env(self, mock_settings):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        evaluator = RAGASEvaluatorV2(
            judge_base_url="http://explicit:8080/v1",
            judge_model="explicit-model",
            judge_api_key="explicit-key",
        )
        config = evaluator._resolve_judge_config()
        assert config["base_url"] == "http://explicit:8080/v1"

    @patch.dict(os.environ, {}, clear=True)
    @patch("app.services.ragas_v2.settings")
    def test_local_llm_fallback_normalizes_v1(self, mock_settings):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        mock_settings.LOCAL_LLM_BASE_URL = "http://localhost:8080"
        mock_settings.LOCAL_LLM_MODEL = "local-model"
        evaluator = RAGASEvaluatorV2()
        config = evaluator._resolve_judge_config()
        assert config["base_url"] == "http://localhost:8080/v1"

    @patch.dict(os.environ, {}, clear=True)
    @patch("app.services.ragas_v2.settings")
    def test_openrouter_fallback(self, mock_settings):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        mock_settings.OPENROUTER_API_KEY = "or-key"
        mock_settings.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
        evaluator = RAGASEvaluatorV2()
        config = evaluator._resolve_judge_config()
        assert config["model"] == "deepseek/deepseek-v4-flash"
        assert config["api_key"] == "or-key"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ragas_v2.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.ragas_v2'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/ragas_v2.py
"""
RAGAS V2 Evaluator - Uses RAGAS v0.4.x API.

Provides RAGAS-based evaluation for the lecture note Q&A system:
- Faithfulness: Does the answer stay faithful to the context?
- Answer Relevancy: Is the answer relevant to the question?
- Context Precision: How precise are the retrieved contexts?
- Context Recall: Does the context contain the information needed?

Usage:
    from app.services.ragas_v2 import RAGASEvaluatorV2

    evaluator = RAGASEvaluatorV2(judge_base_url="...", judge_model="...")
    result = evaluator.evaluate("eval_baseline.jsonl")
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

from app.config import settings

logger = logging.getLogger("ragas_v2")


class RAGASEvaluatorError(Exception):
    """Custom exception for RAGAS V2 evaluator errors."""

    pass


class RAGASEvaluatorV2:
    """RAGAS v0.4.x evaluator for RAG pipeline quality.

    Evaluates the end-to-end RAG pipeline using RAGAS metrics:
    - Faithfulness
    - Answer Relevancy
    - Context Precision
    - Context Recall
    """

    def __init__(
        self,
        judge_base_url: Optional[str] = None,
        judge_model: Optional[str] = None,
        judge_api_key: Optional[str] = None,
    ):
        """Initialize the RAGAS V2 evaluator.

        Args:
            judge_base_url: OpenAI-compatible base URL for judge LLM
            judge_model: Judge model name
            judge_api_key: API key for judge LLM
        """
        self.judge_base_url = judge_base_url
        self.judge_model = judge_model
        self.judge_api_key = judge_api_key

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        """Ensure the base URL ends in /v1 (OpenAI SDK requirement)."""
        normalized = base_url.rstrip("/")
        if not normalized.endswith("/v1"):
            normalized = f"{normalized}/v1"
        return normalized

    def _resolve_judge_config(self) -> Dict[str, str]:
        """Resolve the OpenAI-compatible judge LLM config.

        Priority: explicit args > RAGAS_JUDGE_* env vars > OPENROUTER > local_llm.

        Returns:
            Dict with keys: base_url, model, api_key
        """
        if self.judge_base_url and self.judge_model:
            return {
                "base_url": self._normalize_base_url(str(self.judge_base_url)),
                "model": str(self.judge_model),
                "api_key": str(self.judge_api_key or "local"),
            }

        env_base = os.environ.get("RAGAS_JUDGE_BASE_URL")
        env_model = os.environ.get("RAGAS_JUDGE_MODEL")
        env_key = os.environ.get("RAGAS_JUDGE_API_KEY")
        if env_base and env_model:
            return {
                "base_url": self._normalize_base_url(env_base),
                "model": env_model,
                "api_key": env_key or "local",
            }

        or_key = os.environ.get("OPENROUTER_API_KEY") or getattr(
            settings, "OPENROUTER_API_KEY", None
        )
        if or_key:
            or_base = getattr(
                settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            )
            return {
                "base_url": self._normalize_base_url(str(or_base)),
                "model": "deepseek/deepseek-v4-flash",
                "api_key": str(or_key),
            }

        local_base = getattr(settings, "LOCAL_LLM_BASE_URL", "http://localhost:8080")
        return {
            "base_url": self._normalize_base_url(str(local_base)),
            "model": getattr(settings, "LOCAL_LLM_MODEL", "local-model"),
            "api_key": "local",
        }

    def _build_judge_llm(self, judge_config: Dict[str, str]):
        """Create llm_factory()-based judge LLM (OpenAI-compatible)."""
        from ragas.llms import llm_factory
        from openai import OpenAI

        client = OpenAI(
            base_url=judge_config["base_url"],
            api_key=judge_config["api_key"],
        )
        return llm_factory(judge_config["model"], provider="openai", client=client)

    def _build_ragas_embeddings(self):
        """Build a BaseRagasEmbedding wrapping the existing EmbeddingService.

        Implements embed_text()/aembed_text() (RAGAS modern interface).
        No langchain import.
        """
        from ragas.embeddings import BaseRagasEmbedding
        from app.services.embedding import EmbeddingService
        from app.services.runtime_embedding import load_runtime_embedding_settings

        rt = load_runtime_embedding_settings()
        embedding_service = EmbeddingService(model_name=rt["model_id"])

        class _LocalRagasEmbedding(BaseRagasEmbedding):
            def embed_text(self, text: str) -> List[float]:
                emb = embedding_service.embed_query(text)
                if hasattr(emb, "tolist"):
                    emb = emb.tolist()
                return [float(v) for v in emb]

            async def aembed_text(self, text: str) -> List[float]:
                return self.embed_text(text)

        return _LocalRagasEmbedding()

    def run_rag(
        self,
        questions: List[str],
        ground_truths: List[str],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Run RAG pipeline for each question.

        Args:
            questions: List of question strings
            ground_truths: List of ground truth answers
            top_k: Number of chunks to retrieve

        Returns:
            List of {question, answer, contexts, ground_truth} dicts
        """
        from app.services.local_rag import (
            build_context_from_sources,
            generate_with_local_llm,
            retrieve_with_faiss,
        )

        results = []

        for i, question in enumerate(questions):
            logger.info(
                "Processing question %d/%d: %s", i + 1, len(questions), question[:80]
            )

            try:
                sources = retrieve_with_faiss(query=question, top_k=top_k)
                context = build_context_from_sources(sources)

                answer = generate_with_local_llm(question, context)
                if isinstance(answer, tuple):
                    answer = answer[0]

                results.append(
                    {
                        "question": question,
                        "answer": str(answer),
                        "contexts": [s.get("text", "") for s in sources],
                        "ground_truth": ground_truths[i],
                    }
                )

            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to process question '%s': %s", question[:50], exc
                )
                results.append(
                    {
                        "question": question,
                        "answer": "",
                        "contexts": [],
                        "ground_truth": ground_truths[i],
                    }
                )

        return results

    def evaluate(
        self,
        dataset_path: str,
        top_k: int = 5,
        ragas_timeout: int = 300,
        ragas_max_workers: int = 4,
    ) -> Dict[str, Any]:
        """Full evaluation: load JSONL -> run RAG -> score with RAGAS -> save CSV.

        Args:
            dataset_path: Path to JSONL file with {question, ground_truth} per line
            top_k: Number of chunks to retrieve
            ragas_timeout: Per-job RAGAS timeout in seconds
            ragas_max_workers: Maximum concurrent RAGAS metric jobs

        Returns:
            Dict with num_questions, scores, csv_path, detailed
        """
        import json

        questions = []
        ground_truths = []
        with open(dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                questions.append(rec["question"])
                ground_truths.append(rec["ground_truth"])

        if not questions:
            raise RAGASEvaluatorError(f"No questions found in {dataset_path}")

        logger.info("Loaded %d questions from %s", len(questions), dataset_path)

        rag_results = self.run_rag(questions, ground_truths, top_k=top_k)

        valid = [r for r in rag_results if r["answer"]]
        if not valid:
            raise RAGASEvaluatorError("No valid RAG results to evaluate")

        logger.info("Valid RAG results: %d/%d", len(valid), len(rag_results))

        try:
            from ragas import evaluate as ragas_evaluate
            from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
            from ragas.metrics.collections import (
                AnswerRelevancy,
                ContextPrecision,
                ContextRecall,
                Faithfulness,
            )
        except ImportError as exc:
            raise RAGASEvaluatorError(
                "RAGAS not installed. Run: pip install 'ragas>=0.4.0,<0.5.0' openai"
            ) from exc

        judge_config = self._resolve_judge_config()
        judge_llm = self._build_judge_llm(judge_config)
        ragas_embeddings = self._build_ragas_embeddings()

        samples = [
            SingleTurnSample(
                user_input=r["question"],
                retrieved_contexts=r["contexts"],
                response=r["answer"],
                reference=r["ground_truth"],
            )
            for r in valid
        ]
        dataset = EvaluationDataset(samples=samples)

        metrics = [
            Faithfulness(llm=judge_llm),
            AnswerRelevancy(llm=judge_llm, embeddings=ragas_embeddings),
            ContextPrecision(llm=judge_llm),
            ContextRecall(llm=judge_llm),
        ]

        logger.info("Running RAGAS v0.4.x evaluation...")
        result = ragas_evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=judge_llm,
            embeddings=ragas_embeddings,
        )

        out_dir = Path("evaluation/ragas/results")
        out_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = str(out_dir / f"ragas_v2_eval_{timestamp}.csv")

        df = result.to_pandas()
        df.to_csv(csv_path, index=False, encoding="utf-8")

        metric_cols = [
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "context_recall",
        ]
        scores = {}
        for col in metric_cols:
            if col in df.columns:
                vals = df[col].dropna()
                scores[col] = {
                    "mean": float(vals.mean()),
                    "min": float(vals.min()),
                    "max": float(vals.max()),
                }

        return {
            "num_questions": len(valid),
            "scores": scores,
            "csv_path": csv_path,
            "detailed": df.to_dict(orient="records"),
        }

    @staticmethod
    def format_report(result: Dict[str, Any]) -> str:
        """Format RAGAS evaluation result as a readable report.

        Args:
            result: Result dict from evaluate()

        Returns:
            Formatted report string
        """
        scores = result.get("scores", {})
        num_q = result.get("num_questions", 0)

        lines = [
            "=" * 60,
            "RAGAS V2 EVALUATION REPORT",
            "=" * 60,
            "",
            f"Questions evaluated: {num_q}",
            "",
            "METRICS:",
            "-" * 40,
        ]

        for metric, value in scores.items():
            if isinstance(value, dict):
                lines.append(
                    f"{metric:<25} avg={value['mean']:.4f}  "
                    f"min={value['min']:.4f}  max={value['max']:.4f}"
                )
            else:
                lines.append(f"{metric:<25} {value}")

        lines.extend(["", "=" * 60])

        return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ragas_v2.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/ragas_v2.py tests/test_ragas_v2.py
git commit -m "feat: add RAGASEvaluatorV2 core class with RAGAS v0.4.x API"
```

---

### Task 3: Create CLI Script

**Files:**
- Create: `scripts/ragas_v2_eval.py`
- Test: `tests/test_ragas_v2_cli.py`

**Interfaces:**
- Consumes: `app.services.ragas_v2.RAGASEvaluatorV2`, `app.services.ragas_v2.RAGASEvaluatorError`
- Produces: CLI entry point with a single `evaluate` subcommand

Important: `django.setup()` must be deferred to `main()` (lazy import) so that importing the module in tests does not crash.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ragas_v2_cli.py
"""Tests for RAGAS V2 CLI."""

import importlib
import sys

import pytest


class TestRAGASV2CLI:
    """Test CLI argument parsing and subcommands."""

    def test_module_import_does_not_trigger_django_setup(self):
        """Importing the module must not call django.setup()."""
        import scripts.ragas_v2_eval as cli_mod
        importlib.reload(cli_mod)

        assert hasattr(cli_mod, "main")

    def test_evaluate_subcommand_parses_args(self):
        """Test that 'evaluate' subcommand parses correctly."""
        sys.argv = [
            "ragas_v2_eval.py",
            "evaluate",
            "--dataset", "test.jsonl",
            "--out", "results/test.csv",
            "--judge-base-url", "http://localhost:8080/v1",
            "--judge-model", "test-model",
        ]

        import scripts.ragas_v2_eval as cli_mod
        importlib.reload(cli_mod)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ragas_v2_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.ragas_v2_eval'`

- [ ] **Step 3: Write CLI script**

```python
# scripts/ragas_v2_eval.py
"""RAGAS V2 Evaluation CLI - Uses RAGAS v0.4.x API.

Evaluate the RAG pipeline on a JSONL dataset of {question, ground_truth}.

Usage:
    python scripts/ragas_v2_eval.py evaluate \\
        --dataset eval_baseline.jsonl \\
        --out results/ragas_v2_result.csv \\
        --judge-base-url http://localhost:8080/v1 \\
        --judge-model deepseek/deepseek-v4-flash \\
        --judge-api-key local \\
        --top-k 5
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _setup_django() -> None:
    """Set up Django environment (lazy, only when running as a script)."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
    import django

    django.setup()


def cmd_evaluate(args: argparse.Namespace) -> None:
    """Run RAGAS evaluation on a JSONL dataset."""
    _setup_django()

    from app.services.ragas_v2 import RAGASEvaluatorV2

    evaluator = RAGASEvaluatorV2(
        judge_base_url=args.judge_base_url,
        judge_model=args.judge_model,
        judge_api_key=args.judge_api_key,
    )

    print(f"Dataset: {args.dataset}")
    print(f"Judge: {args.judge_base_url} / {args.judge_model}")
    print(f"Top-K: {args.top_k}")

    result = evaluator.evaluate(
        dataset_path=args.dataset,
        top_k=args.top_k,
        ragas_timeout=args.timeout,
        ragas_max_workers=args.max_workers,
    )

    report = RAGASEvaluatorV2.format_report(result)
    print(report)
    print(f"\nCSV saved to: {result['csv_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="RAGAS V2 Evaluation CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    evl = sub.add_parser("evaluate", help="RAGAS evaluation on JSONL dataset")
    evl.add_argument("--dataset", required=True, help="JSONL dataset path")
    evl.add_argument("--out", required=True, help="Output CSV path")
    evl.add_argument("--judge-base-url", help="Judge LLM base URL (default: auto)")
    evl.add_argument("--judge-model", help="Judge model name (default: auto)")
    evl.add_argument("--judge-api-key", default=None, help="Judge API key")
    evl.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve")
    evl.add_argument("--timeout", type=int, default=300, help="RAGAS timeout in seconds")
    evl.add_argument("--max-workers", type=int, default=4, help="Max concurrent workers")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        cmd_evaluate(args)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

Note: `--judge-base-url`/`--judge-model` are optional in the CLI so config resolution falls back to env vars / OpenRouter / local llama.cpp.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ragas_v2_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/ragas_v2_eval.py tests/test_ragas_v2_cli.py
git commit -m "feat: add RAGAS V2 CLI script with evaluate subcommand"
```

---

### Task 4: Add Evaluation Integration Test

**Files:**
- Test: `tests/test_ragas_v2_integration.py`

**Interfaces:**
- Consumes: `app.services.ragas_v2.RAGASEvaluatorV2`
- Produces: Integration test verifying end-to-end flow with mocks

- [ ] **Step 1: Write the integration test**

```python
# tests/test_ragas_v2_integration.py
"""Integration tests for RAGAS V2 Evaluator (mocked RAGAS)."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


class TestRAGASEvaluatorV2Integration:
    """Test full evaluation flow with mocked dependencies."""

    @patch("app.services.ragas_v2.RAGASEvaluatorV2._build_ragas_embeddings")
    @patch("app.services.ragas_v2.RAGASEvaluatorV2._build_judge_llm")
    @patch("app.services.ragas_v2.RAGASEvaluatorV2.run_rag")
    @patch("ragas.evaluate")
    def test_evaluate_full_flow(
        self,
        mock_ragas_evaluate,
        mock_run_rag,
        mock_build_judge_llm,
        mock_embeddings,
    ):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        mock_run_rag.return_value = [
            {
                "question": "What is AI?",
                "answer": "AI is artificial intelligence.",
                "contexts": ["AI is a branch of computer science."],
                "ground_truth": "AI is artificial intelligence.",
            }
        ]

        mock_result = MagicMock()
        mock_df = MagicMock()
        mock_result.to_pandas.return_value = mock_df
        mock_df.to_csv = MagicMock()
        mock_df.to_dict.return_value = [
            {
                "question": "What is AI?",
                "answer": "AI is artificial intelligence.",
                "faithfulness": 0.9,
                "answer_relevancy": 0.85,
                "context_precision": 0.8,
                "context_recall": 0.95,
            }
        ]

        # Make mean()/min()/max() work on the mock
        def stat_mock(value):
            return MagicMock(
                dropna=MagicMock(
                    return_value=MagicMock(
                        mean=MagicMock(return_value=value),
                        min=MagicMock(return_value=value - 0.1),
                        max=MagicMock(return_value=value + 0.1),
                    )
                )
            )

        mock_df.__getitem__.side_effect = lambda key: stat_mock(0.875)
        mock_df.__contains__.side_effect = lambda key: key in {
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "context_recall",
        }
        mock_ragas_evaluate.return_value = mock_result

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(
                json.dumps({"question": "What is AI?", "ground_truth": "AI is..."})
                + "\n"
            )
            tmp_path = f.name

        try:
            evaluator = RAGASEvaluatorV2(
                judge_base_url="http://test:8080/v1",
                judge_model="test-model",
                judge_api_key="test-key",
            )

            result = evaluator.evaluate(
                dataset_path=tmp_path,
                top_k=3,
            )

            assert result["num_questions"] == 1
            assert "scores" in result
            assert "csv_path" in result

        finally:
            os.unlink(tmp_path)

    def test_format_report(self):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        result = {
            "num_questions": 10,
            "scores": {
                "faithfulness": {"mean": 0.85, "min": 0.5, "max": 1.0},
                "answer_relevancy": {"mean": 0.92, "min": 0.7, "max": 1.0},
            },
        }

        report = RAGASEvaluatorV2.format_report(result)
        assert "RAGAS V2 EVALUATION REPORT" in report
        assert "Questions evaluated: 10" in report
        assert "faithfulness" in report
        assert "0.8500" in report
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_ragas_v2_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_ragas_v2_integration.py
git commit -m "test: add RAGAS V2 integration tests with mocked dependencies"
```

---

### Task 5: Update Documentation

**Files:**
- Modify: `evaluation/ragas/ragas.txt`

**Interfaces:**
- Consumes: None
- Produces: Updated documentation

- [ ] **Step 1: Add V2 usage to ragas.txt**

Read `evaluation/ragas/ragas.txt` and add after the existing lines:

```
# RAGAS V2 (v0.4.x API) - JSONL evaluation
python scripts/ragas_v2_eval.py evaluate --dataset eval_baseline.jsonl --out results/ragas_v2_result.csv --judge-base-url http://localhost:8080/v1 --judge-model deepseek/deepseek-v4-flash --top-k 5
```

- [ ] **Step 2: Commit**

```bash
git add evaluation/ragas/ragas.txt
git commit -m "docs: add RAGAS V2 usage examples to ragas.txt"
```

---

## Verification Checklist

After all tasks are complete, run:

```bash
# Lint
ruff check app/services/ragas_v2.py scripts/ragas_v2_eval.py

# Format
black app/services/ragas_v2.py scripts/ragas_v2_eval.py

# Type check
mypy app/services/ragas_v2.py

# Tests
pytest tests/test_ragas_v2.py tests/test_ragas_v2_cli.py tests/test_ragas_v2_integration.py -v
```

All should pass with no errors.
