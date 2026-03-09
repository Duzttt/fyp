"""
Smart chunking module for intelligent document splitting.

This module provides:
- SmartChunker: Intelligent chunking with semantic boundaries and overlap
- ChunkMetadata: Utilities for extracting headings and keywords
"""

from .smart_chunker import Chunk, ChunkMetadata, SmartChunker, SmartChunkerError

__all__ = [
    "Chunk",
    "ChunkMetadata",
    "SmartChunker",
    "SmartChunkerError",
]
