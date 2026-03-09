"""
Evaluation module for retrieval system performance measurement.

This module provides:
- RetrievalEvaluator: Comprehensive evaluation metrics (Recall@k, Precision@k, MRR, NDCG)
- PerformanceMonitor: Real-time performance tracking and monitoring
"""

from .performance_monitor import (
    ComponentTimer,
    LatencyTracker,
    PerformanceMetrics,
    PerformanceMonitor,
    PerformanceMonitorError,
    QueryRecord,
)
from .retrieval_evaluator import (
    AggregateMetrics,
    EvaluationResult,
    RetrievalEvaluator,
    RetrievalEvaluatorError,
)

__all__ = [
    "RetrievalEvaluator",
    "RetrievalEvaluatorError",
    "PerformanceMonitor",
    "PerformanceMonitorError",
    "AggregateMetrics",
    "EvaluationResult",
    "PerformanceMetrics",
    "QueryRecord",
    "LatencyTracker",
    "ComponentTimer",
]
