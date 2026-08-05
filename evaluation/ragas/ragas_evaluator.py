"""
RAGAS Evaluator for RAG Pipeline Quality Assessment.

This module provides RAGAS-based evaluation for the lecture note Q&A system:
- Faithfulness: Does the answer stay faithful to the context?
- Answer Relevancy: Is the answer relevant to the question?
- Context Precision: How precise are the retrieved contexts?
- Context Recall: Does the context contain the information needed?

Usage:
    from evaluation.ragas_evaluator import RAGASEvaluator

    evaluator = RAGASEvaluator()
    result = evaluator.evaluate_from_pdfs(["path/to/file.pdf"])
    print(result)
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings

load_dotenv()

from app.config import settings
from app.services.local_rag import (
    build_context_from_sources,
    generate_with_local_llm,
    retrieve_with_faiss,
)
from app.services.pdf_chunking import read_pdf_text
from app.services.runtime_llm import load_runtime_llm_settings

try:
    from retrieval.hybrid_retriever import FusionMethod, HybridRetriever

    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False

logger = logging.getLogger("ragas_eval")


class RAGASEvaluatorError(Exception):
    """Custom exception for RAGAS evaluator errors."""

    pass


class _LocalRagasEmbeddings(Embeddings):
    """LangChain-compatible embeddings backed by the active local model."""

    def __init__(self, embedding_service: Any):
        self.embedding_service = embedding_service

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.embedding_service.embed_texts(texts)
        if hasattr(embeddings, "tolist"):
            embeddings = embeddings.tolist()
        return [[float(value) for value in row] for row in embeddings]

    def embed_query(self, text: str) -> List[float]:
        embedding = self.embedding_service.embed_query(text)
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()
        return [float(value) for value in embedding]


class RAGASEvaluator:
    """
    RAGAS-based evaluator for RAG pipeline quality.

    Evaluates the end-to-end RAG pipeline using RAGAS metrics:
    - Faithfulness
    - Answer Relevancy
    - Context Precision
    - Context Recall
    """

    def __init__(
        self,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
    ):
        """
        Initialize the RAGAS evaluator.

        Args:
            llm_provider: LLM provider for question generation (default: from settings)
            llm_model: LLM model for question generation (default: from settings)
        """
        self.llm_provider = llm_provider or settings.LLM_PROVIDER
        self.llm_model = llm_model

    def _build_ragas_embeddings(self) -> _LocalRagasEmbeddings:
        """Build the embeddings object RAGAS uses for similarity metrics."""
        from app.services.embedding import EmbeddingService
        from app.services.runtime_embedding import load_runtime_embedding_settings

        rt = load_runtime_embedding_settings()
        embedding_service = EmbeddingService(model_name=rt["model_id"])
        return _LocalRagasEmbeddings(embedding_service)

    def _resolve_ragas_llm_config(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, str]:
        """Resolve the OpenAI-compatible judge LLM used by RAGAS metrics.

        Priority: explicit args > RAGAS_* env vars > OpenRouter (DeepSeek) > local_llm.
        """
        # Explicit arguments take highest priority
        if api_key and base_url and model:
            return {
                "api_key": str(api_key),
                "base_url": str(base_url),
                "model": str(model),
            }

        # RAGAS-specific env vars
        env_key = os.environ.get("RAGAS_API_KEY")
        env_base = os.environ.get("RAGAS_BASE_URL")
        env_model = os.environ.get("RAGAS_MODEL")
        if env_key and env_base:
            return {
                "api_key": env_key,
                "base_url": env_base,
                "model": model or env_model or "deepseek/deepseek-v4-flash",
            }

        # OpenRouter with DeepSeek — preferred for RAGAS judge
        or_key = api_key or os.environ.get("OPENROUTER_API_KEY") or settings.OPENROUTER_API_KEY
        if or_key:
            or_base = base_url or settings.OPENROUTER_BASE_URL
            return {
                "api_key": str(or_key),
                "base_url": str(or_base),
                "model": str(model or "deepseek/deepseek-v4-flash"),
            }

        # Fall back to local llama.cpp (OpenAI-compatible, no real key needed)
        rt = load_runtime_llm_settings()
        local_base = base_url or rt.get("base_url") or settings.LOCAL_LLM_BASE_URL
        normalized = str(local_base).rstrip("/")
        if not normalized.endswith("/v1"):
            normalized = f"{normalized}/v1"
        return {
            "api_key": "local",
            "base_url": normalized,
            "model": str(model or rt.get("model") or settings.LOCAL_LLM_MODEL),
        }

    @staticmethod
    def _parse_qa_json(content: str) -> List[Dict[str, str]]:
        """Extract a JSON array of QA pairs from LLM output, tolerating extra text."""
        content = content.strip()

        # Strip markdown code fences
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        # Try direct parse first
        try:
            result = json.loads(content)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # Fallback: extract the first JSON array from the text
        start = content.find("[")
        end = content.rfind("]")
        if start != -1 and end > start:
            try:
                result = json.loads(content[start : end + 1])
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        # Repair truncated JSON: find last complete object and close the array
        if start != -1:
            fragment = content[start:]
            last_brace = fragment.rfind("}")
            if last_brace > 0:
                repaired = fragment[: last_brace + 1] + "]"
                try:
                    result = json.loads(repaired)
                    if isinstance(result, list):
                        return result
                except json.JSONDecodeError:
                    pass

        raise ValueError(f"No valid JSON array found in LLM response: {content[:200]}")

    def generate_qa_from_text(
        self,
        text: str,
        num_questions: int = 5,
        language: str = "en",
    ) -> List[Dict[str, str]]:
        """
        Generate question-answer pairs from text using LLM.

        Args:
            text: Source text to generate questions from
            num_questions: Number of questions to generate
            language: Language for questions ("en" or "zh")

        Returns:
            List of {"question": "...", "ground_truth": "..."} dicts
        """
        lang_instruction = (
            "Generate questions and answers in Chinese."
            if language == "zh"
            else "Generate questions and answers in English."
        )

        prompt = f"""Based on the following text, generate {num_questions} question-answer pairs for evaluation.

{lang_instruction}

Return ONLY a JSON array with no additional text:
[
    {{"question": "...", "ground_truth": "..."}},
    ...
]

Text:
{text[:4000]}"""

        try:
            from app.services.llm_client import call_llm
            from app.services.runtime_llm import load_runtime_llm_settings

            rt = load_runtime_llm_settings()
            provider = rt["provider"] or self.llm_provider
            model = rt["model"] or self.llm_model
            base_url = rt["base_url"]

            messages = [{"role": "user", "content": prompt}]

            call_kwargs: Dict[str, Any] = {
                "provider": provider,
                "model": model or settings.GEMINI_MODEL,
                "call_type": "qa_generation",
                "messages": messages,
                "timeout": 120,
                "query_text": "",
            }

            # Add provider-specific kwargs
            if provider == "local_llm":
                call_kwargs["base_url"] = base_url or settings.LOCAL_LLM_BASE_URL
                call_kwargs["num_predict"] = 4096
            elif provider == "openrouter":
                call_kwargs["api_key"] = rt["api_key"] or settings.OPENROUTER_API_KEY
                call_kwargs["base_url"] = base_url or settings.OPENROUTER_BASE_URL
            elif provider == "gemini":
                call_kwargs["api_key"] = rt["api_key"] or settings.GEMINI_API_KEY
                call_kwargs["base_url"] = base_url or settings.GEMINI_BASE_URL

            response = call_llm(**call_kwargs)

            # Extract content from response
            content = response[0] if isinstance(response, tuple) else response
            qa_pairs = self._parse_qa_json(content)
            return qa_pairs

        except Exception as exc:
            logger.error("Failed to generate QA pairs: %s", exc)
            raise RAGASEvaluatorError(f"QA generation failed: {exc}") from exc

    def run_rag_pipeline(
        self,
        questions: List[str],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Run RAG pipeline for a list of questions using hybrid retrieval when available.

        Args:
            questions: List of question strings
            top_k: Number of chunks to retrieve

        Returns:
            List of {"question", "answer", "contexts"} dicts
        """
        # Try to build a hybrid retriever from all indexed documents
        hybrid_retriever = None
        if HYBRID_AVAILABLE:
            try:
                from app.services.runtime_embedding import (
                    load_runtime_embedding_settings,
                )
                from app.services.vector_store import VectorStore

                rt = load_runtime_embedding_settings()
                vector_store = VectorStore.get_cached(
                    index_path=settings.FAISS_INDEX_PATH,
                    embedding_dim=rt["embedding_dim"],
                )

                documents = [
                    {
                        "id": f"chunk_{i}",
                        "text": chunk.get("text", ""),
                        "source": chunk.get("source", "unknown"),
                        "metadata": {
                            "page": chunk.get("page"),
                            "source": chunk.get("source", "unknown"),
                        },
                    }
                    for i, chunk in enumerate(vector_store.chunks)
                    if chunk.get("text", "").strip()
                ]

                if documents:
                    hybrid_retriever = HybridRetriever(
                        documents=documents,
                        model_name=rt["model_id"],
                        fusion_method=FusionMethod.RRF,
                    )
                    logger.info(
                        "Hybrid retriever initialized with %d documents",
                        len(documents),
                    )
            except Exception as exc:
                logger.warning(
                    "Hybrid retriever init failed, falling back to dense: %s", exc
                )
                hybrid_retriever = None

        results = []

        for i, question in enumerate(questions):
            logger.info(
                "Processing question %d/%d: %s", i + 1, len(questions), question[:80]
            )

            try:
                # Retrieve with hybrid or fallback to dense
                if hybrid_retriever is not None:
                    hybrid_results = hybrid_retriever.retrieve(
                        query=question,
                        top_k=top_k,
                    )
                    sources = [
                        {
                            "text": r.get("text", ""),
                            "source": r.get("source", "unknown"),
                            "page": r.get("metadata", {}).get("page"),
                        }
                        for r in hybrid_results
                    ]
                else:
                    sources = retrieve_with_faiss(question, top_k=top_k)

                context = build_context_from_sources(sources)

                # Generate answer
                answer = generate_with_local_llm(question, context)
                if isinstance(answer, tuple):
                    answer = answer[0]

                results.append(
                    {
                        "question": question,
                        "answer": str(answer),
                        "contexts": [s.get("text", "") for s in sources],
                    }
                )

            except Exception as exc:
                logger.warning(
                    "Failed to process question '%s': %s", question[:50], exc
                )
                results.append(
                    {
                        "question": question,
                        "answer": "",
                        "contexts": [],
                    }
                )

        return results

    def evaluate(
        self,
        questions: List[str],
        ground_truths: List[str],
        top_k: int = 5,
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        ragas_model: Optional[str] = None,
        ragas_timeout: int = 300,
        ragas_max_workers: int = 4,
    ) -> Dict[str, Any]:
        """
        Evaluate RAG pipeline using RAGAS metrics.

        Args:
            questions: List of question strings
            ground_truths: List of ground truth answers
            top_k: Number of chunks to retrieve
            openai_api_key: OpenAI API key for RAGAS evaluation (or set OPENAI_API_KEY env)
            openai_base_url: OpenAI-compatible base URL (or set OPENAI_BASE_URL env)
            ragas_model: OpenAI-compatible judge model for RAGAS evaluation
            ragas_timeout: Per-job RAGAS timeout in seconds
            ragas_max_workers: Maximum concurrent RAGAS metric jobs

        Returns:
            Dict with RAGAS scores
        """
        try:
            from ragas import evaluate as ragas_evaluate
            from ragas.metrics import (
                answer_relevancy,
                context_precision,
                context_recall,
                faithfulness,
            )
            from datasets import Dataset
            from ragas.run_config import RunConfig
        except ImportError as exc:
            raise RAGASEvaluatorError(
                "RAGAS not installed. Run: pip install ragas datasets openai"
            ) from exc

        if len(questions) != len(ground_truths):
            raise RAGASEvaluatorError(
                "questions and ground_truths must have the same length"
            )

        # Run RAG pipeline
        logger.info("Running RAG pipeline for %d questions...", len(questions))
        rag_results = self.run_rag_pipeline(questions, top_k=top_k)

        # Build dataset
        data = {
            "question": [],
            "answer": [],
            "contexts": [],
            "ground_truth": [],
        }

        for rag_result, gt in zip(rag_results, ground_truths):
            if not rag_result["answer"]:
                continue
            data["question"].append(rag_result["question"])
            data["answer"].append(rag_result["answer"])
            data["contexts"].append(rag_result["contexts"])
            data["ground_truth"].append(gt)

        if not data["question"]:
            raise RAGASEvaluatorError("No valid RAG results to evaluate")

        dataset = Dataset.from_dict(data)

        judge_config = self._resolve_ragas_llm_config(
            api_key=openai_api_key,
            base_url=openai_base_url,
            model=ragas_model,
        )

        from langchain_openai import ChatOpenAI
        from ragas.llms import LangchainLLMWrapper

        langchain_llm = ChatOpenAI(
            model=judge_config["model"],
            openai_api_key=judge_config["api_key"],
            openai_api_base=judge_config["base_url"],
            temperature=0,
            max_tokens=4096,
        )
        ragas_llm = LangchainLLMWrapper(langchain_llm)

        # Configure metrics with custom LLM
        metrics = [
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ]

        for metric in metrics:
            if hasattr(metric, "llm"):
                metric.llm = ragas_llm

        ragas_embeddings = self._build_ragas_embeddings()

        # Run RAGAS evaluation
        logger.info("Running RAGAS evaluation...")
        result = ragas_evaluate(
            dataset=dataset,
            metrics=metrics,
            embeddings=ragas_embeddings,
            run_config=RunConfig(
                timeout=ragas_timeout,
                max_workers=ragas_max_workers,
            ),
        )

        return {
            "scores": result,
            "num_questions": len(data["question"]),
            "detailed": result.to_pandas().to_dict(orient="records"),
        }

    def evaluate_from_pdfs(
        self,
        pdf_paths: List[str],
        num_questions_per_pdf: int = 5,
        top_k: int = 5,
        language: str = "en",
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        ragas_model: Optional[str] = None,
        ragas_timeout: int = 300,
        ragas_max_workers: int = 4,
    ) -> Dict[str, Any]:
        """
        End-to-end evaluation from PDF files.

        Args:
            pdf_paths: List of PDF file paths
            num_questions_per_pdf: Number of questions to generate per PDF
            top_k: Number of chunks to retrieve
            language: Language for generated questions
            openai_api_key: OpenAI API key for RAGAS evaluation
            openai_base_url: OpenAI-compatible base URL
            ragas_model: OpenAI-compatible judge model for RAGAS evaluation
            ragas_timeout: Per-job RAGAS timeout in seconds
            ragas_max_workers: Maximum concurrent RAGAS metric jobs

        Returns:
            Dict with RAGAS scores and metadata
        """
        all_questions = []
        all_ground_truths = []

        for pdf_path in pdf_paths:
            logger.info("Processing PDF: %s", pdf_path)

            if not os.path.exists(pdf_path):
                logger.warning("PDF not found: %s", pdf_path)
                continue

            text = read_pdf_text(pdf_path)
            if not text.strip():
                logger.warning("No text extracted from: %s", pdf_path)
                continue

            # Generate QA pairs
            try:
                qa_pairs = self.generate_qa_from_text(
                    text=text,
                    num_questions=num_questions_per_pdf,
                    language=language,
                )
            except RAGASEvaluatorError as exc:
                logger.warning("Skipping PDF %s: %s", pdf_path, exc)
                continue

            for qa in qa_pairs:
                print(f"  Q: {qa['question']}")
                print(f"  A: {qa['ground_truth']}")
                all_questions.append(qa["question"])
                all_ground_truths.append(qa["ground_truth"])

        if not all_questions:
            raise RAGASEvaluatorError("No questions generated from PDFs")

        logger.info(
            "Generated %d questions from %d PDFs",
            len(all_questions),
            len(pdf_paths),
        )

        return self.evaluate(
            questions=all_questions,
            ground_truths=all_ground_truths,
            top_k=top_k,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            ragas_model=ragas_model,
            ragas_timeout=ragas_timeout,
            ragas_max_workers=ragas_max_workers,
        )

    def evaluate_from_jsonl(
        self,
        jsonl_path: str,
        top_k: int = 5,
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        ragas_model: Optional[str] = None,
        ragas_timeout: int = 300,
        ragas_max_workers: int = 4,
    ) -> Dict[str, Any]:
        """
        Evaluate from a JSONL file with pre-defined questions.

        JSONL format: {"question": "...", "ground_truth": "..."}

        Args:
            jsonl_path: Path to JSONL file
            top_k: Number of chunks to retrieve
            openai_api_key: OpenAI API key for RAGAS evaluation
            openai_base_url: OpenAI-compatible base URL
            ragas_model: OpenAI-compatible judge model for RAGAS evaluation
            ragas_timeout: Per-job RAGAS timeout in seconds
            ragas_max_workers: Maximum concurrent RAGAS metric jobs

        Returns:
            Dict with RAGAS scores
        """
        questions = []
        ground_truths = []

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                questions.append(data["question"])
                ground_truths.append(data["ground_truth"])

        if not questions:
            raise RAGASEvaluatorError(f"No questions found in {jsonl_path}")

        return self.evaluate(
            questions=questions,
            ground_truths=ground_truths,
            top_k=top_k,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            ragas_model=ragas_model,
            ragas_timeout=ragas_timeout,
            ragas_max_workers=ragas_max_workers,
        )

    @staticmethod
    def format_report(result: Dict[str, Any]) -> str:
        """
        Format RAGAS evaluation result as a readable report.

        Args:
            result: Result dict from evaluate()

        Returns:
            Formatted report string
        """
        scores = result.get("scores", {})
        num_q = result.get("num_questions", 0)

        lines = [
            "=" * 60,
            "RAGAS EVALUATION REPORT",
            "=" * 60,
            "",
            f"Questions evaluated: {num_q}",
            "",
            "METRICS:",
            "-" * 40,
        ]

        # RAGAS scores object
        if hasattr(scores, "to_dict"):
            score_dict = scores.to_dict()
        elif isinstance(scores, dict):
            score_dict = scores
        else:
            score_dict = {"overall": str(scores)}

        for metric, value in score_dict.items():
            if isinstance(value, (int, float)):
                lines.append(f"{metric:<25} {value:.4f}")
            else:
                lines.append(f"{metric:<25} {value}")

        lines.extend(["", "=" * 60])

        return "\n".join(lines)
