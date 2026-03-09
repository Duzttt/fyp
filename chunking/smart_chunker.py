"""
Smart Chunker implementation with semantic boundaries and overlap.

This module provides intelligent document chunking that:
- Respects paragraph and sentence boundaries
- Merges small paragraphs and splits large ones
- Adds overlap between chunks to preserve context
- Extracts and preserves metadata including headings
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import jieba
    import jieba.analyse
except ImportError:
    raise ImportError("Please install jieba: pip install jieba")


class SmartChunkerError(Exception):
    """Custom exception for SmartChunker errors."""

    pass


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""

    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    position: int = 0  # Chunk position in document (0-indexed)
    total_chunks: int = 1
    start_char: int = 0  # Start character position in original text
    end_char: int = 0  # End character position in original text
    headings: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary."""
        return {
            "text": self.text,
            "metadata": self.metadata,
            "position": self.position,
            "total_chunks": self.total_chunks,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "headings": self.headings,
            "keywords": self.keywords,
        }


class SmartChunker:
    """
    智能文档分块器。

    Implements intelligent document chunking with:
    - Paragraph-aware splitting
    - Sentence boundary detection for Chinese and English
    - Adaptive chunk sizing (merge small, split large)
    - Overlap to preserve context across chunk boundaries
    - Metadata extraction (headings, keywords, positions)

    Attributes:
        chunk_size: Target chunk size in characters
        overlap: Overlap size in characters
        min_paragraph_size: Minimum paragraph size before merging
        max_paragraph_size: Maximum paragraph size before splitting
    """

    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 100,
        min_paragraph_size: int = 100,
        max_paragraph_size: int = 800,
    ):
        """
        初始化智能分块器。

        Args:
            chunk_size: 目标块大小（字符数）
            overlap: 重叠部分大小（字符数）
            min_paragraph_size: 最小段落大小，小于此值会与下一段合并
            max_paragraph_size: 最大段落大小，超过此值会按句子分割
        """
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        if min_paragraph_size <= 0:
            raise ValueError("min_paragraph_size must be positive")
        if max_paragraph_size <= min_paragraph_size:
            raise ValueError("max_paragraph_size must be greater than min_paragraph_size")

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_paragraph_size = min_paragraph_size
        self.max_paragraph_size = max_paragraph_size

        # Sentence ending patterns for Chinese and English
        self._chinese_sentence_endings = "。！？；!?；"
        self._english_sentence_endings = ".!?;:。！？；"
        self._sentence_pattern = re.compile(
            rf"(?<=[{re.escape(self._english_sentence_endings)}])\s*"
        )

    def chunk_document(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        extract_keywords: bool = True,
        top_k_keywords: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        将文档分割成智能块。

        Args:
            text: 文档全文
            metadata: 文档元数据（标题、来源等）
            extract_keywords: 是否提取关键词
            top_k_keywords: 提取的关键词数量

        Returns:
            List[Dict] - 每个块包含 text, metadata, position, headings, keywords
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        metadata = metadata or {}

        # 1. 按段落分割
        paragraphs = self._split_paragraphs(text)

        # 2. 合并小段落，分割大段落
        chunks = self._merge_and_split(paragraphs)

        # 3. 添加重叠
        chunks = self._add_overlap(chunks)

        # 4. 提取标题
        headings_map = self._extract_headings(text)

        # 5. 添加元数据
        result = []
        for idx, chunk_text in enumerate(chunks):
            chunk_start = text.find(chunk_text[:50]) if len(chunk_text) >= 50 else text.find(chunk_text)
            if chunk_start == -1:
                chunk_start = idx * (self.chunk_size - self.overlap)

            chunk_end = chunk_start + len(chunk_text)

            # Find applicable headings based on position
            chunk_headings = []
            for heading, start_pos in headings_map.items():
                if start_pos <= chunk_end:
                    chunk_headings.append(heading)

            # Extract keywords for this chunk
            chunk_keywords = []
            if extract_keywords:
                chunk_keywords = self._extract_keywords(chunk_text, top_k_keywords)

            chunk_dict = {
                "text": chunk_text,
                "metadata": metadata.copy(),
                "position": idx,
                "total_chunks": len(chunks),
                "start_char": chunk_start,
                "end_char": chunk_end,
                "headings": chunk_headings[:3],  # Limit to 3 headings
                "keywords": chunk_keywords,
            }
            result.append(chunk_dict)

        return result

    def _split_paragraphs(self, text: str) -> List[str]:
        """
        按段落分割（支持中英文）。

        识别：\n\n, \r\n\r\n, \n 等段落分隔符

        Args:
            text: 输入文本

        Returns:
            List[str]: 段落列表
        """
        # Split on common paragraph separators
        # Handle both Windows (\r\n) and Unix (\n) line endings
        paragraphs = re.split(r"\n\s*\n|\r\n\s*\r\n", text)

        # Clean up paragraphs
        cleaned = []
        for para in paragraphs:
            para = para.strip()
            if para:
                # Replace single newlines with spaces within paragraph
                para = re.sub(r"\s+", " ", para)
                cleaned.append(para)

        return cleaned

    def _merge_and_split(self, paragraphs: List[str]) -> List[str]:
        """
        智能合并/分割段落。

        规则：
        - 短段落（<min_paragraph_size 字）与下一个合并
        - 长段落（>max_paragraph_size 字）按句子分割
        - 尽量在句子边界切分

        Args:
            paragraphs: 段落列表

        Returns:
            List[str]: 处理后的块列表
        """
        if not paragraphs:
            return []

        chunks: List[str] = []
        current_chunk = ""

        for para in paragraphs:
            # If current chunk is empty, start with this paragraph
            if not current_chunk:
                current_chunk = para
                continue

            # If paragraph is short, merge with next
            if len(para) < self.min_paragraph_size:
                # Check if merging would exceed max size
                if len(current_chunk) + len(para) + 1 <= self.max_paragraph_size:
                    current_chunk += " " + para
                else:
                    # Current chunk is full, add it and start new one
                    chunks.extend(self._split_if_needed(current_chunk))
                    current_chunk = para
            else:
                # Paragraph is long enough to stand alone
                # First, save current chunk if it exists
                if current_chunk:
                    chunks.extend(self._split_if_needed(current_chunk))
                current_chunk = para

        # Don't forget the last chunk
        if current_chunk:
            chunks.extend(self._split_if_needed(current_chunk))

        return chunks

    def _split_if_needed(self, text: str) -> List[str]:
        """
        如果文本太长，按句子分割。

        Args:
            text: 输入文本

        Returns:
            List[str]: 分割后的块列表
        """
        if len(text) <= self.chunk_size:
            return [text]

        # Split by sentences
        sentences = self._split_by_sentences(text)

        if len(sentences) <= 1:
            # Can't split further, just return as is
            return [text]

        chunks: List[str] = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if adding this sentence would exceed chunk size
            if len(current_chunk) + len(sentence) + 1 <= self.chunk_size:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                # Current chunk is full
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # Start new chunk with current sentence
                current_chunk = sentence

        # Add remaining chunk
        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """
        添加重叠内容。

        每个块的开始包含上一个块末尾的 overlap 内容
        避免在切分点丢失上下文

        Args:
            chunks: 块列表

        Returns:
            List[str]: 添加重叠后的块列表
        """
        if len(chunks) <= 1 or self.overlap <= 0:
            return chunks

        result: List[str] = [chunks[0]]

        for i in range(1, len(chunks)):
            prev_chunk = result[-1]
            current_chunk = chunks[i]

            # Get overlap from end of previous chunk
            overlap_text = ""
            if len(prev_chunk) > self.overlap:
                # Try to find a good break point (sentence or word boundary)
                overlap_candidate = prev_chunk[-self.overlap:]

                # Find sentence boundary in overlap
                for ending in self._chinese_sentence_endings:
                    idx = overlap_candidate.find(ending)
                    if idx != -1 and idx > len(overlap_candidate) // 2:
                        overlap_text = overlap_candidate[idx + 1:].strip()
                        break

                # If no good sentence boundary, use word boundary
                if not overlap_text:
                    # For Chinese, try to break at word boundary using jieba
                    words = list(jieba.cut(overlap_candidate))
                    overlap_text = overlap_candidate
                    for i, word in enumerate(reversed(words)):
                        if len(overlap_candidate) - sum(len(w) for w in words[len(words)-i:]) >= self.overlap // 2:
                            overlap_text = "".join(words[len(words)-i:])
                            break

            if overlap_text:
                # Prepend overlap to current chunk
                if not current_chunk.startswith(overlap_text):
                    result.append(overlap_text + " " + current_chunk)
                else:
                    result.append(current_chunk)
            else:
                result.append(current_chunk)

        return result

    def _split_by_sentences(self, text: str) -> List[str]:
        """
        按句子分割（中英文）。

        中文：。！？等
        英文：.!?等

        Args:
            text: 输入文本

        Returns:
            List[str]: 句子列表
        """
        # Use regex to split on sentence boundaries
        # This pattern handles both Chinese and English sentence endings
        sentences = self._sentence_pattern.split(text)

        # Filter out empty sentences
        return [s.strip() for s in sentences if s.strip()]

    def _extract_headings(self, text: str, max_level: int = 3) -> Dict[str, int]:
        """
        提取文本中的标题。

        识别 Markdown 风格标题 (#, ##) 或数字编号 (1., 1.1)

        Args:
            text: 输入文本
            max_level: 最大标题层级 (1-3)

        Returns:
            Dict[heading_text, position]: 标题及其在文本中的位置
        """
        headings: Dict[str, int] = {}

        # Pattern for Markdown-style headings: #, ##, ###
        markdown_pattern = re.compile(
            r"^(#{1," + str(max_level) + r"})\s+(.+)$",
            re.MULTILINE
        )

        # Pattern for numbered headings: 1., 1.1, 1.1.1
        numbered_pattern = re.compile(
            r"^(\d+(?:\.\d+){0," + str(max_level - 1) + r"})[\s、.]\s*(.+)$",
            re.MULTILINE
        )

        # Find Markdown headings
        for match in markdown_pattern.finditer(text):
            heading = match.group(2).strip()
            if heading and len(heading) < 200:  # Reasonable heading length
                headings[heading] = match.start()

        # Find numbered headings
        for match in numbered_pattern.finditer(text):
            number = match.group(1)
            title = match.group(2).strip()
            if title and len(title) < 200:
                headings[f"{number} {title}"] = match.start()

        return headings

    def _extract_keywords(self, text: str, top_k: int = 5) -> List[str]:
        """
        提取关键词（用于检索过滤）。

        使用 jieba 分词 + TF-IDF

        Args:
            text: 输入文本
            top_k: 提取的关键词数量

        Returns:
            List[str]: 关键词列表
        """
        if not text or len(text) < 10:
            return []

        try:
            # Use jieba's TF-IDF keyword extraction
            keywords = jieba.analyse.extract_tags(text, topK=top_k)
            return keywords
        except Exception:
            # Fallback to simple word frequency
            words = jieba.lcut(text)
            word_freq: Dict[str, int] = {}
            for word in words:
                word = word.strip().lower()
                if len(word) > 1:  # Filter out single characters
                    word_freq[word] = word_freq.get(word, 0) + 1

            # Sort by frequency
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            return [word for word, _ in sorted_words[:top_k]]


class ChunkMetadata:
    """
    块元数据工具类。

    Provides static methods for extracting metadata from text chunks.
    """

    @staticmethod
    def extract_headings(text: str, max_level: int = 3) -> List[str]:
        """
        提取文本中的标题。

        识别 Markdown 风格标题 (#, ##) 或数字编号 (1., 1.1)

        Args:
            text: 输入文本
            max_level: 最大标题层级

        Returns:
            List[str]: 标题列表
        """
        chunker = SmartChunker()
        headings_dict = chunker._extract_headings(text, max_level)
        return list(headings_dict.keys())

    @staticmethod
    def extract_keywords(text: str, top_k: int = 5) -> List[str]:
        """
        提取关键词（用于检索过滤）。

        使用 jieba 分词 + TF-IDF

        Args:
            text: 输入文本
            top_k: 提取的关键词数量

        Returns:
            List[str]: 关键词列表
        """
        chunker = SmartChunker()
        return chunker._extract_keywords(text, top_k)

    @staticmethod
    def count_words(text: str) -> int:
        """
        统计文本中的词数。

        Args:
            text: 输入文本

        Returns:
            int: 词数
        """
        words = jieba.lcut(text)
        return len([w for w in words if w.strip()])

    @staticmethod
    def count_characters(text: str) -> int:
        """
        统计文本中的字符数（不含空格）。

        Args:
            text: 输入文本

        Returns:
            int: 字符数
        """
        return len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
