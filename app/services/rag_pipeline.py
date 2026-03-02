from typing import Dict, List, Optional

import requests

from app.config import settings
from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStore


class LLMError(Exception):
    pass


class RAGPipeline:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        api_key: Optional[str] = None,
        model: str = "anthropic/claude-3-haiku",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.model = model
        self.base_url = base_url

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        query_embedding = self.embedding_service.embed_query(query)
        sources, _ = self.vector_store.search(query_embedding, top_k=top_k)
        return sources

    def generate_answer(self, query: str, context: List[str]) -> str:
        if not context:
            return "No relevant information found in the uploaded documents."

        if not self.api_key:
            raise LLMError("OpenRouter API key not configured")

        context_text = "\n\n".join([f"Source {i+1}:\n{source}" for i, source in enumerate(context)])

        prompt = f"""Based on the following context from lecture notes, please answer the question.

Context:
{context_text}

Question: {query}

Answer:"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 500,
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            raise LLMError(f"Failed to generate answer: {str(e)}")
        except (KeyError, IndexError) as e:
            raise LLMError(f"Invalid response from LLM API: {str(e)}")

    def query(self, question: str, top_k: int = 3) -> Dict:
        sources = self.retrieve(question, top_k=top_k)
        answer = self.generate_answer(question, sources)
        return {
            "answer": answer,
            "sources": sources,
        }
