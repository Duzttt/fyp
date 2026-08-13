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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from app.config import settings

logger = logging.getLogger("ragas_v2")

METRIC_COLUMNS = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
]


class RAGASEvaluatorError(Exception):
    """Custom exception for RAGAS V2 evaluator errors."""


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
        from openai import OpenAI
        from ragas.llms import llm_factory

        client = OpenAI(
            base_url=judge_config["base_url"],
            api_key=judge_config["api_key"],
        )
        return llm_factory(judge_config["model"], provider="openai", client=client)

    def _build_ragas_embeddings(self):
        """Build RAGAS embeddings wrapping the existing EmbeddingService.

        The legacy evaluate() path uses BaseRagasEmbeddings which the legacy
        metrics call via embed_query()/embed_documents(). No langchain import;
        we implement a plain object exposing both interfaces.
        """
        from app.services.embedding import EmbeddingService
        from app.services.runtime_embedding import load_runtime_embedding_settings
        from ragas.embeddings.base import BaseRagasEmbeddings

        rt = load_runtime_embedding_settings()
        embedding_service = EmbeddingService(model_name=rt["model_id"])

        def _to_floats(emb: Any) -> List[float]:
            if hasattr(emb, "tolist"):
                emb = emb.tolist()
            return [float(v) for v in emb]

        class _LocalRagasEmbedding(BaseRagasEmbeddings):
            def embed_query(self, text: str) -> List[float]:
                return _to_floats(embedding_service.embed_query(text))

            def embed_documents(
                self, texts: List[str], batch_size: int = 32
            ) -> List[List[float]]:
                return [_to_floats(embedding_service.embed_query(t)) for t in texts]

            async def aembed_query(self, text: str) -> List[float]:
                return self.embed_query(text)

            async def aembed_documents(
                self, texts: List[str], batch_size: int = 32
            ) -> List[List[float]]:
                return self.embed_documents(texts, batch_size=batch_size)

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

        results: List[Dict[str, Any]] = []

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
        ragas_max_workers: int = 2,
    ) -> Dict[str, Any]:
        """Full evaluation: load JSONL -> run RAG -> score with RAGAS -> save CSV.

        Args:
            dataset_path: Path to JSONL file with {question, ground_truth} per line
            top_k: Number of chunks to retrieve
            ragas_timeout: Per-job RAGAS timeout in seconds
            ragas_max_workers: Maximum concurrent RAGAS metric jobs.
                NVIDIA NIM API is limited to ~40 requests/minute, so keep this
                low (default 2) to avoid rate-limit 429 responses.

        Returns:
            Dict with num_questions, scores, csv_path, detailed
        """
        import json

        questions: List[str] = []
        ground_truths: List[str] = []
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
            from ragas.dataset_schema import (
                EvaluationDataset,
                EvaluationResult,
                SingleTurnSample,
            )
            from ragas.metrics import (
                AnswerRelevancy,
                ContextPrecision,
                ContextRecall,
                Faithfulness,
            )
            from ragas.run_config import RunConfig
        except ImportError as exc:
            raise RAGASEvaluatorError(
                "RAGAS not installed. Run: pip install 'ragas>=0.4.0,<0.5.0' openai"
            ) from exc

        judge_config = self._resolve_judge_config()
        judge_llm = self._build_judge_llm(judge_config)
        ragas_embeddings = self._build_ragas_embeddings()

        samples: List[Any] = [
            SingleTurnSample(
                user_input=r["question"],
                retrieved_contexts=r["contexts"],
                response=r["answer"],
                reference=r["ground_truth"],
            )
            for r in valid
        ]
        dataset = EvaluationDataset(samples=samples)

        # NOTE: ragas 0.4.x top-level evaluate() only accepts legacy Metric
        # instances from ragas.metrics; the ragas.metrics.collections classes
        # use a separate score()/ascore() API and are rejected by evaluate().
        # llm/embeddings are passed to evaluate() which auto-fills metric-level
        # values when the metric was constructed without them.
        metrics: List[Any] = [
            Faithfulness(),
            AnswerRelevancy(),
            ContextPrecision(),
            ContextRecall(),
        ]

        logger.info("Running RAGAS v0.4.x evaluation...")
        run_config = RunConfig(
            timeout=ragas_timeout,
            max_workers=ragas_max_workers,
        )
        result = cast(
            EvaluationResult,
            ragas_evaluate(
                dataset=dataset,
                metrics=metrics,
                llm=judge_llm,
                embeddings=ragas_embeddings,
                run_config=run_config,
            ),
        )

        out_dir = Path("evaluation/ragas/results")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = str(out_dir / f"ragas_v2_eval_{timestamp}.csv")

        df = result.to_pandas()
        df.to_csv(csv_path, index=False, encoding="utf-8")

        scores: Dict[str, Any] = {}
        for col in METRIC_COLUMNS:
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
