"""
Retrieval module for hybrid search combining BM25 and dense vector retrieval.

This module provides:
- BM25Index: Keyword-based retrieval with Chinese tokenization support
- DenseRetriever: Vector-based semantic search using FAISS
- HybridRetriever: Combined retrieval using RRF or weighted fusion
"""

from .bm25_index import BM25Index, BM25IndexError
from .dense_retriever import DenseRetriever, DenseRetrieverError
from .hybrid_retriever import (
    FusionMethod,
    HybridRetriever,
    HybridRetrieverError,
)

__all__ = [
    "BM25Index",
    "BM25IndexError",
    "DenseRetriever",
    "DenseRetrieverError",
    "HybridRetriever",
    "HybridRetrieverError",
    "FusionMethod",
]
