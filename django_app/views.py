import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings
from app.services.embedding import EmbeddingService
from app.services.pdf_loader import PDFLoader
from app.services.pdf_indexing import PDFIndexingError, index_pdf_file
from app.services.rag_pipeline import LLMError, RAGPipeline
from app.services.vector_store import VectorStore

SETTINGS_FILE = Path(__file__).resolve().parents[1] / "data" / "settings.json"
VALID_PROVIDERS = {"gemini", "openrouter"}


def _error_response(detail: str, status: int) -> JsonResponse:
    return JsonResponse({"detail": detail}, status=status)


def _get_json_body(request: HttpRequest) -> Dict[str, Any]:
    if not request.body:
        return {}

    try:
        parsed = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Invalid JSON body")

    if not isinstance(parsed, dict):
        raise ValueError("JSON payload must be an object")

    return parsed


def _load_persisted_settings() -> Dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}

    try:
        with SETTINGS_FILE.open("r", encoding="utf-8") as settings_file:
            data = json.load(settings_file)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        return {}

    return {}


def _build_runtime_llm_settings() -> Dict[str, Optional[str]]:
    persisted = _load_persisted_settings()

    provider = persisted.get("provider") or settings.LLM_PROVIDER
    if provider not in VALID_PROVIDERS:
        provider = settings.LLM_PROVIDER

    if provider == "gemini":
        default_model = settings.GEMINI_MODEL
        default_key = settings.GEMINI_API_KEY
    else:
        default_model = "anthropic/claude-3-haiku"
        default_key = settings.OPENROUTER_API_KEY

    model = persisted.get("model") or default_model
    api_key = persisted.get("api_key") or default_key

    return {
        "provider": provider,
        "model": model,
        "api_key": api_key,
    }


def root(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "message": "Lecture Note Q&A System API",
            "version": settings.APP_VERSION,
            "status": "running",
        }
    )


def health_check(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "healthy"})


@csrf_exempt
@require_http_methods(["POST"])
def upload_pdf(request: HttpRequest) -> JsonResponse:
    upload_file = request.FILES.get("file")
    if upload_file is None or not upload_file.name:
        return _error_response("No file provided", status=400)

    file_ext = os.path.splitext(upload_file.name)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        return _error_response(
            f"Invalid file type. Allowed types: {settings.ALLOWED_EXTENSIONS}",
            status=400,
        )

    if upload_file.size > settings.MAX_UPLOAD_SIZE:
        return _error_response(
            f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE} bytes",
            status=400,
        )

    pdf_loader = PDFLoader(documents_path=settings.DOCUMENTS_PATH)

    try:
        contents = upload_file.read()
        unique_filename = f"{uuid.uuid4()}_{upload_file.name}"
        saved_file_path = pdf_loader.save_pdf(contents, unique_filename)
    except OSError as exc:
        return _error_response(f"Failed to save PDF: {str(exc)}", status=500)

    try:
        index_stats = index_pdf_file(
            pdf_path=saved_file_path,
            chunk_size=500,
        )
    except PDFIndexingError as exc:
        return _error_response(str(exc), status=400)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            f"Failed to process embeddings: {str(exc)}",
            status=500,
        )

    return JsonResponse(
        {
            "success": True,
            "message": "PDF uploaded and indexed successfully",
            "filename": unique_filename,
            "chunks_created": index_stats["chunks_created"],
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def ask_question(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    question = str(payload.get("question", "")).strip()
    if not question:
        return _error_response("Question cannot be empty", status=400)

    embedding_service = EmbeddingService(model_name=settings.EMBEDDING_MODEL)
    vector_store = VectorStore(
        index_path=settings.FAISS_INDEX_PATH,
        embedding_dim=settings.EMBEDDING_DIM,
    )

    llm_settings = _build_runtime_llm_settings()
    rag_pipeline = RAGPipeline(
        embedding_service=embedding_service,
        vector_store=vector_store,
        provider=llm_settings["provider"] or settings.LLM_PROVIDER,
        model=llm_settings["model"],
        api_key=llm_settings["api_key"],
    )

    try:
        result = rag_pipeline.query(question, top_k=3)
    except LLMError as exc:
        return _error_response(str(exc), status=503)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            f"Failed to process question: {str(exc)}",
            status=500,
        )

    return JsonResponse(
        {
            "answer": result["answer"],
            "sources": result["sources"],
        }
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def settings_handler(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        stored_settings = _load_persisted_settings()
        provider = stored_settings.get("provider") or settings.LLM_PROVIDER
        if provider not in VALID_PROVIDERS:
            provider = settings.LLM_PROVIDER

        if provider == "gemini":
            default_model = settings.GEMINI_MODEL
            default_key = settings.GEMINI_API_KEY
        else:
            default_model = "anthropic/claude-3-haiku"
            default_key = settings.OPENROUTER_API_KEY

        model = stored_settings.get("model") or default_model
        api_key = stored_settings.get("api_key") or default_key

        return JsonResponse(
            {
                "provider": provider,
                "model": model,
                "has_api_key": bool(api_key),
            }
        )

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    provider = str(payload.get("provider", "")).strip().lower()
    model = str(payload.get("model", "")).strip()
    existing_settings = _load_persisted_settings()
    api_key: Optional[str]
    if "api_key" in payload:
        incoming_key = payload.get("api_key")
        if incoming_key is None:
            api_key = None
        else:
            stripped_key = str(incoming_key).strip()
            api_key = stripped_key or None
    else:
        api_key = existing_settings.get("api_key")

    if provider not in VALID_PROVIDERS:
        return _error_response("Invalid provider", status=400)

    if not model:
        return _error_response("Model cannot be empty", status=400)

    data_to_store: Dict[str, Optional[str]] = {
        "provider": provider,
        "model": model,
        "api_key": api_key,
    }

    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with SETTINGS_FILE.open("w", encoding="utf-8") as settings_file:
            json.dump(data_to_store, settings_file)
    except OSError as exc:
        return _error_response(f"Failed to save settings: {str(exc)}", status=500)

    return JsonResponse({"success": True, "message": "Settings updated"})
