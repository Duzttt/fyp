"""
BM25 Index implementation with English tokenization.

This module provides BM25 (Best Matching 25) full-text search capabilities
with:

- Lightweight English tokenization (NFKC normalization + lowercase +
  alnum-run extraction).
- English stopword filtering (configurable).
- Multiple BM25 variants: Okapi (default), Plus, Lucene.
- Configurable k1 / b / delta parameters.
- Optional custom tokenizer injection.

Note on Python version: type hints keep Python 3.9 compatibility
(Optional[X], Union[X, Y] instead of X | None).
"""

import heapq
import re
import unicodedata
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

try:
    from rank_bm25 import BM25L, BM25Okapi, BM25Plus
except ImportError as e:
    raise ImportError("Please install rank-bm25: pip install rank-bm25") from e


class BM25Variant(str, Enum):
    """Supported BM25 scoring variants."""

    OKAPI = "okapi"
    PLUS = "plus"
    LUCENE = "lucene"


class BM25IndexError(Exception):
    """Custom exception for BM25Index errors."""

    pass


# --- Stopwords ---------------------------------------------------------

_EN_STOPWORDS = frozenset(
    """a an and are as at be been but by can could did do does for from had has
    have he her hers him his i if in into is it its me more most my
    of on or our ours out over she should so some such than that the their
    theirs them then there these they this those to too under until up very was
    we were what when where which while who whom why will with would you your
    yours""".split()
)

# Technical-term-aware token pattern. Alternatives are ordered so that
# symbol-bearing and compound terms win over plain alnum runs:
#   1. alnum + trailing punctuation suffixes  (c++, c#, a*)
#   2. dotted version numbers                 (3.10, python3.10)
#   3. underscore/hyphen compounds            (foo_bar, deep-learning)
#   4. plain alnum runs                       (oauth2, python)
_WORD_RE = re.compile(
    r"[a-z0-9]+[+#*]+"
    r"|[a-z0-9]+(?:\.[a-z0-9]+)+"
    r"|[a-z0-9]+(?:[_-][a-z0-9]+)+"
    r"|[a-z0-9]+"
)

# Minimum length for constituent tokens split out of compounds. Single
# characters (e.g. the "c" of "c++") are kept only as part of the full term
# to avoid low-value single-char noise in the index.
_MIN_CONSTITUENT_LEN = 2


class BM25Index:
    """
    BM25 index with English tokenization.

    Attributes:
        documents: List of document dictionaries with id and text
        tokenized_docs: List of tokenized documents for BM25
        bm25: rank_bm25 scoring instance
        doc_map: Mapping from BM25 index to document ID
    """

    def __init__(
        self,
        documents: List[Dict[str, Any]],
        variant: Union[str, BM25Variant] = BM25Variant.OKAPI,
        k1: float = 1.5,
        b: float = 0.75,
        delta: float = 0.5,
        use_stopwords: bool = True,
        tokenizer: Optional[Callable[[str], List[str]]] = None,
    ):
        """
        Build BM25 index.

        Args:
            documents: List[Dict] - Each document contains id, text
                Example: [{"id": "doc1", "text": "This is document content"}, ...]
            variant: BM25 scoring variant - "okapi" (default), "plus", or "lucene"
            k1: Term frequency saturation parameter (default 1.5)
            b: Document length normalization parameter, 0..1 (default 0.75)
            delta: Delta parameter for the "plus" variant (default 0.5)
            use_stopwords: Filter English stopwords (default True)
            tokenizer: Optional custom tokenizer callable taking text and
                returning a list of tokens. When provided, it fully replaces
                the built-in tokenization (including stopword filtering).
        """
        if not documents:
            raise BM25IndexError("Documents list cannot be empty")
        if k1 <= 0:
            raise BM25IndexError("k1 must be positive")
        if not 0 <= b <= 1:
            raise BM25IndexError("b must be between 0 and 1")
        if delta <= 0:
            raise BM25IndexError("delta must be positive")

        if isinstance(variant, str):
            try:
                variant = BM25Variant(variant.lower())
            except ValueError:
                raise BM25IndexError(
                    "Unsupported BM25 variant: {0}. Choose from {1}".format(
                        variant, [v.value for v in BM25Variant]
                    )
                )

        self.documents = documents
        self.variant = variant
        self.k1 = k1
        self.b = b
        self.delta = delta
        self.use_stopwords = use_stopwords
        self._custom_tokenizer = tokenizer
        self.tokenized_docs: List[List[str]] = []
        self.bm25: Optional[Union[BM25Okapi, BM25Plus, BM25L]] = None
        self.doc_map: Dict[int, str] = {}  # BM25 index -> doc_id

        self._build_index()

    # --- Tokenization -------------------------------------------------------

    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into a list of tokens.

        Uses the injected custom tokenizer when provided; otherwise applies
        the built-in English tokenizer (NFKC normalization, alnum-run
        extraction, optional stopword filtering).

        Args:
            text: Input text

        Returns:
            List of tokens
        """
        if self._custom_tokenizer is not None:
            return self._custom_tokenizer(text)
        return self._tokenize(text)

    def _tokenize(self, text: str) -> List[str]:
        """
        Built-in English tokenizer.

        - Normalizes full-width/compatibility characters to standard form
          (NFKC) and lowercases in one pass.
        - Extracts technical terms with a single regex scan: symbol-bearing
          terms (C++, C#, A*), underscore/hyphen compounds (foo_bar,
          deep-learning) and dotted version numbers (3.10) are kept whole.
        - Compound terms are expanded so both the full term and its
          constituent words are indexed (foo_bar -> foo_bar, foo, bar).
        - Negation words (no, nor, not) are preserved; optional English
          stopword filtering applies to the remaining tokens.
        """
        if not text or not text.strip():
            return []

        normalized = unicodedata.normalize("NFKC", text).lower()
        tokens = _WORD_RE.findall(normalized)

        # Expand compound terms: index both the full term and its constituents.
        expanded: List[str] = []
        for token in tokens:
            expanded.append(token)
            for part in re.findall(r"[a-z0-9]+", token):
                if (
                    len(part) >= _MIN_CONSTITUENT_LEN
                    and part != token
                    and any(ch.isalpha() for ch in part)
                ):
                    expanded.append(part)

        if self.use_stopwords:
            expanded = [t for t in expanded if t not in _EN_STOPWORDS]

        return expanded

    # --- Index construction -------------------------------------------------

    def _build_index(self) -> None:
        """
        Build BM25 index.

        1. Tokenize documents
        2. Build rank_bm25 index with the selected variant
        """
        try:
            for idx, doc in enumerate(self.documents):
                text = doc.get("text", "")
                if not text:
                    continue

                tokens = self.tokenize(text)
                if tokens:
                    self.tokenized_docs.append(tokens)
                    self.doc_map[len(self.tokenized_docs) - 1] = doc.get(
                        "id", f"doc_{idx}"
                    )

            if not self.tokenized_docs:
                raise BM25IndexError("No valid documents to index")

            if self.variant == BM25Variant.PLUS:
                self.bm25 = BM25Plus(
                    self.tokenized_docs, k1=self.k1, b=self.b, delta=self.delta
                )
            elif self.variant == BM25Variant.LUCENE:
                self.bm25 = BM25L(self.tokenized_docs, k1=self.k1, b=self.b)
            else:
                self.bm25 = BM25Okapi(self.tokenized_docs, k1=self.k1, b=self.b)

        except BM25IndexError:
            raise
        except Exception as e:
            raise BM25IndexError(f"Failed to build BM25 index: {str(e)}") from e

    # --- Search --------------------------------------------------------------

    def search(self, query: str, top_k: int = 20) -> List[Tuple[str, float]]:
        """
        Search BM25 index.

        Args:
            query: Query string
            top_k: Number of results to return

        Returns:
            List[(doc_id, score)] - Sorted by BM25 score in descending order
        """
        bm25 = self.bm25
        if bm25 is None:
            raise BM25IndexError("BM25 index not initialized")

        if not query or not query.strip():
            return []

        try:
            query_tokens = self.tokenize(query)
            if not query_tokens:
                return []

            scores = bm25.get_scores(query_tokens)

            # Keep only the top_k highest-scoring indices (heapq is O(n log k)).
            if len(scores) > top_k:
                top_indices = heapq.nlargest(
                    top_k, range(len(scores)), key=lambda i: scores[i]
                )
            else:
                top_indices = sorted(
                    range(len(scores)), key=lambda i: scores[i], reverse=True
                )

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
        Get BM25 scores for all documents.

        Args:
            query: Query string

        Returns:
            Dict[doc_id, score] - Scores for all documents
        """
        bm25 = self.bm25
        if bm25 is None:
            raise BM25IndexError("BM25 index not initialized")

        query_tokens = self.tokenize(query)
        scores = bm25.get_scores(query_tokens)

        return {
            self.doc_map[idx]: float(scores[idx])
            for idx in range(len(scores))
            if idx in self.doc_map
        }

    def get_document_count(self) -> int:
        """
        Get the number of documents in the index.

        Returns:
            int: Number of documents
        """
        return len(self.tokenized_docs)

    def refresh(self, documents: List[Dict[str, Any]]) -> None:
        """
        Rebuild the index with the same tokenization/scoring settings.

        Args:
            documents: New document list
        """
        self.documents = documents
        self.tokenized_docs = []
        self.doc_map = {}
        self.bm25 = None
        self._build_index()
