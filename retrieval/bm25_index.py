"""
BM25 Index implementation with Chinese tokenization support.

This module provides BM25 (Best Matching 25) full-text search capabilities
with proper Chinese language support using jieba for tokenization.
"""

from typing import Any, Dict, List, Tuple

try:
    import jieba
    from rank_bm25 import BM25Okapi
except ImportError as e:
    raise ImportError(
        "Please install jieba and rank-bm25: pip install jieba rank-bm25"
    ) from e


class BM25IndexError(Exception):
    """Custom exception for BM25Index errors."""

    pass


class BM25Index:
    """
    BM25 索引，支持中文分词。

    BM25 (Best Matching 25) is a ranking function used in information retrieval
    that estimates the relevance of documents to a given search query.

    Attributes:
        documents: List of document dictionaries with id and text
        tokenized_docs: List of tokenized documents for BM25
        bm25: BM25Okapi instance for scoring
        doc_map: Mapping from BM25 index to document ID
    """

    def __init__(self, documents: List[Dict[str, Any]]):
        """
        构建 BM25 索引。

        Args:
            documents: List[Dict] - 每个文档包含 id, text
                Example: [{"id": "doc1", "text": "这是文档内容"}, ...]
        """
        if not documents:
            raise BM25IndexError("Documents list cannot be empty")

        self.documents = documents
        self.tokenized_docs: List[List[str]] = []
        self.bm25: BM25Okapi = None
        self.doc_map: Dict[int, str] = {}  # BM25 index -> doc_id

        self._build_index()

    def _tokenize_chinese(self, text: str) -> List[str]:
        """
        使用 jieba 进行中文分词。

        For Chinese text, uses jieba to segment into words.
        For English text, splits on whitespace.

        Args:
            text: Input text to tokenize

        Returns:
            List of tokens
        """
        if not text or not text.strip():
            return []

        text = text.strip().lower()

        # Use jieba for Chinese tokenization
        # jieba automatically handles mixed Chinese/English text
        tokens = list(jieba.lcut(text))

        # Filter out empty tokens and whitespace
        tokens = [t.strip() for t in tokens if t and t.strip()]

        return tokens

    def _build_index(self) -> None:
        """
        构建 BM25 索引。

        1. 使用 jieba 进行中文分词
        2. 构建 rank_bm25 索引
        """
        try:
            for idx, doc in enumerate(self.documents):
                text = doc.get("text", "")
                if not text:
                    continue

                tokens = self._tokenize_chinese(text)
                if tokens:
                    self.tokenized_docs.append(tokens)
                    self.doc_map[len(self.tokenized_docs) - 1] = doc.get("id", f"doc_{idx}")

            if not self.tokenized_docs:
                raise BM25IndexError("No valid documents to index")

            # Build BM25 index using Okapi variant
            self.bm25 = BM25Okapi(self.tokenized_docs)

        except Exception as e:
            raise BM25IndexError(f"Failed to build BM25 index: {str(e)}") from e

    def search(self, query: str, top_k: int = 20) -> List[Tuple[str, float]]:
        """
        搜索 BM25 索引。

        Args:
            query: 查询字符串
            top_k: 返回结果数量

        Returns:
            List[(doc_id, score)] - 按 BM25 分数降序排列
        """
        if not self.bm25:
            raise BM25IndexError("BM25 index not initialized")

        if not query or not query.strip():
            return []

        try:
            # Tokenize query using same method as documents
            query_tokens = self._tokenize_chinese(query)

            if not query_tokens:
                return []

            # Get BM25 scores for all documents
            scores = self.bm25.get_scores(query_tokens)

            # Get top_k indices
            top_indices = sorted(
                range(len(scores)),
                key=lambda i: scores[i],
                reverse=True
            )[:top_k]

            # Filter out zero scores and build results
            results: List[Tuple[str, float]] = []
            for idx in top_indices:
                if scores[idx] > 0 and idx in self.doc_map:
                    doc_id = self.doc_map[idx]
                    results.append((doc_id, float(scores[idx])))

            return results

        except Exception as e:
            raise BM25IndexError(f"Search failed: {str(e)}") from e

    def get_scores(self, query: str) -> Dict[str, float]:
        """
        获取所有文档的 BM25 分数。

        Args:
            query: 查询字符串

        Returns:
            Dict[doc_id, score] - 所有文档的分数
        """
        if not self.bm25:
            raise BM25IndexError("BM25 index not initialized")

        query_tokens = self._tokenize_chinese(query)
        scores = self.bm25.get_scores(query_tokens)

        return {
            self.doc_map[idx]: float(scores[idx])
            for idx in range(len(scores))
            if idx in self.doc_map
        }

    def get_document_count(self) -> int:
        """
        获取索引中的文档数量。

        Returns:
            int: 文档数量
        """
        return len(self.tokenized_docs)

    def refresh(self, documents: List[Dict[str, Any]]) -> None:
        """
        重新构建索引。

        Args:
            documents: 新的文档列表
        """
        self.documents = documents
        self.tokenized_docs = []
        self.doc_map = {}
        self.bm25 = None
        self._build_index()
