import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.config import settings
from app.models.schemas import UploadResponse
from app.services.chunker import TextChunker
from app.services.embedding import EmbeddingService
from app.services.pdf_loader import PDFLoader, PDFLoaderError
from app.services.vector_store import VectorStore, VectorStoreError


def get_pdf_loader() -> PDFLoader:
    return PDFLoader(documents_path=settings.DOCUMENTS_PATH)


def get_chunker() -> TextChunker:
    return TextChunker(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService(model_name=settings.EMBEDDING_MODEL)


def get_vector_store() -> VectorStore:
    return VectorStore(
        index_path=settings.FAISS_INDEX_PATH,
        embedding_dim=settings.EMBEDDING_DIM,
    )


router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    pdf_loader: PDFLoader = Depends(get_pdf_loader),
    chunker: TextChunker = Depends(get_chunker),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {settings.ALLOWED_EXTENSIONS}",
        )

    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE} bytes",
        )

    try:
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        pdf_loader.save_pdf(contents, unique_filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save PDF: {str(e)}")

    try:
        text = pdf_loader.extract_text_from_bytes(contents, unique_filename)
    except PDFLoaderError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="No text extracted from PDF")

    chunks = chunker.chunk_text(text)

    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks created from text")

    try:
        embeddings = embedding_service.embed_texts(chunks)
        vector_store.add_embeddings(embeddings, chunks)
        vector_store.save()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process embeddings: {str(e)}")

    return UploadResponse(
        success=True,
        message="PDF uploaded and processed successfully",
        filename=unique_filename,
        chunks_created=len(chunks),
    )
