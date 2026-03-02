from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingError(Exception):
    pass


class EmbeddingService:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None

    def _get_model(self):
        if self.model is None:
            try:
                self.model = SentenceTransformer(self.model_name)
            except Exception as e:
                raise EmbeddingError(f"Failed to load embedding model: {str(e)}")
        return self.model

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.array([])

        try:
            model = self._get_model()
            embeddings = model.encode(texts, show_progress_bar=False)
            return embeddings
        except Exception as e:
            raise EmbeddingError(f"Failed to create embeddings: {str(e)}")

    def embed_query(self, query: str) -> np.ndarray:
        if not query or not query.strip():
            raise EmbeddingError("Query cannot be empty")

        try:
            model = self._get_model()
            embedding = model.encode([query], show_progress_bar=False)
            return embedding[0]
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {str(e)}")

    def get_embedding_dimension(self) -> int:
        model = self._get_model()
        dim = model.get_sentence_embedding_dimension()
        if dim is None:
            raise EmbeddingError("Could not determine embedding dimension")
        return dim
