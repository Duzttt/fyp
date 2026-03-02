from typing import List, Optional

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    success: bool
    message: str
    filename: Optional[str] = None
    chunks_created: Optional[int] = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class AskResponse(BaseModel):
    answer: str
    sources: List[str]
