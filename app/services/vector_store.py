import os
from typing import List, Optional, Tuple

import faiss
import numpy as np


class VectorStoreError(Exception):
    pass


class VectorStore:
    def __init__(self, index_path: str, embedding_dim: int = 384):
        self.index_path = index_path
        self.embedding_dim = embedding_dim
        self.index: Optional[faiss.Index] = None
        self.chunks: List[str] = []
        self._load_or_create_index()

    def _load_or_create_index(self):
        os.makedirs(self.index_path, exist_ok=True)
        index_file = os.path.join(self.index_path, "index.faiss")
        chunks_file = os.path.join(self.index_path, "chunks.npy")

        if os.path.exists(index_file) and os.path.exists(chunks_file):
            try:
                self.index = faiss.read_index(index_file)
                self.chunks = np.load(chunks_file, allow_pickle=True).tolist()
            except Exception as e:
                raise VectorStoreError(f"Failed to load index: {str(e)}")
        else:
            self.index = faiss.IndexFlatL2(self.embedding_dim)

    def add_embeddings(self, embeddings: np.ndarray, chunks: List[str]) -> None:
        if len(embeddings) == 0:
            return

        if len(embeddings) != len(chunks):
            raise VectorStoreError("Number of embeddings must match number of chunks")

        embeddings_array = np.array(embeddings).astype("float32")
        self.index.add(embeddings_array)
        self.chunks.extend(chunks)

    def search(self, query_embedding: np.ndarray, top_k: int = 3) -> Tuple[List[str], List[float]]:
        if self.index.ntotal == 0:
            return [], []

        query_vector = np.array([query_embedding]).astype("float32")
        distances, indices = self.index.search(query_vector, min(top_k, self.index.ntotal))

        results = []
        result_distances = []

        for i, idx in enumerate(indices[0]):
            if idx < len(self.chunks):
                results.append(self.chunks[idx])
                result_distances.append(float(distances[0][i]))

        return results, result_distances

    def save(self) -> None:
        if self.index is None:
            return

        os.makedirs(self.index_path, exist_ok=True)
        index_file = os.path.join(self.index_path, "index.faiss")
        chunks_file = os.path.join(self.index_path, "chunks.npy")

        faiss.write_index(self.index, index_file)
        np.save(chunks_file, np.array(self.chunks, dtype=object))

    def clear(self) -> None:
        if self.index is not None:
            self.index.reset()
        self.chunks = []

    def get_total_chunks(self) -> int:
        return len(self.chunks)
