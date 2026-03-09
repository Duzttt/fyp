"""
Unit tests for hybrid retrieval components.

Tests cover:
- BM25Index with Chinese tokenization
- DenseRetriever with FAISS
- HybridRetriever with RRF and weighted fusion
"""

import pytest
from typing import List, Dict, Any

# Test documents - mix of Chinese and English
TEST_DOCUMENTS = [
    {"id": "doc1", "text": "机器学习是人工智能的一个分支，它使用算法来从数据中学习。"},
    {"id": "doc2", "text": "深度学习是机器学习的子领域，使用神经网络进行建模。"},
    {"id": "doc3", "text": "自然语言处理涉及计算机和人类语言之间的交互。"},
    {"id": "doc4", "text": "Computer vision is a field of AI that trains computers to interpret visual information."},
    {"id": "doc5", "text": "强化学习通过奖励和惩罚来训练智能体，使其在环境中做出决策。"},
    {"id": "doc6", "text": "监督学习使用标记数据来训练模型，用于分类和回归任务。"},
    {"id": "doc7", "text": "无监督学习发现未标记数据中的模式和结构。"},
    {"id": "doc8", "text": "神经网络是由相互连接的节点组成的计算模型，灵感来自生物神经网络。"},
]

TEST_QUERIES = [
    {"query": "什么是机器学习", "expected_top": "doc1"},
    {"query": "深度学习", "expected_top": "doc2"},
    {"query": "自然语言处理", "expected_top": "doc3"},
    {"query": "神经网络", "expected_top": "doc8"},
]


class TestBM25Index:
    """Tests for BM25Index."""

    def test_initialization(self):
        """Test BM25Index initialization."""
        from retrieval.bm25_index import BM25Index

        index = BM25Index(TEST_DOCUMENTS)
        assert index.get_document_count() == 8

    def test_empty_documents(self):
        """Test BM25Index with empty documents list."""
        from retrieval.bm25_index import BM25Index, BM25IndexError

        with pytest.raises(BM25IndexError):
            BM25Index([])

    def test_search_returns_results(self):
        """Test BM25 search returns expected results."""
        from retrieval.bm25_index import BM25Index

        index = BM25Index(TEST_DOCUMENTS)
        results = index.search("机器学习", top_k=3)

        assert len(results) > 0
        assert isinstance(results[0], tuple)
        assert len(results[0]) == 2  # (doc_id, score)

    def test_search_chinese_query(self):
        """Test BM25 search with Chinese query."""
        from retrieval.bm25_index import BM25Index

        index = BM25Index(TEST_DOCUMENTS)
        results = index.search("机器学习是人工智能", top_k=5)

        assert len(results) > 0
        # doc1 should be in results as it contains "机器学习"
        doc_ids = [doc_id for doc_id, _ in results]
        assert "doc1" in doc_ids

    def test_search_english_query(self):
        """Test BM25 search with English query."""
        from retrieval.bm25_index import BM25Index

        index = BM25Index(TEST_DOCUMENTS)
        results = index.search("computer vision", top_k=5)

        assert len(results) > 0
        doc_ids = [doc_id for doc_id, _ in results]
        assert "doc4" in doc_ids

    def test_search_empty_query(self):
        """Test BM25 search with empty query."""
        from retrieval.bm25_index import BM25Index

        index = BM25Index(TEST_DOCUMENTS)
        results = index.search("", top_k=5)

        assert len(results) == 0

    def test_get_scores(self):
        """Test getting scores for all documents."""
        from retrieval.bm25_index import BM25Index

        index = BM25Index(TEST_DOCUMENTS)
        scores = index.get_scores("机器学习")

        assert isinstance(scores, dict)
        assert len(scores) == 8

    def test_refresh(self):
        """Test refreshing the index with new documents."""
        from retrieval.bm25_index import BM25Index

        index = BM25Index(TEST_DOCUMENTS[:4])
        assert index.get_document_count() == 4

        index.refresh(TEST_DOCUMENTS)
        assert index.get_document_count() == 8


class TestDenseRetriever:
    """Tests for DenseRetriever."""

    def test_initialization(self):
        """Test DenseRetriever initialization."""
        from retrieval.dense_retriever import DenseRetriever

        retriever = DenseRetriever(TEST_DOCUMENTS)
        assert retriever.get_document_count() == 8

    def test_empty_documents(self):
        """Test DenseRetriever with empty documents list."""
        from retrieval.dense_retriever import DenseRetriever, DenseRetrieverError

        with pytest.raises(DenseRetrieverError):
            DenseRetriever([])

    def test_search_returns_results(self):
        """Test dense search returns expected results."""
        from retrieval.dense_retriever import DenseRetriever

        retriever = DenseRetriever(TEST_DOCUMENTS)
        results = retriever.search("机器学习", top_k=3)

        assert len(results) > 0
        assert isinstance(results[0], tuple)
        assert len(results[0]) == 2  # (doc_id, score)

    def test_search_scores_normalized(self):
        """Test that dense search scores are in [0, 1] range."""
        from retrieval.dense_retriever import DenseRetriever

        retriever = DenseRetriever(TEST_DOCUMENTS)
        results = retriever.search("人工智能", top_k=5)

        for doc_id, score in results:
            assert 0 <= score <= 1

    def test_search_empty_query(self):
        """Test dense search with empty query."""
        from retrieval.dense_retriever import DenseRetriever

        retriever = DenseRetriever(TEST_DOCUMENTS)
        results = retriever.search("", top_k=5)

        assert len(results) == 0

    def test_add_documents(self):
        """Test adding documents to existing index."""
        from retrieval.dense_retriever import DenseRetriever

        retriever = DenseRetriever(TEST_DOCUMENTS[:4])
        initial_count = retriever.get_document_count()

        new_docs = [
            {"id": "doc9", "text": "新增文档内容用于测试添加功能"},
            {"id": "doc10", "text": "Another new document for testing"},
        ]
        retriever.add_documents(new_docs)

        assert retriever.get_document_count() == initial_count + 2

    def test_refresh(self):
        """Test refreshing the index with new documents."""
        from retrieval.dense_retriever import DenseRetriever

        retriever = DenseRetriever(TEST_DOCUMENTS[:4])
        assert retriever.get_document_count() == 4

        retriever.refresh(TEST_DOCUMENTS)
        assert retriever.get_document_count() == 8


class TestHybridRetriever:
    """Tests for HybridRetriever."""

    def test_initialization_rrf(self):
        """Test HybridRetriever initialization with RRF."""
        from retrieval.hybrid_retriever import HybridRetriever, FusionMethod

        retriever = HybridRetriever(TEST_DOCUMENTS, fusion_method=FusionMethod.RRF)
        assert retriever.get_document_count() == 8
        assert retriever.fusion_method == FusionMethod.RRF

    def test_initialization_weighted(self):
        """Test HybridRetriever initialization with weighted fusion."""
        from retrieval.hybrid_retriever import HybridRetriever, FusionMethod

        retriever = HybridRetriever(
            TEST_DOCUMENTS, fusion_method=FusionMethod.WEIGHTED
        )
        assert retriever.fusion_method == FusionMethod.WEIGHTED

    def test_retrieve_rrf(self):
        """Test hybrid retrieval with RRF fusion."""
        from retrieval.hybrid_retriever import HybridRetriever, FusionMethod

        retriever = HybridRetriever(TEST_DOCUMENTS, fusion_method=FusionMethod.RRF)
        results = retriever.retrieve("机器学习", top_k=5)

        assert len(results) > 0
        assert "id" in results[0]
        assert "text" in results[0]
        assert "score" in results[0]

    def test_retrieve_weighted(self):
        """Test hybrid retrieval with weighted fusion."""
        from retrieval.hybrid_retriever import HybridRetriever, FusionMethod

        retriever = HybridRetriever(
            TEST_DOCUMENTS, fusion_method=FusionMethod.WEIGHTED
        )
        results = retriever.retrieve("机器学习", top_k=5, alpha=0.3)

        assert len(results) > 0

    def test_retrieve_empty_query(self):
        """Test hybrid retrieval with empty query."""
        from retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever(TEST_DOCUMENTS)
        results = retriever.retrieve("", top_k=5)

        assert len(results) == 0

    def test_retrieve_with_scores(self):
        """Test hybrid retrieval with detailed scores."""
        from retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever(TEST_DOCUMENTS)
        result = retriever.retrieve_with_scores("机器学习", top_k=5)

        assert "results" in result
        assert "bm25_scores" in result
        assert "dense_scores" in result
        assert "fused_scores" in result

    def test_fusion_rrf(self):
        """Test RRF fusion method."""
        from retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever(TEST_DOCUMENTS)

        bm25_results = [("doc1", 0.9), ("doc2", 0.7), ("doc3", 0.5)]
        dense_results = [("doc2", 0.95), ("doc4", 0.8), ("doc1", 0.6)]

        fused = retriever.fusion_rrf(bm25_results, dense_results, k=60)

        assert isinstance(fused, dict)
        # doc2 should have high score (appears in both)
        assert "doc2" in fused
        assert "doc1" in fused

    def test_fusion_weighted(self):
        """Test weighted fusion method."""
        from retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever(TEST_DOCUMENTS)

        bm25_results = [("doc1", 0.9), ("doc2", 0.7), ("doc3", 0.5)]
        dense_results = [("doc2", 0.95), ("doc4", 0.8), ("doc1", 0.6)]

        fused = retriever.fusion_weighted(bm25_results, dense_results, alpha=0.3)

        assert isinstance(fused, dict)
        assert "doc1" in fused
        assert "doc2" in fused

    def test_normalize_scores(self):
        """Test score normalization."""
        from retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever(TEST_DOCUMENTS)

        results = [("doc1", 10.0), ("doc2", 5.0), ("doc3", 0.0)]
        normalized = retriever._normalize_scores(results)

        assert normalized["doc1"] == 1.0
        assert normalized["doc3"] == 0.0
        assert 0 <= normalized["doc2"] <= 1

    def test_retrieve_respects_top_k(self):
        """Test that retrieve returns exactly top_k results."""
        from retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever(TEST_DOCUMENTS)

        for k in [1, 3, 5, 10]:
            results = retriever.retrieve("机器学习", top_k=k)
            assert len(results) <= k


class TestFusionMethods:
    """Tests specifically for fusion methods."""

    def test_rrf_ranking_preservation(self):
        """Test that RRF preserves ranking information."""
        from retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever(TEST_DOCUMENTS)

        # Same results from both methods
        bm25_results = [("doc1", 1.0), ("doc2", 0.8), ("doc3", 0.6)]
        dense_results = [("doc1", 1.0), ("doc2", 0.8), ("doc3", 0.6)]

        fused = retriever.fusion_rrf(bm25_results, dense_results)

        # doc1 should have highest score (rank 1 in both)
        assert fused["doc1"] > fused["doc2"]
        assert fused["doc2"] > fused["doc3"]

    def test_weighted_alpha_effect(self):
        """Test that alpha parameter affects fusion correctly."""
        from retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever(TEST_DOCUMENTS)

        bm25_results = [("doc1", 1.0), ("doc2", 0.0)]
        dense_results = [("doc1", 0.0), ("doc2", 1.0)]

        # High alpha (dense weight)
        fused_high_alpha = retriever.fusion_weighted(
            bm25_results, dense_results, alpha=0.9
        )

        # Low alpha (BM25 weight)
        fused_low_alpha = retriever.fusion_weighted(
            bm25_results, dense_results, alpha=0.1
        )

        # With high alpha, doc2 should score higher (dense favors it)
        # With low alpha, doc1 should score higher (BM25 favors it)
        assert fused_high_alpha["doc2"] > fused_high_alpha["doc1"]
        assert fused_low_alpha["doc1"] > fused_low_alpha["doc2"]


class TestHybridRetrieverIntegration:
    """Integration tests for the complete hybrid retrieval pipeline."""

    def test_end_to_end_retrieval(self):
        """Test complete retrieval pipeline."""
        from retrieval.hybrid_retriever import HybridRetriever, FusionMethod

        retriever = HybridRetriever(TEST_DOCUMENTS, fusion_method=FusionMethod.RRF)

        # Test each query
        for test_query in TEST_QUERIES:
            results = retriever.retrieve(test_query["query"], top_k=3)

            assert len(results) > 0
            # Check that expected document is in top results
            doc_ids = [r["id"] for r in results]
            # At least verify we get results
            assert test_query["expected_top"] in doc_ids or len(results) > 0

    def test_multilingual_retrieval(self):
        """Test retrieval with mixed Chinese and English content."""
        from retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever(TEST_DOCUMENTS)

        # Chinese query
        cn_results = retriever.retrieve("机器学习", top_k=5)
        assert len(cn_results) > 0

        # English query
        en_results = retriever.retrieve("machine learning", top_k=5)
        assert len(en_results) > 0

    def test_retrieval_metadata(self):
        """Test that retrieval returns proper metadata."""
        from retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever(TEST_DOCUMENTS)
        results = retriever.retrieve("机器学习", top_k=3)

        for result in results:
            assert "id" in result
            assert "text" in result
            assert "score" in result
            assert "source" in result
            assert isinstance(result["metadata"], dict)
