from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.models.schemas import AskRequest, AskResponse
from app.services.embedding import EmbeddingService
from app.services.rag_pipeline import LLMError, RAGPipeline
from app.services.vector_store import VectorStore


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService(model_name=settings.EMBEDDING_MODEL)


def get_vector_store() -> VectorStore:
    return VectorStore(
        index_path=settings.FAISS_INDEX_PATH,
        embedding_dim=settings.EMBEDDING_DIM,
    )


def get_rag_pipeline(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
) -> RAGPipeline:
    return RAGPipeline(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )


router = APIRouter()


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = rag_pipeline.query(request.question, top_k=3)
        return AskResponse(
            answer=result["answer"],
            sources=result["sources"],
        )
    except LLMError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process question: {str(e)}")
