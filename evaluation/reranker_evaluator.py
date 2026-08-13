"""
Reranker Evaluator for comparing cross-encoder reranking models.

Evaluates multiple reranker models on the same retrieval candidates and measures:
- Quality: Recall@k, Precision@k, MRR, NDCG@k
- Performance: latency (avg, p50, p95, p99), throughput
- Stability: score distribution, rank movement statistics

Supported reranker models:
- CrossEncoder (sentence-transformers): bge-reranker-v2-m3, bge-reranker-base, ms-marco-MiniLM-L6-v2
- JinaReranker (via jina-reranker or HTTP API)
- Qwen3Reranker (via llama.cpp GGUF or skipped if unavailable)
"""

import json
import logging
import math
import statistics
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("reranker_evaluator")


class RerankerError(Exception):
    """Custom exception for reranker evaluation errors."""


@dataclass
class RerankerModelInfo:
    """Metadata about a reranker model."""

    name: str
    model_id: str
    model_type: str  # "cross_encoder", "jina", "qwen3"
    parameters: Optional[str] = None  # e.g. "278M", "4B"
    description: str = ""


@dataclass
class RerankerLatencyStats:
    """Latency statistics for a single reranker run."""

    total_ms: float = 0.0
    per_query_ms: List[float] = field(default_factory=list)
    avg_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    qps: float = 0.0

    def compute(self, num_queries: int) -> None:
        if not self.per_query_ms:
            return
        self.avg_ms = statistics.mean(self.per_query_ms)
        sorted_lat = sorted(self.per_query_ms)
        n = len(sorted_lat)
        self.p50_ms = sorted_lat[int(math.ceil(0.50 * n)) - 1]
        self.p95_ms = sorted_lat[int(math.ceil(0.95 * n)) - 1]
        self.p99_ms = sorted_lat[int(math.ceil(0.99 * n)) - 1]
        self.qps = num_queries / (self.total_ms / 1000.0) if self.total_ms > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_ms": round(self.total_ms, 2),
            "avg_ms": round(self.avg_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "qps": round(self.qps, 2),
        }


@dataclass
class RankMovementStats:
    """Statistics on how the reranker moves documents up/down in rank."""

    moved_up: int = 0  # documents ranked higher after reranking
    moved_down: int = 0  # documents ranked lower after reranking
    unchanged: int = 0  # documents at same rank
    avg_positions_changed: float = 0.0  # average absolute rank change

    def to_dict(self) -> Dict[str, Any]:
        return {
            "moved_up": self.moved_up,
            "moved_down": self.moved_down,
            "unchanged": self.unchanged,
            "avg_positions_changed": round(self.avg_positions_changed, 2),
        }


@dataclass
class RerankerEvaluationResult:
    """Full evaluation result for a single reranker model."""

    model_info: RerankerModelInfo
    # Quality metrics (averaged across queries)
    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    precision_at_1: float = 0.0
    precision_at_3: float = 0.0
    precision_at_5: float = 0.0
    precision_at_10: float = 0.0
    mrr: float = 0.0
    ndcg_at_5: float = 0.0
    ndcg_at_10: float = 0.0
    # Performance
    latency: RerankerLatencyStats = field(default_factory=RerankerLatencyStats)
    # Rank movement
    rank_movement: RankMovementStats = field(default_factory=RankMovementStats)
    # Per-query detail
    per_query: List[Dict[str, Any]] = field(default_factory=list)
    # Baseline comparison (no-reranker)
    baseline_mrr: float = 0.0
    baseline_recall_at_5: float = 0.0
    mrr_delta: float = 0.0
    recall_delta: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model_info.name,
            "model_id": self.model_info.model_id,
            "model_type": self.model_info.model_type,
            "parameters": self.model_info.parameters,
            "quality": {
                "recall_at_1": round(self.recall_at_1, 4),
                "recall_at_3": round(self.recall_at_3, 4),
                "recall_at_5": round(self.recall_at_5, 4),
                "recall_at_10": round(self.recall_at_10, 4),
                "precision_at_1": round(self.precision_at_1, 4),
                "precision_at_3": round(self.precision_at_3, 4),
                "precision_at_5": round(self.precision_at_5, 4),
                "precision_at_10": round(self.precision_at_10, 4),
                "mrr": round(self.mrr, 4),
                "ndcg_at_5": round(self.ndcg_at_5, 4),
                "ndcg_at_10": round(self.ndcg_at_10, 4),
            },
            "latency": self.latency.to_dict(),
            "rank_movement": self.rank_movement.to_dict(),
            "baseline": {
                "mrr": round(self.baseline_mrr, 4),
                "recall_at_5": round(self.baseline_recall_at_5, 4),
            },
            "deltas": {
                "mrr": round(self.mrr_delta, 4),
                "recall_at_5": round(self.recall_delta, 4),
            },
        }


class BaseRerankerAdapter(ABC):
    """Abstract base for reranker model adapters."""

    def __init__(self, model_info: RerankerModelInfo) -> None:
        self.model_info = model_info

    @abstractmethod
    def load(self) -> None:
        """Load the model into memory."""

    @abstractmethod
    def rerank(
        self, query: str, candidates: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        """Rerank candidates for a query. Must set 'rerank_score' on each dict."""

    def unload(self) -> None:
        """Release model resources (optional)."""


class CrossEncoderAdapter(BaseRerankerAdapter):
    """Adapter for sentence-transformers CrossEncoder models."""

    def __init__(
        self,
        model_id: str,
        device: Optional[str] = None,
        trust_remote_code: bool = False,
        **kwargs: Any,
    ) -> None:
        info = RerankerModelInfo(
            name=model_id.split("/")[-1],
            model_id=model_id,
            model_type="cross_encoder",
            **kwargs,
        )
        super().__init__(info)
        self._model_id = model_id
        self._device = device
        self._trust_remote_code = trust_remote_code
        self._model: Any = None

    def _resolve_device(self) -> str:
        if self._device is not None and self._device != "auto":
            return self._device
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
            mps = getattr(torch.backends, "mps", None)
            if mps is not None and mps.is_available():
                return "mps"
        except Exception:  # noqa: BLE001
            pass
        return "cpu"

    def load(self) -> None:
        import torch

        from sentence_transformers import CrossEncoder

        device = self._resolve_device()
        self._model = CrossEncoder(
            self._model_id,
            device=device,
            trust_remote_code=self._trust_remote_code,
        )
        self._device_obj = torch.device(device)
        logger.info("Loaded CrossEncoder: %s on %s", self._model_id, device)

    def _predict_safe(self, pairs: List[tuple]) -> Any:
        """Call model forward directly, handling BFloat16→float32 for numpy."""
        import torch

        tokenizer = self._model.tokenizer
        features = tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(self._model.model.device)

        with torch.no_grad():
            outputs = self._model.model(**features, return_dict=True)
            logits = outputs.logits
            # Handle BFloat16 which numpy can't convert
            if logits.dtype == torch.bfloat16:
                logits = logits.float()
            scores = logits.cpu().numpy()
            if scores.ndim > 1 and scores.shape[1] == 1:
                scores = scores.flatten()
            return scores

    def rerank(
        self, query: str, candidates: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []
        pairs = [(query, c.get("text", "")) for c in candidates]
        scores = self._predict_safe(pairs)
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        candidates.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        return candidates[:top_k]


class JinaRerankerAdapter(BaseRerankerAdapter):
    """Adapter for Jina reranker models.

    Attempts to use the jina-reranker library, falling back to
    sentence-transformers CrossEncoder if the Jina library is unavailable.
    """

    def __init__(
        self,
        model_id: str = "jinaai/jina-reranker-v2-base-multilingual",
        device: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        info = RerankerModelInfo(
            name="jina-reranker-v2",
            model_id=model_id,
            model_type="jina",
            **kwargs,
        )
        super().__init__(info)
        self._model_id = model_id
        self._device = device
        self._model: Any = None
        self._use_cross_encoder_fallback = False

    def load(self) -> None:
        try:
            from jina import Reranker

            self._model = Reranker(model_name=self._model_id)
            logger.info("Loaded JinaReranker: %s", self._model_id)
        except ImportError:
            logger.warning(
                "jina-reranker not installed, falling back to CrossEncoder for %s",
                self._model_id,
            )
            self._use_cross_encoder_fallback = True
            self._fallback_adapter = CrossEncoderAdapter(
                self._model_id, self._device, trust_remote_code=True
            )
            self._fallback_adapter.load()
            self._model = self._fallback_adapter._model
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "JinaReranker load failed (%s), using CrossEncoder fallback", exc
            )
            self._use_cross_encoder_fallback = True
            self._fallback_adapter = CrossEncoderAdapter(
                self._model_id, self._device, trust_remote_code=True
            )
            self._fallback_adapter.load()
            self._model = self._fallback_adapter._model

    def rerank(
        self, query: str, candidates: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []
        if self._use_cross_encoder_fallback:
            pairs = [(query, c.get("text", "")) for c in candidates]
            scores = self._fallback_adapter._predict_safe(pairs)
        else:
            docs = [c.get("text", "") for c in candidates]
            results = self._model.rank(query=query, documents=docs, top_k=top_k)
            scores = [0.0] * len(candidates)
            for r in results:
                idx = r.get("index", -1)
                if 0 <= idx < len(candidates):
                    scores[idx] = r.get("relevance_score", r.get("score", 0.0))
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        candidates.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        return candidates[:top_k]


class Qwen3RerankerAdapter(BaseRerankerAdapter):
    """Adapter for Qwen3-Reranker-4B.

    Uses sentence-transformers CrossEncoder with the HuggingFace model ID.
    If the model is too large for the device, it logs a warning and can be
    skipped via the --skip-large flag.
    """

    def __init__(
        self,
        model_id: str = "Qwen/Qwen3-Reranker-0.6B",
        device: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        info = RerankerModelInfo(
            name="Qwen3-Reranker",
            model_id=model_id,
            model_type="qwen3",
            parameters=kwargs.pop("parameters", "0.6B"),
            **kwargs,
        )
        super().__init__(info)
        self._model_id = model_id
        self._device = device
        self._model: Any = None

    def _resolve_device(self) -> str:
        if self._device is not None and self._device != "auto":
            return self._device
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
            mps = getattr(torch.backends, "mps", None)
            if mps is not None and mps.is_available():
                return "mps"
        except Exception:  # noqa: BLE001
            pass
        return "cpu"

    def load(self) -> None:
        from sentence_transformers import CrossEncoder

        device = self._resolve_device()
        try:
            self._model = CrossEncoder(self._model_id, device=device)
            self._device_obj = __import__("torch").device(device)
            logger.info("Loaded Qwen3-Reranker: %s on %s", self._model_id, device)
        except Exception as exc:  # noqa: BLE001
            raise RerankerError(
                f"Failed to load Qwen3-Reranker ({self._model_id}): {exc}"
            ) from exc

    def _predict_safe(self, pairs: List[tuple]) -> Any:
        """Call model forward directly, handling padding token issues."""
        import torch

        tokenizer = self._model.tokenizer
        if getattr(tokenizer, "pad_token", None) is None:
            tokenizer.pad_token = tokenizer.eos_token
        features = tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(self._model.model.device)

        with torch.no_grad():
            outputs = self._model.model(**features, return_dict=True)
            logits = outputs.logits
            if logits.dtype == torch.bfloat16:
                logits = logits.float()
            scores = logits.cpu().numpy()
            if scores.ndim > 1 and scores.shape[1] == 1:
                scores = scores.flatten()
            return scores

    def rerank(
        self, query: str, candidates: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []
        pairs = [(query, c.get("text", "")) for c in candidates]
        scores = self._predict_safe(pairs)
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        candidates.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        return candidates[:top_k]


def get_default_rerankers(
    device: Optional[str] = None,
    skip_large: bool = False,
) -> List[BaseRerankerAdapter]:
    """Get the default set of reranker adapters to evaluate."""
    adapters: List[BaseRerankerAdapter] = [
        CrossEncoderAdapter(
            "cross-encoder/ms-marco-MiniLM-L6-v2",
            device=device,
            parameters="22.7M",
            description="Default cross-encoder, fast and lightweight",
        ),
        CrossEncoderAdapter(
            "BAAI/bge-reranker-base",
            device=device,
            parameters="278M",
            description="BGE reranker base, multilingual support",
        ),
        CrossEncoderAdapter(
            "BAAI/bge-reranker-v2-m3",
            device=device,
            parameters="568M",
            description="BGE reranker v2 M3, best multilingual performance",
        ),
        JinaRerankerAdapter(
            model_id="jina-ai/jina-reranker-v2-base-multilingual-f4",
            device=device,
            parameters="278M",
            description="Jina reranker v2, multilingual with fine-grained relevance",
        ),
    ]
    if not skip_large:
        adapters.append(
            Qwen3RerankerAdapter(
                model_id="Qwen/Qwen3-Reranker-0.6B",
                device=device,
                parameters="0.6B",
                description="Qwen3 reranker, instruction-aware (0.6B variant)",
            )
        )
    return adapters


def _compute_single_query_metrics(
    retrieved_ids: List[str], relevant_ids: set, top_k: int = 10
) -> Dict[str, float]:
    """Compute retrieval metrics for a single query."""
    total_relevant = len(relevant_ids)
    if total_relevant == 0:
        return {}

    relevances = [1 if doc_id in relevant_ids else 0 for doc_id in retrieved_ids]
    metrics: Dict[str, float] = {}

    for k in [1, 3, 5, 10]:
        k_rels = relevances[:k]
        k_relevant_count = sum(k_rels)
        metrics[f"recall_at_{k}"] = k_relevant_count / total_relevant
        metrics[f"precision_at_{k}"] = k_relevant_count / k if k > 0 else 0.0

    # Reciprocal Rank
    first_rel_rank = None
    for rank, rel in enumerate(relevances, start=1):
        if rel == 1:
            first_rel_rank = rank
            break
    metrics["reciprocal_rank"] = 1.0 / first_rel_rank if first_rel_rank else 0.0

    # NDCG@k
    for k in [5, 10]:
        metrics[f"ndcg_at_{k}"] = _compute_ndcg(relevances, total_relevant, k)

    return metrics


def _compute_ndcg(relevances: List[int], total_relevant: int, k: int) -> float:
    """Compute NDCG@k."""
    k_rels = relevances[:k]
    dcg = sum((2**r - 1) / math.log2(i + 1) for i, r in enumerate(k_rels, start=1))
    ideal = [1] * min(total_relevant, k) + [0] * max(0, k - total_relevant)
    idcg = sum((2**r - 1) / math.log2(i + 1) for i, r in enumerate(ideal, start=1))
    return dcg / idcg if idcg > 0 else 0.0


def _compute_rank_movement(
    before: List[Dict[str, Any]], after: List[Dict[str, Any]]
) -> RankMovementStats:
    """Compute how the reranker changed document positions."""
    stats = RankMovementStats()
    # Build position maps using chunk_index or id as key
    before_positions: Dict[Any, int] = {}
    for i, doc in enumerate(before):
        key = doc.get("chunk_index", doc.get("id", i))
        before_positions[key] = i

    total_change = 0
    count = 0
    for i, doc in enumerate(after):
        key = doc.get("chunk_index", doc.get("id", i))
        if key in before_positions:
            old_pos = before_positions[key]
            diff = old_pos - i  # positive = moved up
            if diff > 0:
                stats.moved_up += 1
            elif diff < 0:
                stats.moved_down += 1
            else:
                stats.unchanged += 1
            total_change += abs(diff)
            count += 1

    stats.avg_positions_changed = total_change / count if count > 0 else 0.0
    return stats


class RerankerEvaluator:
    """Evaluate multiple reranker models on the same retrieval candidates."""

    def __init__(
        self,
        benchmark_path: str,
        candidate_top_k: int = 30,
        eval_top_k: int = 10,
        device: Optional[str] = None,
        skip_large: bool = False,
    ) -> None:
        self.benchmark_path = benchmark_path
        self.candidate_top_k = candidate_top_k
        self.eval_top_k = eval_top_k
        self.device = device
        self.skip_large = skip_large
        self._queries: List[Dict[str, Any]] = []
        self._candidates_cache: Dict[str, List[Dict[str, Any]]] = {}

    def _load_benchmark(self) -> List[Dict[str, Any]]:
        queries: List[Dict[str, Any]] = []
        with open(self.benchmark_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    queries.append(json.loads(stripped))
        return queries

    def _get_candidates_for_query(self, query_text: str) -> List[Dict[str, Any]]:
        """Retrieve hybrid candidates (pre-rerank) for a query.

        Uses the production hybrid retrieval pipeline without reranking.
        """
        if query_text in self._candidates_cache:
            return list(self._candidates_cache[query_text])

        import os

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
        import django

        django.setup()

        from app.services.local_rag import retrieve_with_faiss

        results = retrieve_with_faiss(
            query=query_text,
            top_k=self.candidate_top_k,
            reranker_enabled=False,
        )
        # Convert to standard format
        candidates = []
        for r in results:
            candidates.append(
                {
                    "id": f"chunk_{r.get('chunk_index', '')}",
                    "chunk_index": r.get("chunk_index"),
                    "text": r.get("text", ""),
                    "source": r.get("source", "unknown"),
                    "page": r.get("page"),
                    "score": r.get("score", r.get("fusion_score", 0.0)),
                    "fusion_score": r.get("fusion_score", 0.0),
                    "bm25_score": r.get("bm25_score", 0.0),
                    "dense_score": r.get("dense_score", 0.0),
                    "cosine_similarity": r.get("cosine_similarity", 0.0),
                }
            )
        self._candidates_cache[query_text] = candidates
        return list(candidates)

    def _evaluate_baseline(self, queries: List[Dict[str, Any]]) -> Dict[str, float]:
        """Evaluate baseline (no reranker) on the same candidates."""
        all_metrics: List[Dict[str, float]] = []
        for q in queries:
            relevant = set(q.get("relevant_chunk_ids", q.get("expected_doc_ids", [])))
            if not relevant:
                continue
            candidates = self._get_candidates_for_query(q.get("query", ""))
            retrieved_ids = [c.get("id", "") for c in candidates[: self.eval_top_k]]
            metrics = _compute_single_query_metrics(retrieved_ids, relevant)
            if metrics:
                all_metrics.append(metrics)

        if not all_metrics:
            return {"mrr": 0.0, "recall_at_5": 0.0}

        return {
            "mrr": statistics.mean(m["reciprocal_rank"] for m in all_metrics),
            "recall_at_5": statistics.mean(
                m.get("recall_at_5", 0.0) for m in all_metrics
            ),
        }

    def evaluate_reranker(
        self,
        adapter: BaseRerankerAdapter,
        queries: List[Dict[str, Any]],
        baseline: Dict[str, float],
    ) -> RerankerEvaluationResult:
        """Evaluate a single reranker model."""
        logger.info("Loading reranker: %s", adapter.model_info.name)
        adapter.load()

        all_metrics: List[Dict[str, float]] = []
        rank_movements: List[RankMovementStats] = []
        latencies: List[float] = []
        per_query_results: List[Dict[str, Any]] = []

        total_start = time.perf_counter()

        for q in queries:
            query_text = q.get("query", "")
            query_id = q.get("id", "")
            relevant = set(q.get("relevant_chunk_ids", q.get("expected_doc_ids", [])))
            if not relevant:
                continue

            candidates = self._get_candidates_for_query(query_text)
            if not candidates:
                continue

            # Snapshot before reranking
            before_snapshot = [
                {"chunk_index": c.get("chunk_index"), "id": c.get("id")}
                for c in candidates
            ]

            # Rerank and time it
            q_start = time.perf_counter()
            reranked = adapter.rerank(query_text, candidates, self.eval_top_k)
            q_latency = (time.perf_counter() - q_start) * 1000.0
            latencies.append(q_latency)

            # Compute metrics
            retrieved_ids = [c.get("id", "") for c in reranked]
            metrics = _compute_single_query_metrics(retrieved_ids, relevant)
            if metrics:
                all_metrics.append(metrics)

            # Rank movement
            movement = _compute_rank_movement(before_snapshot, reranked)
            rank_movements.append(movement)

            per_query_results.append(
                {
                    "query_id": query_id,
                    "query": query_text,
                    "metrics": metrics,
                    "latency_ms": round(q_latency, 2),
                    "rank_movement": movement.to_dict(),
                    "num_candidates": len(candidates),
                    "reranked_ids": retrieved_ids[:5],
                    "relevant_ids": list(relevant),
                }
            )

        total_elapsed = (time.perf_counter() - total_start) * 1000.0

        # Aggregate
        n = len(all_metrics) if all_metrics else 1
        result = RerankerEvaluationResult(
            model_info=adapter.model_info,
            recall_at_1=(
                statistics.mean(m.get("recall_at_1", 0.0) for m in all_metrics)
                if all_metrics
                else 0.0
            ),
            recall_at_3=(
                statistics.mean(m.get("recall_at_3", 0.0) for m in all_metrics)
                if all_metrics
                else 0.0
            ),
            recall_at_5=(
                statistics.mean(m.get("recall_at_5", 0.0) for m in all_metrics)
                if all_metrics
                else 0.0
            ),
            recall_at_10=(
                statistics.mean(m.get("recall_at_10", 0.0) for m in all_metrics)
                if all_metrics
                else 0.0
            ),
            precision_at_1=(
                statistics.mean(m.get("precision_at_1", 0.0) for m in all_metrics)
                if all_metrics
                else 0.0
            ),
            precision_at_3=(
                statistics.mean(m.get("precision_at_3", 0.0) for m in all_metrics)
                if all_metrics
                else 0.0
            ),
            precision_at_5=(
                statistics.mean(m.get("precision_at_5", 0.0) for m in all_metrics)
                if all_metrics
                else 0.0
            ),
            precision_at_10=(
                statistics.mean(m.get("precision_at_10", 0.0) for m in all_metrics)
                if all_metrics
                else 0.0
            ),
            mrr=(
                statistics.mean(m.get("reciprocal_rank", 0.0) for m in all_metrics)
                if all_metrics
                else 0.0
            ),
            ndcg_at_5=(
                statistics.mean(m.get("ndcg_at_5", 0.0) for m in all_metrics)
                if all_metrics
                else 0.0
            ),
            ndcg_at_10=(
                statistics.mean(m.get("ndcg_at_10", 0.0) for m in all_metrics)
                if all_metrics
                else 0.0
            ),
            per_query=per_query_results,
            baseline_mrr=baseline.get("mrr", 0.0),
            baseline_recall_at_5=baseline.get("recall_at_5", 0.0),
        )
        result.mrr_delta = result.mrr - result.baseline_mrr
        result.recall_delta = result.recall_at_5 - result.baseline_recall_at_5

        # Latency stats
        result.latency.total_ms = total_elapsed
        result.latency.per_query_ms = latencies
        result.latency.compute(n)

        # Rank movement aggregate
        if rank_movements:
            result.rank_movement.moved_up = sum(r.moved_up for r in rank_movements)
            result.rank_movement.moved_down = sum(r.moved_down for r in rank_movements)
            result.rank_movement.unchanged = sum(r.unchanged for r in rank_movements)
            total_positions = sum(r.avg_positions_changed for r in rank_movements)
            result.rank_movement.avg_positions_changed = total_positions / len(
                rank_movements
            )

        adapter.unload()
        return result

    def run(
        self, adapters: Optional[List[BaseRerankerAdapter]] = None
    ) -> List[RerankerEvaluationResult]:
        """Run full evaluation across all reranker models."""
        self._queries = self._load_benchmark()
        logger.info("Loaded %d benchmark queries", len(self._queries))

        if adapters is None:
            adapters = get_default_rerankers(self.device, self.skip_large)

        # Baseline
        logger.info("Computing baseline (no reranker) ...")
        baseline = self._evaluate_baseline(self._queries)
        logger.info(
            "Baseline MRR=%.4f, Recall@5=%.4f", baseline["mrr"], baseline["recall_at_5"]
        )

        results: List[RerankerEvaluationResult] = []
        for adapter in adapters:
            try:
                result = self.evaluate_reranker(adapter, self._queries, baseline)
                results.append(result)
                logger.info(
                    "%s: MRR=%.4f (delta=%+.4f), Recall@5=%.4f, p95=%.1fms",
                    result.model_info.name,
                    result.mrr,
                    result.mrr_delta,
                    result.recall_at_5,
                    result.latency.p95_ms,
                )
            except RerankerError as exc:
                logger.error("Skipping %s: %s", adapter.model_info.name, exc)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Error evaluating %s: %s",
                    adapter.model_info.name,
                    exc,
                    exc_info=True,
                )

        return results


def generate_comparison_table(results: List[RerankerEvaluationResult]) -> str:
    """Generate a formatted comparison table."""
    if not results:
        return "No results to display."

    lines = [
        "=" * 100,
        "RERANKER MODEL COMPARISON",
        "=" * 100,
        "",
    ]

    # Header
    header = f"{'Metric':<20}"
    for r in results:
        header += f" | {r.model_info.name:>24}"
    lines.append(header)
    lines.append("-" * len(header))

    # Quality metrics
    mrr_row = f"{'MRR':<20}"
    for r in results:
        delta = f" ({r.mrr_delta:+.4f})" if r.baseline_mrr > 0 else ""
        mrr_row += f" | {r.mrr:>14.4f}{delta:>8}"
    lines.append(mrr_row)

    for metric, label in [
        ("recall_at_1", "Recall@1"),
        ("recall_at_3", "Recall@3"),
        ("recall_at_5", "Recall@5"),
        ("recall_at_10", "Recall@10"),
        ("precision_at_1", "Precision@1"),
        ("precision_at_3", "Precision@3"),
        ("precision_at_5", "Precision@5"),
        ("precision_at_10", "Precision@10"),
        ("ndcg_at_5", "NDCG@5"),
        ("ndcg_at_10", "NDCG@10"),
    ]:
        row = f"{label:<20}"
        for r in results:
            val = getattr(r, metric, 0.0)
            row += f" | {val:>24.4f}"
        lines.append(row)

    lines.append("-" * len(header))

    # Latency
    row = f"{'Avg Latency (ms)':<20}"
    for r in results:
        row += f" | {r.latency.avg_ms:>24.1f}"
    lines.append(row)

    row = f"{'P50 Latency (ms)':<20}"
    for r in results:
        row += f" | {r.latency.p50_ms:>24.1f}"
    lines.append(row)

    row = f"{'P95 Latency (ms)':<20}"
    for r in results:
        row += f" | {r.latency.p95_ms:>24.1f}"
    lines.append(row)

    row = f"{'P99 Latency (ms)':<20}"
    for r in results:
        row += f" | {r.latency.p99_ms:>24.1f}"
    lines.append(row)

    row = f"{'Throughput (QPS)':<20}"
    for r in results:
        row += f" | {r.latency.qps:>24.1f}"
    lines.append(row)

    lines.append("-" * len(header))

    # Rank movement
    row = f"{'Docs Moved Up':<20}"
    for r in results:
        row += f" | {r.rank_movement.moved_up:>24}"
    lines.append(row)

    row = f"{'Docs Moved Down':<20}"
    for r in results:
        row += f" | {r.rank_movement.moved_down:>24}"
    lines.append(row)

    row = f"{'Avg Pos Changed':<20}"
    for r in results:
        row += f" | {r.rank_movement.avg_positions_changed:>24.2f}"
    lines.append(row)

    lines.append("-" * len(header))

    # Baseline comparison
    row = f"{'Baseline MRR':<20}"
    for r in results:
        row += f" | {r.baseline_mrr:>24.4f}"
    lines.append(row)

    row = f"{'MRR Delta':<20}"
    for r in results:
        sign = "+" if r.mrr_delta >= 0 else ""
        row += f" | {sign}{r.mrr_delta:>23.4f}"
    lines.append(row)

    row = f"{'Recall@5 Delta':<20}"
    for r in results:
        sign = "+" if r.recall_delta >= 0 else ""
        row += f" | {sign}{r.recall_delta:>23.4f}"
    lines.append(row)

    lines.append("=" * 100)

    # Model info
    lines.append("")
    lines.append("MODEL DETAILS:")
    for r in results:
        lines.append(
            f"  {r.model_info.name}: {r.model_info.model_id} "
            f"({r.model_info.parameters or '?'}) - {r.model_info.description}"
        )

    # Best model
    if results:
        best_mrr = max(results, key=lambda x: x.mrr)
        best_latency = min(results, key=lambda x: x.latency.p95_ms)
        best_tradeoff = max(
            results,
            key=lambda x: x.mrr / (x.latency.p95_ms + 1.0),
        )
        lines.append("")
        lines.append(
            f"Best MRR:           {best_mrr.model_info.name} ({best_mrr.mrr:.4f})"
        )
        lines.append(
            f"Best Latency:       {best_latency.model_info.name} "
            f"({best_latency.latency.p95_ms:.1f}ms p95)"
        )
        lines.append(
            f"Best Quality/Speed:  {best_tradeoff.model_info.name} "
            f"(MRR={best_tradeoff.mrr:.4f}, p95={best_tradeoff.latency.p95_ms:.1f}ms)"
        )

    return "\n".join(lines)
