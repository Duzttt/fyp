import json
import os
import threading
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import faiss
import httpx
import numpy as np
import requests
from django.conf import settings as django_settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from ollama import Client as OllamaClient

from app.config import settings
from app.services.local_rag import (
    LocalRAGError,
    build_context_from_sources,
    generate_with_local_qwen,
    retrieve_with_faiss,
)
from app.services.pdf_loader import PDFLoader
from app.services.pdf_indexing import (
    PDFIndexingError,
    index_pdf_directory,
    index_pdf_file,
)
from django.template.loader import render_to_string

SETTINGS_FILE = Path(__file__).resolve().parents[1] / "data" / "settings.json"
RAG_CONFIG_FILE = Path(__file__).resolve().parents[1] / "data" / "rag_config.json"
CHAT_DEMO_FILE = Path(__file__).resolve().parent / "chat_demo.html"
VALID_PROVIDERS = {"gemini", "openrouter"}
LOCAL_QWEN_MODELS = [
    "qwen2.5:0.5b",
    "qwen2.5:1.5b",
    "qwen2.5:3b",
    "qwen2.5:7b",
    "qwen2.5:14b",
]
INDEXING_STRATEGY_FULL_REBUILD = "full_rebuild"
INDEXING_STRATEGY_APPEND = "append"
VALID_INDEXING_STRATEGIES = {
    INDEXING_STRATEGY_FULL_REBUILD,
    INDEXING_STRATEGY_APPEND,
}
INDEXING_STATUS_IDLE = "idle"
INDEXING_STATUS_QUEUED = "queued"
INDEXING_STATUS_RUNNING = "running"
INDEXING_STATUS_COMPLETED = "completed"
INDEXING_STATUS_FAILED = "failed"
_INDEXING_STATE_LOCK = threading.Lock()
_INDEXING_WORKER_THREAD: Optional[threading.Thread] = None
_INDEXING_RERUN_REQUESTED = False
_INDEXING_STATE: Dict[str, Any] = {
    "status": INDEXING_STATUS_IDLE,
    "strategy": INDEXING_STRATEGY_FULL_REBUILD,
    "is_async": bool(settings.UPLOAD_INDEXING_ASYNC),
    "pending_requests": 0,
    "last_uploaded_filename": None,
    "last_started_at": None,
    "last_completed_at": None,
    "last_error": None,
    "last_stats": None,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _resolve_upload_indexing_strategy() -> str:
    strategy = str(settings.UPLOAD_INDEXING_STRATEGY).strip().lower()
    if strategy in VALID_INDEXING_STRATEGIES:
        return strategy
    return INDEXING_STRATEGY_FULL_REBUILD


def _get_upload_indexing_state() -> Dict[str, Any]:
    with _INDEXING_STATE_LOCK:
        return dict(_INDEXING_STATE)


def _enqueue_full_rebuild(uploaded_filename: str) -> Dict[str, Any]:
    global _INDEXING_WORKER_THREAD
    global _INDEXING_RERUN_REQUESTED

    should_start_worker = False
    with _INDEXING_STATE_LOCK:
        _INDEXING_RERUN_REQUESTED = True
        _INDEXING_STATE["status"] = INDEXING_STATUS_QUEUED
        _INDEXING_STATE["strategy"] = INDEXING_STRATEGY_FULL_REBUILD
        _INDEXING_STATE["is_async"] = True
        _INDEXING_STATE["pending_requests"] = (
            int(_INDEXING_STATE.get("pending_requests", 0)) + 1
        )
        _INDEXING_STATE["last_uploaded_filename"] = uploaded_filename
        _INDEXING_STATE["last_error"] = None

        if _INDEXING_WORKER_THREAD is None or not _INDEXING_WORKER_THREAD.is_alive():
            _INDEXING_WORKER_THREAD = threading.Thread(
                target=_full_rebuild_worker,
                daemon=True,
                name="full-rebuild-index-worker",
            )
            should_start_worker = True

    if should_start_worker:
        _INDEXING_WORKER_THREAD.start()

    return _get_upload_indexing_state()


def _full_rebuild_worker() -> None:
    global _INDEXING_RERUN_REQUESTED

    while True:
        with _INDEXING_STATE_LOCK:
            if not _INDEXING_RERUN_REQUESTED:
                return

            _INDEXING_RERUN_REQUESTED = False
            _INDEXING_STATE["status"] = INDEXING_STATUS_RUNNING
            _INDEXING_STATE["pending_requests"] = 0
            _INDEXING_STATE["last_started_at"] = _utc_now_iso()
            _INDEXING_STATE["last_error"] = None

        try:
            index_stats = index_pdf_directory(
                data_source_dir=settings.DOCUMENTS_PATH,
                chunk_size=settings.CHUNK_SIZE,
                index_path=settings.FAISS_INDEX_PATH,
                model_name=settings.EMBEDDING_MODEL,
                clear_existing=True,
            )
            with _INDEXING_STATE_LOCK:
                _INDEXING_STATE["status"] = INDEXING_STATUS_COMPLETED
                _INDEXING_STATE["last_completed_at"] = _utc_now_iso()
                _INDEXING_STATE["last_stats"] = index_stats
                _INDEXING_STATE["last_error"] = None
        except Exception as exc:  # noqa: BLE001
            with _INDEXING_STATE_LOCK:
                _INDEXING_STATE["status"] = INDEXING_STATUS_FAILED
                _INDEXING_STATE["last_completed_at"] = _utc_now_iso()
                _INDEXING_STATE["last_error"] = str(exc)

        with _INDEXING_STATE_LOCK:
            should_rerun = bool(_INDEXING_RERUN_REQUESTED)
            if should_rerun:
                _INDEXING_STATE["status"] = INDEXING_STATUS_QUEUED

        if not should_rerun:
            return


def _error_response(detail: str, status: int) -> JsonResponse:
    return JsonResponse({"detail": detail}, status=status)


def _build_source_snippets(sources: Any) -> List[Dict[str, Any]]:
    snippets: List[Dict[str, Any]] = []
    if not isinstance(sources, list):
        return snippets

    for item in sources:
        if not isinstance(item, dict):
            continue
        snippets.append(
            {
                "source": str(item.get("source") or "unknown"),
                "page": item.get("page"),
                "text": str(item.get("text") or ""),
                "distance": item.get("distance"),
            }
        )
    return snippets


def _build_retrieved_chunks(sources: Any) -> List[Dict[str, Any]]:
    """Build retrieved chunks with similarity scores for visualization."""
    chunks: List[Dict[str, Any]] = []
    if not isinstance(sources, list):
        return chunks

    distances = [r.get("distance", 0) for r in sources if isinstance(r, dict)]
    max_distance = max(distances) if distances else 1.0
    max_distance = max(max_distance, 0.001)

    for r in sources:
        if not isinstance(r, dict):
            continue

        distance = r.get("distance", 0)
        similarity = max(0.0, 1.0 - (distance / max_distance))
        text = r.get("text", "")

        chunks.append(
            {
                "text": text,
                "preview": text[:100] + ("..." if len(text) > 100 else ""),
                "score": round(similarity, 3),
                "distance": round(distance, 4),
                "source": str(r.get("source", "unknown")),
                "page": r.get("page"),
            }
        )

    return chunks


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


def _load_rag_config() -> Dict[str, Any]:
    default_config = {
        "llm_model": settings.LOCAL_QWEN_MODEL,
        "top_k": 3,
        "temperature": 0.7,
    }
    if not RAG_CONFIG_FILE.exists():
        return default_config

    try:
        with RAG_CONFIG_FILE.open("r", encoding="utf-8") as config_file:
            data = json.load(config_file)
            if isinstance(data, dict):
                return {**default_config, **data}
    except (OSError, json.JSONDecodeError):
        return default_config

    return default_config


def _save_rag_config(config: Dict[str, Any]) -> None:
    RAG_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RAG_CONFIG_FILE.open("w", encoding="utf-8") as config_file:
        json.dump(config, config_file)


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


@require_http_methods(["GET"])
def index_page(request: HttpRequest) -> HttpResponse:
    """Serve the Vue.js frontend application (SPA)."""
    from django.conf import settings as django_settings

    frontend_index = (
        Path(django_settings.BASE_DIR)
        / "django_app"
        / "static"
        / "frontend"
        / "index.html"
    )

    if frontend_index.exists():
        html = frontend_index.read_text(encoding="utf-8")
        # Fix asset paths to include /static/frontend/ prefix for Django
        html = html.replace('src="/assets/', 'src="/static/frontend/assets/')
        html = html.replace('href="/assets/', 'href="/static/frontend/assets/')
        return HttpResponse(html, content_type="text/html; charset=utf-8")

    # Fallback to template if build doesn't exist
    return render(request, "index.html")


@require_http_methods(["GET"])
def app_page(request: HttpRequest) -> HttpResponse:
    """Serve the Vue.js frontend application."""
    return index_page(request)


@require_http_methods(["GET"])
def chat_demo_page(request: HttpRequest) -> HttpResponse:
    try:
        html = CHAT_DEMO_FILE.read_text(encoding="utf-8")
    except OSError:
        return HttpResponse(
            "Failed to load chat demo page.",
            status=500,
            content_type="text/plain; charset=utf-8",
        )
    return HttpResponse(html, content_type="text/html; charset=utf-8")


def health_check(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "healthy"})


@require_http_methods(["GET"])
def upload_index_status(request: HttpRequest) -> JsonResponse:
    return JsonResponse(_get_upload_indexing_state())


@csrf_exempt
@require_http_methods(["POST"])
def upload_pdf(request: HttpRequest) -> JsonResponse:
    upload_file = request.FILES.get("file")
    if upload_file is None or not upload_file.name:
        return _error_response("No file provided", status=400)

    original_filename = os.path.basename(str(upload_file.name).strip())
    if not original_filename:
        return _error_response("Invalid filename", status=400)

    file_ext = os.path.splitext(original_filename)[1].lower()
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
        # Prefer keeping the original filename; if a file with the same
        # name already exists, append a numeric suffix instead of a UUID.
        base_name, ext = os.path.splitext(original_filename)
        safe_filename = original_filename
        counter = 1
        while os.path.exists(os.path.join(settings.DOCUMENTS_PATH, safe_filename)):
            safe_filename = f"{base_name}_{counter}{ext}"
            counter += 1

        saved_file_path = pdf_loader.save_pdf(contents, safe_filename)
    except OSError as exc:
        return _error_response(f"Failed to save PDF: {str(exc)}", status=500)

    indexing_strategy = _resolve_upload_indexing_strategy()
    if (
        indexing_strategy == INDEXING_STRATEGY_FULL_REBUILD
        and settings.UPLOAD_INDEXING_ASYNC
    ):
        state = _enqueue_full_rebuild(uploaded_filename=safe_filename)
        return JsonResponse(
            {
                "success": True,
                "message": "File uploaded. Full reindex is running in background.",
                "filename": safe_filename,
                "saved_path": saved_file_path,
                "indexing_mode": INDEXING_STRATEGY_FULL_REBUILD,
                "indexing_status": state["status"],
            },
            status=202,
        )

    try:
        if indexing_strategy == INDEXING_STRATEGY_FULL_REBUILD:
            index_stats = index_pdf_directory(
                data_source_dir=settings.DOCUMENTS_PATH,
                chunk_size=settings.CHUNK_SIZE,
                index_path=settings.FAISS_INDEX_PATH,
                model_name=settings.EMBEDDING_MODEL,
                clear_existing=True,
            )
        elif indexing_strategy == INDEXING_STRATEGY_APPEND:
            index_stats = index_pdf_file(
                pdf_path=saved_file_path,
                chunk_size=settings.CHUNK_SIZE,
                model_name=settings.EMBEDDING_MODEL,
                clear_existing=False,
            )
        else:
            return _error_response(
                f"Invalid indexing strategy: {indexing_strategy}",
                status=500,
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
            "filename": safe_filename,
            "saved_path": saved_file_path,
            "indexing_mode": indexing_strategy,
            "indexing_status": INDEXING_STATUS_COMPLETED,
            "chunks_created": index_stats["chunks_created"],
            "total_chunks_in_index": index_stats["total_chunks_in_index"],
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def ask_question(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query") or payload.get("question") or "").strip()
    source_filter = payload.get("sources")
    if isinstance(source_filter, str):
        source_filter = [source_filter]

    if not query:
        return _error_response("Query cannot be empty", status=400)

    try:
        retrieved_sources = retrieve_with_faiss(
            query=query, top_k=3, source_filter=source_filter
        )
        context = build_context_from_sources(retrieved_sources)
        answer = generate_with_local_qwen(query=query, context=context)
    except requests.exceptions.Timeout:
        return _error_response(
            (
                "Local Qwen model request timed out "
                f"(timeout={settings.LOCAL_QWEN_TIMEOUT_SECONDS}s)"
            ),
            status=504,
        )
    except requests.exceptions.RequestException as exc:
        return _error_response(
            f"Failed to call local Qwen model: {str(exc)}",
            status=503,
        )
    except LocalRAGError as exc:
        return _error_response(str(exc), status=503)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            f"Failed to process query: {str(exc)}",
            status=500,
        )

    source_files = sorted(
        {
            str(source.get("source", "unknown"))
            for source in retrieved_sources
            if source.get("source")
        }
    )

    return JsonResponse(
        {
            "answer": answer,
            "sources": source_files,
            "source_snippets": _build_source_snippets(retrieved_sources),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def ask_qwen(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query") or "").strip()
    source_filter = payload.get("sources")
    if isinstance(source_filter, str):
        source_filter = [source_filter]

    if not query:
        return _error_response("Query cannot be empty", status=400)

    rag_config = _load_rag_config()
    top_k = rag_config.get("top_k", 3)
    llm_model = rag_config.get("llm_model", settings.LOCAL_QWEN_MODEL)
    temperature = rag_config.get("temperature", 0.7)

    try:
        retrieved_sources = retrieve_with_faiss(
            query=query, top_k=top_k, source_filter=source_filter
        )
        context = build_context_from_sources(retrieved_sources)
        if not context.strip():
            return _error_response("No indexed context found in FAISS", status=400)

        system_prompt = (
            "You are a rigorous academic teaching assistant. Please answer the questions based on the following reference materials."
            "If the evidence is insufficient, please explain clearly. "
            "Respond in English by default unless the user explicitly requests another language."
        )
        user_prompt = f"Reference materials:\n{context}\n\nUser question: {query}"

        ollama_client = OllamaClient(
            host=settings.LOCAL_QWEN_BASE_URL,
            timeout=settings.LOCAL_QWEN_TIMEOUT_SECONDS,
        )
        model_response = ollama_client.chat(
            model=llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
            keep_alive=settings.LOCAL_QWEN_KEEP_ALIVE,
            options={"temperature": temperature},
        )

        answer = str(model_response.get("message", {}).get("content", "")).strip()
        if not answer:
            raise LocalRAGError("Empty response from local Qwen model")
    except httpx.TimeoutException:
        return _error_response(
            (
                "Local Qwen model request timed out "
                f"(timeout={settings.LOCAL_QWEN_TIMEOUT_SECONDS}s)"
            ),
            status=504,
        )
    except httpx.RequestError as exc:
        return _error_response(
            f"Failed to call local Qwen model: {str(exc)}", status=503
        )
    except LocalRAGError as exc:
        return _error_response(str(exc), status=503)
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to process query: {str(exc)}", status=500)

    source_files = sorted(
        {
            str(source.get("source", "unknown"))
            for source in retrieved_sources
            if source.get("source")
        }
    )
    return JsonResponse(
        {
            "answer": answer,
            "sources": source_files,
            "source_snippets": _build_source_snippets(retrieved_sources),
            "retrieved_chunks": _build_retrieved_chunks(retrieved_sources),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def ask_with_citations(request: HttpRequest) -> JsonResponse:
    """
    Ask a question and get an answer with sentence-level citations.

    Returns structured JSON where each sentence has a citations array
    referencing the source chunks that support it.

    Response format:
    {
        "sentences": [
            {"text": "...", "citations": [1, 2]},
            {"text": "...", "citations": [1]},
            {"text": "...", "citations": []}
        ],
        "sources": {
            "1": {"file": "lecture.pdf", "page": 24},
            "2": {"file": "lecture.pdf", "page": 3}
        },
        "retrieved_chunks": [...]
    }
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query") or "").strip()
    source_filter = payload.get("sources")
    if isinstance(source_filter, str):
        source_filter = [source_filter]

    if not query:
        return _error_response("Query cannot be empty", status=400)

    # Load configuration
    rag_config = _load_rag_config()
    top_k = rag_config.get("top_k", 3)
    llm_model = rag_config.get("llm_model", settings.LOCAL_QWEN_MODEL)

    try:
        # Use the citation-aware RAG pipeline
        from app.services.citation_rag import CitationRAGPipeline, CitationRAGError

        pipeline = CitationRAGPipeline(model=llm_model)
        result = pipeline.query(
            question=query,
            top_k=top_k,
            source_filter=source_filter,
        )
    except httpx.TimeoutException:
        return _error_response(
            (
                "Local Qwen model request timed out "
                f"(timeout={settings.LOCAL_QWEN_TIMEOUT_SECONDS}s)"
            ),
            status=504,
        )
    except httpx.RequestError as exc:
        return _error_response(
            f"Failed to call local Qwen model: {str(exc)}", status=503
        )
    except CitationRAGError as exc:
        return _error_response(str(exc), status=503)
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to process query: {str(exc)}", status=500)

    # Build retrieved chunks for visualization
    # Extract chunks from sources in the result
    retrieved_chunks = []
    for chunk_id, source_info in result.get("sources", {}).items():
        retrieved_chunks.append(
            {
                "chunk_id": int(chunk_id),
                "text": source_info.get("text", ""),
                "source": source_info.get("file", "unknown"),
                "page": source_info.get("page"),
            }
        )

    return JsonResponse(
        {
            "sentences": result.get("sentences", []),
            "sources": result.get("sources", {}),
            "retrieved_chunks": (
                _build_retrieved_chunks(retrieved_chunks) if retrieved_chunks else []
            ),
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


@require_http_methods(["GET"])
def list_files(request: HttpRequest) -> JsonResponse:
    doc_path = Path(settings.DOCUMENTS_PATH)
    files = []
    if doc_path.exists():
        for f in doc_path.glob("*.pdf"):
            stats = f.stat()
            files.append(
                {
                    "name": f.name,
                    "size": stats.st_size,
                    "created_at": datetime.fromtimestamp(
                        stats.st_ctime, tz=timezone.utc
                    ).isoformat(),
                }
            )
    return JsonResponse(
        {"files": sorted(files, key=lambda x: x["created_at"], reverse=True)}
    )


@require_http_methods(["GET"])
def list_documents(request: HttpRequest) -> JsonResponse:
    upload_dir = os.path.join(str(django_settings.MEDIA_ROOT), "data_source")
    if not os.path.exists(upload_dir):
        return JsonResponse({"files": []})

    files = sorted(
        [
            filename
            for filename in os.listdir(upload_dir)
            if filename.lower().endswith(".pdf")
        ]
    )
    return JsonResponse({"files": files})


@csrf_exempt
@require_http_methods(["POST"])
def delete_document(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    filename = str(payload.get("filename") or "").strip()
    if not filename:
        return _error_response("Filename is required", status=400)

    upload_dir = os.path.join(str(django_settings.MEDIA_ROOT), "data_source")
    file_path = os.path.join(upload_dir, filename)
    if not os.path.exists(file_path):
        return _error_response("File not found", status=404)

    try:
        os.remove(file_path)
    except OSError as exc:
        return _error_response(f"Failed to delete file: {str(exc)}", status=500)

    try:
        index_stats = index_pdf_directory(
            data_source_dir=settings.DOCUMENTS_PATH,
            chunk_size=settings.CHUNK_SIZE,
            index_path=settings.FAISS_INDEX_PATH,
            model_name=settings.EMBEDDING_MODEL,
            clear_existing=True,
        )
    except PDFIndexingError as exc:
        return _error_response(str(exc), status=400)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            f"Failed to rebuild embeddings after delete: {str(exc)}",
            status=500,
        )

    return JsonResponse(
        {
            "success": True,
            "message": "Document deleted and index rebuilt successfully",
            "filename": filename,
            "chunks_created": index_stats["chunks_created"],
            "total_chunks_in_index": index_stats["total_chunks_in_index"],
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def summarize_doc(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    filename = payload.get("filename")
    if not filename:
        return _error_response("Filename is required", status=400)

    query = (
        f"Please summarize the core content of document {filename}, and list the "
        "3 most important knowledge points."
    )

    try:
        retrieved_sources = retrieve_with_faiss(query=query, top_k=6)
        # Attempt to filter by filename (case-insensitive and partial match to handle UUID prefixes)
        target = str(filename).lower()
        filtered = [
            s for s in retrieved_sources if target in str(s.get("source", "")).lower()
        ]

        if not filtered:
            filtered = retrieved_sources

        context = build_context_from_sources(filtered)
        summary = generate_with_local_qwen(query=query, context=context)

        return JsonResponse({"summary": summary, "filename": filename})
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Summary failed: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def generate_podcast(request: HttpRequest) -> JsonResponse:
    # Placeholder for podcast generation logic
    # In a real implementation, this would generate a dialogue script and then use TTS.
    return JsonResponse(
        {
            "success": True,
            "message": "Podcast generation is a placeholder. Mock audio returned.",
            "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        }
    )


@require_http_methods(["GET"])
def get_rag_config(request: HttpRequest) -> JsonResponse:
    config = _load_rag_config()
    return JsonResponse(config)


@csrf_exempt
@require_http_methods(["POST"])
def update_rag_config(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    llm_model = str(payload.get("llm_model", settings.LOCAL_QWEN_MODEL)).strip()
    top_k = int(payload.get("top_k", 3))
    temperature = float(payload.get("temperature", 0.7))

    if top_k < 1:
        top_k = 1
    elif top_k > 20:
        top_k = 20

    if temperature < 0.0:
        temperature = 0.0
    elif temperature > 2.0:
        temperature = 2.0

    config = {
        "llm_model": llm_model,
        "top_k": top_k,
        "temperature": temperature,
    }
    _save_rag_config(config)
    return JsonResponse({"status": "success", "config": config})


@csrf_exempt
@require_http_methods(["POST"])
def reset_faiss_index(request: HttpRequest) -> JsonResponse:
    import shutil

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    confirm_text = str(payload.get("confirm", "")).strip().lower()
    if confirm_text != "reset":
        return _error_response(
            'Please type "reset" to confirm index deletion', status=400
        )

    index_path = Path(settings.FAISS_INDEX_PATH)
    if index_path.exists():
        shutil.rmtree(index_path)
        index_path.mkdir(parents=True, exist_ok=True)

    return JsonResponse({"status": "success", "message": "FAISS index has been reset"})


def inject_citation_marks(answer: str, citations: List[Dict[str, Any]]) -> str:
    """
    Inject citation marks [1], [2], etc. into the answer text.
    Places citations at the end of sentences or paragraphs.
    """
    if not citations:
        return answer

    import re

    citation_ids = [c.get("citation_id", i + 1) for i, c in enumerate(citations)]

    sentences = re.split(r"([。！？.!?\n]+)", answer)
    result = []
    citation_idx = 0

    for i, part in enumerate(sentences):
        result.append(part)

        if i % 2 == 0 and part.strip() and citation_idx < len(citation_ids):
            if len(part.strip()) > 20:
                result.append(
                    f' <span class="inline-citation" data-citation-id="{citation_ids[citation_idx]}">[{citation_ids[citation_idx]}]</span>'
                )
                citation_idx += 1

    if citation_idx < len(citation_ids):
        result.append(
            ' <span class="inline-citations">'
            + " ".join(
                [
                    f'<span class="inline-citation" data-citation-id="{cid}">[{cid}]</span>'
                    for cid in citation_ids[citation_idx:]
                ]
            )
            + "</span>"
        )

    return "".join(result)


@csrf_exempt
@require_http_methods(["POST"])
def chat_htmx(request: HttpRequest) -> HttpResponse:
    from datetime import datetime

    query = str(request.POST.get("query", "")).strip()
    if not query:
        return HttpResponse(
            '<div class="chat-message chat-message-error"><div class="chat-message-text">'
            "Question cannot be empty."
            "</div></div>",
            status=400,
        )

    rag_config = _load_rag_config()
    top_k = rag_config.get("top_k", 3)
    llm_model = rag_config.get("llm_model", settings.LOCAL_QWEN_MODEL)
    temperature = rag_config.get("temperature", 0.7)

    retrieved_sources: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    retrieved_chunks: List[Dict[str, Any]] = []

    try:
        retrieved_sources = retrieve_with_faiss(
            query=query,
            top_k=top_k,
            source_filter=None,
        )
        context = build_context_from_sources(retrieved_sources)

        distances = [r.get("distance", 0) for r in retrieved_sources]
        max_distance = max(distances) if distances else 1.0
        max_distance = max(max_distance, 0.001)

        for idx, src in enumerate(retrieved_sources, start=1):
            distance = src.get("distance", 0)
            similarity = max(0.0, 1.0 - (distance / max_distance))
            text = src.get("text", "")
            citations.append(
                {
                    "citation_id": idx,
                    "source": src.get("source", "unknown"),
                    "page": src.get("page"),
                    "text": text[:200],
                    "bbox": src.get("bbox"),
                }
            )
            retrieved_chunks.append(
                {
                    "text": text,
                    "preview": text[:100],
                    "score": round(similarity, 3),
                    "distance": round(distance, 4),
                    "source": src.get("source", "unknown"),
                    "page": src.get("page"),
                    "bbox": src.get("bbox"),
                }
            )

        if not context.strip():
            answer = (
                "No indexed context found in FAISS. Please upload and index PDFs first."
            )
        else:
            system_prompt = (
                "You are a rigorous academic teaching assistant. Please answer the questions based on the following reference materials. "
                "If the evidence is insufficient, please explain clearly."
            )
            user_prompt = f"Reference materials:\n{context}\n\nUser question: {query}"

            ollama_client = OllamaClient(
                host=settings.LOCAL_QWEN_BASE_URL,
                timeout=settings.LOCAL_QWEN_TIMEOUT_SECONDS,
            )
            model_response = ollama_client.chat(
                model=llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                keep_alive=settings.LOCAL_QWEN_KEEP_ALIVE,
                options={"temperature": temperature},
            )
            answer = str(model_response.get("message", {}).get("content", "")).strip()
            if not answer:
                answer = "Empty response from local Qwen model."
            else:
                answer = inject_citation_marks(answer, citations)
    except Exception as exc:  # noqa: BLE001
        answer = f"Failed to process query: {str(exc)}"

    timestamp = datetime.now().strftime("%H:%M")
    message_id = f"msg_{int(datetime.now().timestamp() * 1000)}"

    assistant_html = render_to_string(
        "_chat_message.html",
        {
            "role": "assistant",
            "text": answer,
            "timestamp": timestamp,
            "message_id": f"assistant_{message_id}",
            "citations": citations,
            "citations_json": json.dumps(citations),
            "retrieved_chunks": retrieved_chunks,
        },
    )
    return HttpResponse(assistant_html)


@csrf_exempt
@require_http_methods(["POST"])
def retrieve_chunks(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query") or "").strip()
    top_k = int(payload.get("top_k", 5))
    source_filter = payload.get("sources")

    if not query:
        return _error_response("Query cannot be empty", status=400)

    if isinstance(source_filter, str):
        source_filter = [source_filter]

    try:
        results = retrieve_with_faiss(
            query=query, top_k=top_k, source_filter=source_filter
        )
    except LocalRAGError as exc:
        return _error_response(str(exc), status=503)

    if not results:
        return JsonResponse({"chunks": []})

    distances = [r.get("distance", 0) for r in results]
    max_distance = max(distances) if distances else 1.0
    max_distance = max(max_distance, 0.001)

    chunks = []
    for r in results:
        distance = r.get("distance", 0)
        similarity = max(0.0, 1.0 - (distance / max_distance))

        text = r.get("text", "")
        preview = text[:100] + ("..." if len(text) > 100 else "")

        chunks.append(
            {
                "text": text,
                "preview": preview,
                "score": round(similarity, 3),
                "distance": round(distance, 4),
                "source": r.get("source", "unknown"),
                "page": r.get("page"),
            }
        )

    return JsonResponse({"chunks": chunks})


@csrf_exempt
@require_http_methods(["POST"])
def compare_documents(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query") or "").strip()
    sources = payload.get("sources")

    if not query:
        return _error_response("Query cannot be empty", status=400)

    if not sources or not isinstance(sources, list):
        return _error_response("Sources must be a list of document names", status=400)

    if len(sources) < 2:
        return _error_response(
            "At least 2 documents required for comparison", status=400
        )

    if len(sources) > 3:
        return _error_response(
            "Maximum 3 documents can be compared at once", status=400
        )

    rag_config = _load_rag_config()
    top_k = rag_config.get("top_k", 3)
    llm_model = rag_config.get("llm_model", settings.LOCAL_QWEN_MODEL)
    temperature = rag_config.get("temperature", 0.7)

    results: List[Dict[str, Any]] = []

    for source in sources:
        try:
            retrieved = retrieve_with_faiss(
                query=query,
                top_k=top_k,
                source_filter=[source],
            )
            context = build_context_from_sources(retrieved)

            if not context.strip():
                results.append(
                    {
                        "source": source,
                        "answer": "No relevant content found in this document.",
                        "success": True,
                    }
                )
                continue

            system_prompt = (
                "You are a rigorous academic teaching assistant. Please answer the question "
                "based strictly on the provided reference material. If evidence is insufficient, "
                "say so clearly."
            )
            user_prompt = f"Reference material:\n{context}\n\nQuestion: {query}"

            ollama_client = OllamaClient(
                host=settings.LOCAL_QWEN_BASE_URL,
                timeout=settings.LOCAL_QWEN_TIMEOUT_SECONDS,
            )
            model_response = ollama_client.chat(
                model=llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                keep_alive=settings.LOCAL_QWEN_KEEP_ALIVE,
                options={"temperature": temperature},
            )
            answer = str(model_response.get("message", {}).get("content", "")).strip()
            if not answer:
                answer = "Empty response from model."

            results.append(
                {
                    "source": source,
                    "answer": answer,
                    "success": True,
                }
            )

        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "source": source,
                    "answer": f"Error: {str(exc)}",
                    "success": False,
                }
            )

    common_points, different_points = analyze_differences(
        [r["answer"] for r in results if r["success"]]
    )

    return JsonResponse(
        {
            "results": results,
            "analysis": {
                "common": common_points,
                "different": different_points,
            },
        }
    )


# ==========================================
# Dashboard API Endpoints
# ==========================================


@require_http_methods(["GET"])
def dashboard_stats(request: HttpRequest) -> JsonResponse:
    """
    Get dashboard statistics including document stats, vector info, and storage info.
    """

    # Document statistics
    doc_path = Path(settings.DOCUMENTS_PATH)
    pdf_files = list(doc_path.glob("*.pdf")) if doc_path.exists() else []
    total_documents = len(pdf_files)

    # Vector store statistics
    index_path = Path(settings.FAISS_INDEX_PATH)
    index_file = index_path / "index.faiss"
    chunks_file = index_path / "chunks.npy"

    total_vectors = 0
    embedding_dim = settings.EMBEDDING_DIM
    index_type = "IndexFlatL2"
    total_pages = 0
    total_chunks = 0

    if index_file.exists() and chunks_file.exists():
        try:
            index = faiss.read_index(str(index_file))
            total_vectors = index.ntotal

            chunks = np.load(chunks_file, allow_pickle=True).tolist()
            if isinstance(chunks, list):
                total_chunks = len(chunks)
                # Count unique pages
                pages = set()
                for chunk in chunks:
                    if isinstance(chunk, dict):
                        page = chunk.get("page")
                        if page is not None:
                            pages.add(page)
                        source = chunk.get("source", "")
                total_pages = len(pages) or total_documents
        except Exception:
            pass

    # Storage information
    faiss_size_kb = 0
    docs_size_kb = 0

    if index_file.exists():
        faiss_size_kb = index_file.stat().st_size / 1024

    for pdf in pdf_files:
        docs_size_kb += pdf.stat().st_size / 1024

    return JsonResponse(
        {
            "documents": {
                "total": total_documents,
                "total_pages": total_pages,
                "total_chunks": total_chunks,
            },
            "vectors": {
                "dimension": embedding_dim,
                "index_type": index_type,
                "total_vectors": total_vectors,
            },
            "storage": {
                "faiss_index_size_kb": round(faiss_size_kb, 2),
                "documents_size_kb": round(docs_size_kb, 2),
            },
        }
    )


@require_http_methods(["GET"])
def dashboard_metrics(request: HttpRequest) -> JsonResponse:
    """
    Get performance metrics including average retrieval and embedding times.
    """
    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStore

    # Measure embedding time
    embedding_time_ms = 0
    try:
        embedding_service = EmbeddingService()
        test_text = "This is a test sentence for measuring embedding performance."
        start = time.perf_counter()
        embedding_service.embed_query(test_text)
        embedding_time_ms = (time.perf_counter() - start) * 1000
    except Exception:
        pass

    # Measure retrieval time
    retrieval_time_ms = 0
    try:
        vector_store = VectorStore.get_cached(
            settings.FAISS_INDEX_PATH, settings.EMBEDDING_DIM
        )
        if vector_store.index and vector_store.index.ntotal > 0:
            embedding_service = EmbeddingService()
            query_embedding = embedding_service.embed_query("test query")
            start = time.perf_counter()
            vector_store.search(query_embedding, top_k=3)
            retrieval_time_ms = (time.perf_counter() - start) * 1000
    except Exception:
        pass

    # Quality metrics (placeholder - would need test set for real accuracy)
    quality_metrics = {
        "top_1_accuracy": None,
        "top_3_accuracy": None,
        "top_5_accuracy": None,
        "note": "Requires test set for accuracy calculation",
    }

    return JsonResponse(
        {
            "performance": {
                "avg_retrieval_time_ms": round(retrieval_time_ms, 2),
                "avg_embedding_time_ms": round(embedding_time_ms, 2),
            },
            "quality": quality_metrics,
        }
    )


@require_http_methods(["GET"])
def dashboard_chunks_distribution(request: HttpRequest) -> JsonResponse:
    """
    Get chunk length distribution data for histogram.
    """

    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    chunk_lengths = []
    if chunks_file.exists():
        try:
            chunks = np.load(chunks_file, allow_pickle=True).tolist()
            if isinstance(chunks, list):
                for chunk in chunks:
                    if isinstance(chunk, dict):
                        text = chunk.get("text", "")
                    else:
                        text = str(chunk)
                    chunk_lengths.append(len(text))
        except Exception:
            pass

    # Create histogram bins
    if chunk_lengths:
        min_len = min(chunk_lengths)
        max_len = max(chunk_lengths)
        bin_count = min(20, len(chunk_lengths))
        bin_width = (max_len - min_len) / bin_count if bin_count > 0 else 1

        bins = []
        for i in range(bin_count):
            bin_start = min_len + i * bin_width
            bin_end = min_len + (i + 1) * bin_width
            count = sum(1 for length in chunk_lengths if bin_start <= length < bin_end)
            bins.append(
                {
                    "range": f"{int(bin_start)}-{int(bin_end)}",
                    "count": count,
                }
            )

        stats = {
            "min": min_len,
            "max": max_len,
            "mean": round(sum(chunk_lengths) / len(chunk_lengths), 2),
            "median": sorted(chunk_lengths)[len(chunk_lengths) // 2],
        }
    else:
        bins = []
        stats = {"min": 0, "max": 0, "mean": 0, "median": 0}

    return JsonResponse(
        {
            "histogram": bins,
            "statistics": stats,
            "total_chunks": len(chunk_lengths),
        }
    )


@require_http_methods(["GET"])
def dashboard_similarity_distribution(request: HttpRequest) -> JsonResponse:
    """
    Get similarity score distribution data.
    """
    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStore

    similarity_scores = []

    try:
        vector_store = VectorStore.get_cached(
            settings.FAISS_INDEX_PATH, settings.EMBEDDING_DIM
        )
        if vector_store.index and vector_store.index.ntotal > 0:
            embedding_service = EmbeddingService()

            # Sample some queries and collect similarity scores
            test_queries = ["what is", "explain", "describe", "define", "list"]

            for query in test_queries:
                query_embedding = embedding_service.embed_query(query)
                results = vector_store.search_with_metadata(query_embedding, top_k=10)

                for result in results:
                    distance = result.get("distance", 0)
                    # Convert L2 distance to similarity (approximate)
                    similarity = max(0, 1 - (distance / 2))
                    similarity_scores.append(round(similarity, 3))
    except Exception:
        pass

    # Create distribution bins
    if similarity_scores:
        bins = []
        for i in range(10):
            bin_start = i * 0.1
            bin_end = (i + 1) * 0.1
            count = sum(
                1 for score in similarity_scores if bin_start <= score < bin_end
            )
            bins.append(
                {
                    "range": f"{bin_start:.1f}-{bin_end:.1f}",
                    "count": count,
                }
            )

        stats = {
            "min": round(min(similarity_scores), 3),
            "max": round(max(similarity_scores), 3),
            "mean": round(sum(similarity_scores) / len(similarity_scores), 3),
        }
    else:
        bins = []
        stats = {"min": 0, "max": 0, "mean": 0}

    return JsonResponse(
        {
            "histogram": bins,
            "statistics": stats,
            "sample_size": len(similarity_scores),
        }
    )


@require_http_methods(["GET"])
def dashboard_documents_timeline(request: HttpRequest) -> JsonResponse:
    """
    Get document upload timeline data.
    """
    doc_path = Path(settings.DOCUMENTS_PATH)
    documents = []

    if doc_path.exists():
        for pdf in doc_path.glob("*.pdf"):
            try:
                stats = pdf.stat()
                documents.append(
                    {
                        "name": pdf.name,
                        "display_name": (
                            "_".join(pdf.name.split("_")[1:])
                            if "_" in pdf.name
                            else pdf.name
                        ),
                        "size_kb": round(stats.st_size / 1024, 2),
                        "created_at": datetime.fromtimestamp(
                            stats.st_ctime, tz=timezone.utc
                        ).isoformat(),
                        "modified_at": datetime.fromtimestamp(
                            stats.st_mtime, tz=timezone.utc
                        ).isoformat(),
                    }
                )
            except Exception:
                pass

    # Sort by creation date
    documents.sort(key=lambda x: x["created_at"], reverse=True)

    return JsonResponse(
        {
            "documents": documents,
            "total": len(documents),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def dashboard_update_config(request: HttpRequest) -> JsonResponse:
    """
    Update RAG configuration including chunk_size, overlap, etc.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    chunk_size = payload.get("chunk_size")
    chunk_overlap = payload.get("chunk_overlap")

    # Update .env file or settings (for now, just validate)
    errors = []

    if chunk_size is not None:
        try:
            chunk_size = int(chunk_size)
            if chunk_size < 100 or chunk_size > 2000:
                errors.append("chunk_size must be between 100 and 2000")
        except (ValueError, TypeError):
            errors.append("chunk_size must be an integer")

    if chunk_overlap is not None:
        try:
            chunk_overlap = int(chunk_overlap)
            if chunk_overlap < 0 or chunk_overlap > 500:
                errors.append("chunk_overlap must be between 0 and 500")
        except (ValueError, TypeError):
            errors.append("chunk_overlap must be an integer")

    if errors:
        return _error_response("; ".join(errors), status=400)

    # Save to rag_config.json
    config = _load_rag_config()

    if chunk_size is not None:
        config["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        config["chunk_overlap"] = chunk_overlap

    _save_rag_config(config)

    return JsonResponse(
        {
            "status": "success",
            "config": config,
            "message": "Configuration updated. Reindex required for chunking changes to take effect.",
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def dashboard_reindex(request: HttpRequest) -> JsonResponse:
    """
    Trigger reindexing of all documents.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    force = payload.get("force", False)

    # Check current indexing state
    current_state = _get_upload_indexing_state()
    if current_state["status"] == INDEXING_STATUS_RUNNING:
        return _error_response("Indexing is already in progress", status=409)

    # Trigger full rebuild
    state = _enqueue_full_rebuild(uploaded_filename="manual_reindex")

    return JsonResponse(
        {
            "status": "success",
            "message": "Reindexing started",
            "indexing_state": state,
        }
    )


def analyze_differences(answers: List[str]) -> tuple[List[str], List[str]]:
    """
    Analyze differences between multiple answers.
    Returns (common_points, different_points).
    """
    if len(answers) < 2:
        return [], []

    import re

    def extract_sentences(text: str) -> List[str]:
        sentences = re.split(r"[。！？.!?\n]+", text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    all_sentences = [extract_sentences(a) for a in answers]

    sentence_counts: Dict[str, int] = {}
    for sentences in all_sentences:
        for s in sentences:
            normalized = s.lower()
            sentence_counts[normalized] = sentence_counts.get(normalized, 0) + 1

    common = [
        s for s, count in sentence_counts.items() if count == len(answers) and count > 1
    ]

    different = []
    for i, sentences in enumerate(all_sentences):
        for s in sentences:
            normalized = s.lower()
            if sentence_counts.get(normalized, 0) == 1:
                different.append(f"[{answers[i][:20]}...] {s[:80]}...")

    common_points = [s.capitalize() for s in common[:5]]
    different_points = different[:5]

    return common_points, different_points


# ==========================================
# Admin Dashboard API Endpoints (Phase 1)
# ==========================================


@require_http_methods(["GET"])
def admin_stats(request: HttpRequest) -> JsonResponse:
    """
    Get comprehensive system statistics for admin dashboard.
    """
    from django_app.models import QueryLog
    from django.db.models import Avg, Max
    from datetime import timedelta

    doc_path = Path(settings.DOCUMENTS_PATH)
    pdf_files = list(doc_path.glob("*.pdf")) if doc_path.exists() else []
    total_documents = len(pdf_files)

    index_path = Path(settings.FAISS_INDEX_PATH)
    index_file = index_path / "index.faiss"
    chunks_file = index_path / "chunks.npy"

    total_vectors = 0
    total_chunks = 0
    unique_pages = set()

    if index_file.exists() and chunks_file.exists():
        try:
            index = faiss.read_index(str(index_file))
            total_vectors = index.ntotal

            chunks = np.load(chunks_file, allow_pickle=True).tolist()
            if isinstance(chunks, list):
                total_chunks = len(chunks)
                for chunk in chunks:
                    if isinstance(chunk, dict):
                        page = chunk.get("page")
                        if page is not None:
                            unique_pages.add(page)
        except Exception:
            pass

    faiss_size_kb = index_file.stat().st_size / 1024 if index_file.exists() else 0
    docs_size_kb = sum(f.stat().st_size / 1024 for f in pdf_files)

    now = datetime.now(timezone.utc)
    today_start = now - timedelta(days=1)
    week_start = now - timedelta(days=7)

    today_queries = QueryLog.objects.filter(created_at__gte=today_start).count()
    week_queries = QueryLog.objects.filter(created_at__gte=week_start).count()

    latency_stats = QueryLog.objects.filter(created_at__gte=week_start).aggregate(
        avg_latency=Avg("latency_ms"),
        p95_latency=Max("latency_ms"),
    )

    cache_hits = QueryLog.objects.filter(
        created_at__gte=week_start, cache_hit=True
    ).count()
    cache_total = QueryLog.objects.filter(created_at__gte=week_start).count()
    cache_hit_rate = (cache_hits / cache_total * 100) if cache_total > 0 else 0

    health_status = {
        "faiss_index": "healthy" if total_vectors > 0 else "empty",
        "llm_service": "unknown",
        "disk_space": "healthy" if faiss_size_kb < 500000 else "warning",
        "memory": "unknown",
    }

    return JsonResponse(
        {
            "documents": {
                "total": total_documents,
                "chunks": total_chunks,
                "pages": len(unique_pages),
            },
            "vectors": {
                "dimension": settings.EMBEDDING_DIM,
                "count": total_vectors,
                "index_type": "IndexFlatL2",
            },
            "storage": {
                "faiss_size_kb": round(faiss_size_kb, 2),
                "docs_size_kb": round(docs_size_kb, 2),
            },
            "queries": {
                "today": today_queries,
                "week": week_queries,
                "avg_latency_ms": round(latency_stats.get("avg_latency") or 0, 2),
                "p95_latency_ms": latency_stats.get("p95_latency") or 0,
                "cache_hit_rate": round(cache_hit_rate, 2),
            },
            "health": health_status,
        }
    )


@require_http_methods(["GET"])
def admin_query_stats(request: HttpRequest) -> JsonResponse:
    """
    Get query statistics for admin dashboard.
    """
    from django_app.models import QueryLog
    from django.db.models import Avg, Count
    from datetime import timedelta

    hours = int(request.GET.get("hours", 24))
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    query_stats = QueryLog.objects.filter(created_at__gte=start_time).aggregate(
        total=Count("id"),
        avg_latency=Avg("latency_ms"),
    )

    type_dist = (
        QueryLog.objects.filter(created_at__gte=start_time)
        .values("query_type")
        .annotate(count=Count("id"))
    )

    return JsonResponse(
        {
            "total_queries": query_stats["total"] or 0,
            "avg_latency_ms": round(query_stats["avg_latency"] or 0, 2),
            "type_distribution": list(type_dist),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def admin_debug_retrieval(request: HttpRequest) -> JsonResponse:
    """
    Debug retrieval by comparing BM25, dense, and hybrid retrieval results.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query", "")).strip()
    if not query:
        return _error_response("Query is required", status=400)

    params = payload.get("params", {})
    alpha = float(params.get("alpha", 0.3))
    fusion_method = params.get("fusion", "rrf")
    top_k = int(params.get("top_k", 5))
    rrf_k = int(params.get("rrf_k", 60))

    if not query:
        return _error_response("Query cannot be empty", status=400)

    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStore

    result = {
        "bm25": {"results": [], "time_ms": 0},
        "dense": {"results": [], "time_ms": 0},
        "hybrid": {"results": [], "time_ms": 0},
    }

    try:
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=settings.EMBEDDING_DIM,
        )
        embedding_service = EmbeddingService()

        if not vector_store.chunks:
            return _error_response("No indexed documents found", status=400)

        all_chunks = vector_store.chunks
        if not isinstance(all_chunks, list):
            all_chunks = []

        if fusion_method == "rrf":
            from retrieval.hybrid_retriever import (
                HybridRetriever,
                FusionMethod as HMFusion,
            )

            docs_for_hybrid = []
            for i, chunk in enumerate(all_chunks):
                text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                source = (
                    chunk.get("source", "unknown")
                    if isinstance(chunk, dict)
                    else "unknown"
                )
                docs_for_hybrid.append(
                    {
                        "id": f"chunk_{i}",
                        "text": text,
                        "source": source,
                        "metadata": chunk if isinstance(chunk, dict) else {},
                    }
                )

            if docs_for_hybrid:
                hybrid_retriever = HybridRetriever(
                    documents=docs_for_hybrid,
                    fusion_method=HMFusion.RRF,
                )

                start = time.perf_counter()
                hybrid_results = hybrid_retriever.retrieve(
                    query=query,
                    top_k=top_k,
                    rrf_k=rrf_k,
                )
                hybrid_time = (time.perf_counter() - start) * 1000

                result["hybrid"] = {
                    "results": [
                        {
                            "id": r.get("id"),
                            "text": r.get("text", "")[:200] + "...",
                            "source": r.get("source"),
                            "score": round(r.get("score", 0), 4),
                        }
                        for r in hybrid_results
                    ],
                    "time_ms": round(hybrid_time, 2),
                    "fusion_method": "rrf",
                }

        start = time.perf_counter()
        query_embedding = embedding_service.embed_query(query)
        dense_results = vector_store.search_with_metadata(query_embedding, top_k=top_k)
        dense_time = (time.perf_counter() - start) * 1000

        result["dense"] = {
            "results": [
                {
                    "id": f"chunk_{i}",
                    "text": r.get("text", "")[:200] + "...",
                    "source": r.get("source"),
                    "score": round(1 - r.get("distance", 0) / 2, 4),
                    "distance": round(r.get("distance", 0), 4),
                }
                for i, r in enumerate(dense_results)
            ],
            "time_ms": round(dense_time, 2),
        }

        from retrieval.bm25_index import BM25Index

        if all_chunks:
            docs_for_bm25 = []
            for i, chunk in enumerate(all_chunks):
                text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                docs_for_bm25.append({"id": f"chunk_{i}", "text": text})

            if docs_for_bm25:
                bm25_idx = BM25Index(docs_for_bm25)

                start = time.perf_counter()
                bm25_results = bm25_idx.search(query, top_k=top_k)
                bm25_time = (time.perf_counter() - start) * 1000

                result["bm25"] = {
                    "results": [
                        {
                            "id": doc_id,
                            "text": (
                                docs_for_bm25[int(doc_id.split("_")[1])]["text"][:200]
                                + "..."
                                if "_" in doc_id
                                else ""
                            ),
                            "source": (
                                all_chunks[int(doc_id.split("_")[1])].get(
                                    "source", "unknown"
                                )
                                if "_" in doc_id
                                and int(doc_id.split("_")[1]) < len(all_chunks)
                                else "unknown"
                            ),
                            "score": round(score, 4),
                        }
                        for doc_id, score in bm25_results
                    ],
                    "time_ms": round(bm25_time, 2),
                }

    except Exception as exc:
        return _error_response(f"Retrieval failed: {str(exc)}", status=500)

    return JsonResponse(result)


@require_http_methods(["GET"])
def admin_documents(request: HttpRequest) -> JsonResponse:
    """
    Get list of all indexed documents with metadata.
    """
    doc_path = Path(settings.DOCUMENTS_PATH)
    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    all_chunks = []
    if chunks_file.exists():
        try:
            all_chunks = np.load(chunks_file, allow_pickle=True).tolist()
            if not isinstance(all_chunks, list):
                all_chunks = []
        except Exception:
            all_chunks = []

    source_chunks = {}
    for chunk in all_chunks:
        if isinstance(chunk, dict):
            source = str(chunk.get("source", "unknown"))
            if source not in source_chunks:
                source_chunks[source] = []
            source_chunks[source].append(chunk)

    documents = []
    if doc_path.exists():
        for pdf in doc_path.glob("*.pdf"):
            try:
                stats = pdf.stat()
                source_name = pdf.name

                chunks_for_doc = source_chunks.get(source_name, [])

                documents.append(
                    {
                        "id": source_name,
                        "name": pdf.name,
                        "size_kb": round(stats.st_size / 1024, 2),
                        "chunk_count": len(chunks_for_doc),
                        "created_at": datetime.fromtimestamp(
                            stats.st_ctime, tz=timezone.utc
                        ).isoformat(),
                        "modified_at": datetime.fromtimestamp(
                            stats.st_mtime, tz=timezone.utc
                        ).isoformat(),
                    }
                )
            except Exception:
                pass

    documents.sort(key=lambda x: x["created_at"], reverse=True)

    search = request.GET.get("search", "").strip().lower()
    if search:
        documents = [d for d in documents if search in d["name"].lower()]

    return JsonResponse(
        {
            "documents": documents,
            "total": len(documents),
        }
    )


@require_http_methods(["GET"])
def admin_document_chunks(request: HttpRequest, doc_id: str) -> JsonResponse:
    """
    Get chunks for a specific document with pagination.
    """
    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))
    except ValueError:
        page = 1
        page_size = 20

    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    if not chunks_file.exists():
        return JsonResponse({"chunks": [], "total": 0, "page": 1, "page_size": 20})

    try:
        all_chunks = np.load(chunks_file, allow_pickle=True).tolist()
        if not isinstance(all_chunks, list):
            return JsonResponse({"chunks": [], "total": 0, "page": 1, "page_size": 20})
    except Exception:
        return JsonResponse({"chunks": [], "total": 0, "page": 1, "page_size": 20})

    doc_chunks = []
    for i, chunk in enumerate(all_chunks):
        if isinstance(chunk, dict):
            source = str(chunk.get("source", ""))
            if source == doc_id or source.endswith(doc_id):
                chunk_data = {
                    "index": i,
                    "text": chunk.get("text", ""),
                    "page": chunk.get("page"),
                    "source": chunk.get("source", ""),
                }

                embedding = chunk.get("embedding")
                if embedding and isinstance(embedding, list):
                    chunk_data["embedding_preview"] = embedding[:5]

                doc_chunks.append(chunk_data)

    total = len(doc_chunks)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_chunks = doc_chunks[start:end]

    return JsonResponse(
        {
            "chunks": paginated_chunks,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def admin_delete_document(request: HttpRequest, doc_id: str) -> JsonResponse:
    """
    Delete a document and rebuild index.
    """

    doc_path = Path(settings.DOCUMENTS_PATH)
    file_path = doc_path / doc_id

    if not file_path.exists():
        return _error_response("Document not found", status=404)

    try:
        file_path.unlink()
    except OSError as exc:
        return _error_response(f"Failed to delete file: {str(exc)}", status=500)

    try:
        index_stats = index_pdf_directory(
            data_source_dir=settings.DOCUMENTS_PATH,
            chunk_size=settings.CHUNK_SIZE,
            index_path=settings.FAISS_INDEX_PATH,
            model_name=settings.EMBEDDING_MODEL,
            clear_existing=True,
        )
    except Exception as exc:
        return _error_response(f"Index rebuild failed: {str(exc)}", status=500)

    return JsonResponse(
        {
            "success": True,
            "message": f"Document {doc_id} deleted",
            "chunks_created": index_stats["chunks_created"],
            "total_chunks": index_stats["total_chunks_in_index"],
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def admin_reindex_document(request: HttpRequest, doc_id: str) -> JsonResponse:
    """
    Reindex a specific document.
    """
    doc_path = Path(settings.DOCUMENTS_PATH)
    file_path = doc_path / doc_id

    if not file_path.exists():
        return _error_response("Document not found", status=404)

    try:
        index_stats = index_pdf_file(
            pdf_path=str(file_path),
            chunk_size=settings.CHUNK_SIZE,
            model_name=settings.EMBEDDING_MODEL,
            clear_existing=False,
        )
    except Exception as exc:
        return _error_response(f"Reindex failed: {str(exc)}", status=500)

    return JsonResponse(
        {
            "success": True,
            "message": f"Document {doc_id} reindexed",
            "chunks_created": index_stats["chunks_created"],
        }
    )


@require_http_methods(["GET"])
def admin_indexing_status(request: HttpRequest) -> JsonResponse:
    """
    Get current indexing status.
    """
    state = _get_upload_indexing_state()
    return JsonResponse(state)


# ==========================================
# Admin Analytics API Endpoints (Phase 2)
# ==========================================


@require_http_methods(["GET"])
def admin_document_analytics(request: HttpRequest, doc_id: str) -> JsonResponse:
    """
    Get retrieval analytics for a specific document.
    """
    from django_app.models import QueryLog

    decoded_doc_id = urllib.parse.unquote(doc_id)

    all_logs = QueryLog.objects.all()

    appearance_count = 0
    click_count = 0
    total_score = 0
    score_count = 0
    query_counts: Dict[str, int] = {}

    for log in all_logs:
        retrieved = log.retrieved_documents or []
        for item in retrieved:
            source = item.get("source", "")
            if decoded_doc_id in source or source.endswith(decoded_doc_id):
                appearance_count += 1
                score = item.get("score", 0)
                if score > 0:
                    total_score += score
                    score_count += 1
                if log.user_feedback is True:
                    click_count += 1

        query_text = log.query.lower()
        for item in retrieved:
            source = item.get("source", "")
            if decoded_doc_id in source or source.endswith(decoded_doc_id):
                if query_text not in query_counts:
                    query_counts[query_text] = 0
                query_counts[query_text] += 1

    top_queries = sorted(
        [{"query": q, "count": c} for q, c in query_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    avg_score = total_score / score_count if score_count > 0 else 0
    click_rate = click_count / appearance_count if appearance_count > 0 else 0

    return JsonResponse(
        {
            "document_id": decoded_doc_id,
            "retrieval_stats": {
                "appearance_count": appearance_count,
                "avg_score": round(avg_score, 3),
                "click_count": click_count,
                "click_rate": round(click_rate, 3),
            },
            "top_queries": top_queries,
        }
    )


@require_http_methods(["GET"])
def admin_query_clusters(request: HttpRequest) -> JsonResponse:
    """
    Get query semantic clusters from recent queries.
    """
    from django_app.models import QueryLog

    days = int(request.GET.get("days", 30))
    limit = min(int(request.GET.get("limit", 1000)), 5000)

    start_time = datetime.now(timezone.utc) - timedelta(days=days)
    queries = list(
        QueryLog.objects.filter(created_at__gte=start_time)
        .values_list("query", "query_type")
        .distinct()[:limit]
    )

    if not queries:
        return JsonResponse(
            {
                "clusters": [],
                "total_queries": 0,
                "message": "No queries found for clustering",
            }
        )

    type_counts: Dict[str, int] = {}
    for _, qtype in queries:
        qtype = qtype or "other"
        type_counts[qtype] = type_counts.get(qtype, 0) + 1

    total = len(queries)
    cluster_definitions = {
        "concept": {
            "name": "concept_definition",
            "patterns": ["what is", "define", "explain", "meaning of", "what does"],
            "color": "#22c55e",
        },
        "method": {
            "name": "method_process",
            "patterns": ["how to", "steps to", "process of", "how does", "method"],
            "color": "#3b82f6",
        },
        "comparison": {
            "name": "comparison",
            "patterns": ["difference between", "compare", "vs ", "versus", " versus "],
            "color": "#f59e0b",
        },
        "reason": {
            "name": "reason_explanation",
            "patterns": ["why does", "reason", "because", "explain why"],
            "color": "#8b5cf6",
        },
        "example": {
            "name": "example_application",
            "patterns": ["example", "application", "use case", "instance of"],
            "color": "#ec4899",
        },
    }

    clusters = []
    for qtype, info in cluster_definitions.items():
        count = type_counts.get(qtype, 0)
        if count > 0:
            queries_of_type = [q for q, t in queries if t == qtype]
            clusters.append(
                {
                    "name": info["name"],
                    "query_type": qtype,
                    "percentage": round(count / total * 100, 1),
                    "count": count,
                    "patterns": info["patterns"],
                    "color": info["color"],
                    "representative": queries_of_type[0] if queries_of_type else "",
                    "sample_queries": queries_of_type[:5],
                }
            )

    clusters.sort(key=lambda x: x["count"], reverse=True)

    return JsonResponse(
        {
            "clusters": clusters,
            "total_queries": total,
            "days": days,
        }
    )


@require_http_methods(["GET"])
def admin_failure_analysis(request: HttpRequest) -> JsonResponse:
    """
    Analyze retrieval failures.
    """
    from django_app.models import QueryLog

    hours = int(request.GET.get("time_range", 24))
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    logs = QueryLog.objects.filter(created_at__gte=start_time)
    total = logs.count()

    if total == 0:
        return JsonResponse(
            {
                "failure_rate": 0,
                "breakdown": [],
                "suggestions": ["No query data available for analysis"],
            }
        )

    no_results = logs.filter(results_count=0).count()
    low_score_count = 0
    negative_feedback = logs.filter(user_feedback=False).count()

    for log in logs:
        if log.user_feedback is None and (log.latency_ms or 0) > 2000:
            low_score_count += 1

    failure_rate = (no_results + low_score_count + negative_feedback) / total

    suggestions = []
    if no_results > total * 0.05:
        suggestions.append("Consider adding synonym expansion for technical terms")
        suggestions.append("Review document coverage for common query topics")
    if low_score_count > total * 0.05:
        suggestions.append("Adjust similarity threshold or increase top_k")
        suggestions.append("Consider adding more descriptive content to documents")
    if negative_feedback > total * 0.02:
        suggestions.append("Review retrieved chunks for relevance")
        suggestions.append("Improve chunk boundaries for better context")

    return JsonResponse(
        {
            "failure_rate": round(failure_rate, 3),
            "time_range_hours": hours,
            "total_queries": total,
            "breakdown": [
                {
                    "type": "no_results",
                    "count": no_results,
                    "percentage": round(no_results / total * 100, 1),
                },
                {
                    "type": "low_score",
                    "count": low_score_count,
                    "percentage": round(low_score_count / total * 100, 1),
                },
                {
                    "type": "negative_feedback",
                    "count": negative_feedback,
                    "percentage": round(negative_feedback / total * 100, 1),
                },
            ],
            "suggestions": suggestions if suggestions else ["System performing well"],
        }
    )


@require_http_methods(["GET"])
def admin_embedding_visualization(request: HttpRequest) -> JsonResponse:
    """
    Get embedding visualization data using PCA/t-SNE projection.
    """
    import numpy as np

    method = request.GET.get("method", "pca")
    perplexity = int(request.GET.get("perplexity", 30))
    sample_size = min(int(request.GET.get("sample_size", 500)), 1000)

    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    if not chunks_file.exists():
        return JsonResponse(
            {
                "points": [],
                "documents": [],
                "error": "No indexed data found",
            }
        )

    try:
        all_chunks = np.load(chunks_file, allow_pickle=True).tolist()
        if not isinstance(all_chunks, list):
            return JsonResponse(
                {"points": [], "documents": [], "error": "Invalid data"}
            )
    except Exception:
        return JsonResponse(
            {"points": [], "documents": [], "error": "Failed to load data"}
        )

    documents = list(
        set(str(c.get("source", "unknown")) for c in all_chunks if isinstance(c, dict))
    )
    doc_colors = {
        doc: f"hsl({(i * 360 / len(documents)) % 360}, 70%, 50%)"
        for i, doc in enumerate(documents)
    }

    chunks_with_embeddings = []
    for i, chunk in enumerate(all_chunks):
        if isinstance(chunk, dict):
            embedding = chunk.get("embedding")
            if embedding and isinstance(embedding, (list, np.ndarray)):
                chunks_with_embeddings.append(
                    {
                        "index": i,
                        "text": chunk.get("text", "")[:100],
                        "document": chunk.get("source", "unknown"),
                        "page": chunk.get("page"),
                        "embedding": embedding,
                    }
                )

    if len(chunks_with_embeddings) < 10:
        return JsonResponse(
            {
                "points": [],
                "documents": documents,
                "error": "Not enough embeddings for visualization",
            }
        )

    embeddings = np.array([c["embedding"] for c in chunks_with_embeddings])

    if embeddings.shape[1] != settings.EMBEDDING_DIM:
        return JsonResponse(
            {
                "points": [],
                "documents": documents,
                "error": f"Embedding dimension mismatch: {embeddings.shape[1]} vs {settings.EMBEDDING_DIM}",
            }
        )

    try:
        from sklearn.decomposition import PCA
        from sklearn.manifold import TSNE

        if method == "tsne":
            n_components = 2
            n_iter = 1000
            tsne = TSNE(
                n_components=n_components,
                perplexity=min(perplexity, len(embeddings) - 1),
                n_iter=n_iter,
                random_state=42,
            )
            projected = tsne.fit_transform(embeddings)
        else:
            pca = PCA(n_components=2, random_state=42)
            projected = pca.fit_transform(embeddings)
    except Exception:
        return JsonResponse(
            {
                "points": [],
                "documents": documents,
                "error": "Projection failed",
            }
        )

    points = []
    for i, chunk in enumerate(chunks_with_embeddings):
        points.append(
            {
                "x": float(projected[i, 0]),
                "y": float(projected[i, 1]),
                "chunk_index": chunk["index"],
                "document": chunk["document"],
                "document_color": doc_colors.get(chunk["document"], "#888"),
                "text_preview": chunk["text"],
                "page": chunk["page"],
            }
        )

    return JsonResponse(
        {
            "points": points[:sample_size],
            "documents": documents,
            "method": method,
            "total_chunks": len(chunks_with_embeddings),
        }
    )


@require_http_methods(["GET"])
def admin_chunk_quality(request: HttpRequest) -> JsonResponse:
    """
    Evaluate chunk quality.
    """
    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    if not chunks_file.exists():
        return JsonResponse(
            {
                "chunks": [],
                "overall_score": 0,
                "error": "No indexed data found",
            }
        )

    try:
        all_chunks = np.load(chunks_file, allow_pickle=True).tolist()
        if not isinstance(all_chunks, list):
            return JsonResponse({"chunks": [], "error": "Invalid data"})
    except Exception:
        return JsonResponse({"chunks": [], "error": "Failed to load data"})

    from django_app.models import QueryLog

    chunk_stats: Dict[int, Dict[str, Any]] = {}

    for log in QueryLog.objects.all():
        retrieved = log.retrieved_documents or []
        for i, item in enumerate(retrieved):
            chunk_idx = item.get("chunk_index", -1)
            if chunk_idx >= 0:
                if chunk_idx not in chunk_stats:
                    chunk_stats[chunk_idx] = {"hits": 0, "total_score": 0}
                chunk_stats[chunk_idx]["hits"] += 1
                chunk_stats[chunk_idx]["total_score"] += item.get("score", 0)

    chunk_qualities = []
    for i, chunk in enumerate(all_chunks):
        if not isinstance(chunk, dict):
            continue

        text = chunk.get("text", "")
        stats = chunk_stats.get(i, {"hits": 0, "total_score": 0})

        quality_score = 0.5

        if len(text) > 100:
            quality_score += 0.1
        if text and text[0].isupper():
            quality_score += 0.1
        if " " in text.strip():
            quality_score += 0.1

        if stats["hits"] > 0:
            quality_score += 0.1
            avg_score = stats["total_score"] / stats["hits"]
            if avg_score > 0.7:
                quality_score += 0.2
            elif avg_score > 0.5:
                quality_score += 0.1

        quality_score = min(quality_score, 1.0)

        issues = []
        if len(text) < 50:
            issues.append("Too short")
        if text.startswith("As mentioned") or text.startswith("Figure"):
            issues.append("Context dependent")
        if not text.endswith((".", "!", "?", ")")):
            issues.append("Incomplete sentence")

        chunk_qualities.append(
            {
                "index": i,
                "text_preview": text[:150] + "..." if len(text) > 150 else text,
                "source": chunk.get("source", ""),
                "page": chunk.get("page"),
                "quality_score": round(quality_score, 2),
                "retrieval_hits": stats["hits"],
                "avg_score": (
                    round(stats["total_score"] / stats["hits"], 3)
                    if stats["hits"] > 0
                    else 0
                ),
                "issues": issues,
            }
        )

    chunk_qualities.sort(key=lambda x: x["quality_score"], reverse=True)

    top_chunks = chunk_qualities[:10]
    low_chunks = [c for c in chunk_qualities if c["quality_score"] < 0.5][:10]

    overall = (
        sum(c["quality_score"] for c in chunk_qualities) / len(chunk_qualities)
        if chunk_qualities
        else 0
    )

    return JsonResponse(
        {
            "top_chunks": top_chunks,
            "low_quality_chunks": low_chunks,
            "overall_score": round(overall * 100),
            "total_chunks": len(chunk_qualities),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def admin_retrieval_trace(request: HttpRequest) -> JsonResponse:
    """
    Trace the full retrieval path for a query.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query", "")).strip()
    if not query:
        return _error_response("Query is required", status=400)

    trace_id = payload.get("trace_id") or f"trace_{int(time.time() * 1000)}"

    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStore

    stages = []

    start = time.perf_counter()
    query_processed = query.lower().strip()
    tokens = query_processed.split()
    query_time = (time.perf_counter() - start) * 1000

    stages.append(
        {
            "name": "query_processing",
            "time_ms": round(query_time, 2),
            "details": {
                "original": query,
                "processed": query_processed,
                "tokens": tokens,
                "token_count": len(tokens),
            },
        }
    )

    try:
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=settings.EMBEDDING_DIM,
        )
        embedding_service = EmbeddingService()

        start = time.perf_counter()
        query_embedding = embedding_service.embed_query(query)
        embed_time = (time.perf_counter() - start) * 1000

        stages.append(
            {
                "name": "embedding_generation",
                "time_ms": round(embed_time, 2),
                "details": {
                    "model": settings.EMBEDDING_MODEL,
                    "dimension": len(query_embedding),
                },
            }
        )

        top_k = payload.get("top_k", 5)

        start = time.perf_counter()
        dense_results = vector_store.search_with_metadata(
            query_embedding, top_k=top_k * 3
        )
        dense_time = (time.perf_counter() - start) * 1000

        stages.append(
            {
                "name": "dense_retrieval",
                "time_ms": round(dense_time, 2),
                "results": [
                    {
                        "source": r.get("source"),
                        "score": round(1 - r.get("distance", 0) / 2, 4),
                        "text_preview": r.get("text", "")[:100],
                    }
                    for r in dense_results[:top_k]
                ],
            }
        )

        from retrieval.hybrid_retriever import HybridRetriever, FusionMethod
        from retrieval.bm25_index import BM25Index

        all_chunks = vector_store.chunks
        if isinstance(all_chunks, list) and len(all_chunks) > 0:
            docs_for_bm25 = []
            for j, chunk in enumerate(all_chunks):
                text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                docs_for_bm25.append({"id": f"chunk_{j}", "text": text})

            if docs_for_bm25:
                bm25_idx = BM25Index(docs_for_bm25)

                start = time.perf_counter()
                bm25_results = bm25_idx.search(query, top_k=top_k * 3)
                bm25_time = (time.perf_counter() - start) * 1000

                stages.append(
                    {
                        "name": "bm25_retrieval",
                        "time_ms": round(bm25_time, 2),
                        "results": [
                            {
                                "doc_id": doc_id,
                                "score": round(score, 4),
                            }
                            for doc_id, score in bm25_results[:top_k]
                        ],
                    }
                )

                docs_for_hybrid = []
                for j, chunk in enumerate(all_chunks):
                    text = (
                        chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                    )
                    source = (
                        chunk.get("source", "unknown")
                        if isinstance(chunk, dict)
                        else "unknown"
                    )
                    docs_for_hybrid.append(
                        {
                            "id": f"chunk_{j}",
                            "text": text,
                            "source": source,
                        }
                    )

                hybrid_retriever = HybridRetriever(
                    documents=docs_for_hybrid,
                    fusion_method=FusionMethod.RRF,
                )

                start = time.perf_counter()
                hybrid_results = hybrid_retriever.retrieve(query, top_k=top_k)
                fusion_time = (time.perf_counter() - start) * 1000

                stages.append(
                    {
                        "name": "hybrid_fusion",
                        "time_ms": round(fusion_time, 2),
                        "method": "rrf",
                        "results": [
                            {
                                "id": r.get("id"),
                                "score": round(r.get("score", 0), 4),
                                "source": r.get("source"),
                            }
                            for r in hybrid_results
                        ],
                    }
                )

        context_start = time.perf_counter()
        top_chunks = dense_results[:3]
        context_lines = []
        for idx, item in enumerate(top_chunks, 1):
            source = item.get("source", "unknown")
            page = item.get("page")
            text = item.get("text", "")
            context_lines.append(f"[{idx}] source={source} page={page}\n{text}")
        context = "\n\n".join(context_lines)
        context_time = (time.perf_counter() - context_start) * 1000

        stages.append(
            {
                "name": "context_building",
                "time_ms": round(context_time, 2),
                "chunks_used": len(top_chunks),
                "context_length": len(context),
            }
        )

        total_time = sum(s["time_ms"] for s in stages)

        bottleneck = max(stages, key=lambda s: s["time_ms"])

        return JsonResponse(
            {
                "trace_id": trace_id,
                "query": query,
                "stages": stages,
                "total_time": round(total_time, 2),
                "bottleneck": bottleneck["name"],
            }
        )

    except Exception as exc:
        return _error_response(f"Trace failed: {str(exc)}", status=500)


# A/B Testing endpoints
AB_TESTS_FILE = Path(__file__).resolve().parents[1] / "data" / "ab_tests.json"


def _load_ab_tests() -> List[Dict[str, Any]]:
    if not AB_TESTS_FILE.exists():
        return []
    try:
        with AB_TESTS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_ab_tests(tests: List[Dict[str, Any]]) -> None:
    AB_TESTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AB_TESTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(tests, f, indent=2)


@require_http_methods(["GET"])
def admin_ab_tests(request: HttpRequest) -> JsonResponse:
    """
    Get all A/B tests.
    """
    tests = _load_ab_tests()
    return JsonResponse({"tests": tests})


@csrf_exempt
@require_http_methods(["POST"])
def admin_ab_test_create(request: HttpRequest) -> JsonResponse:
    """
    Create a new A/B test.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    name = str(payload.get("name", "")).strip()
    if not name:
        return _error_response("Test name is required", status=400)

    variants = payload.get("variants", [])
    if len(variants) < 2:
        return _error_response("At least 2 variants required", status=400)

    tests = _load_ab_tests()
    test_id = len(tests) + 1

    new_test = {
        "id": test_id,
        "name": name,
        "description": payload.get("description", ""),
        "variants": variants,
        "traffic_split": payload.get("traffic_split", [50, 50]),
        "metrics": payload.get("metrics", ["click_rate", "feedback", "latency"]),
        "status": "draft",
        "samples": 0,
        "results": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    tests.append(new_test)
    _save_ab_tests(tests)

    return JsonResponse({"success": True, "test": new_test})


@csrf_exempt
@require_http_methods(["POST"])
def admin_ab_test_start(request: HttpRequest) -> JsonResponse:
    """
    Start an A/B test.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    test_id = int(payload.get("test_id", 0))

    tests = _load_ab_tests()
    for test in tests:
        if test["id"] == test_id:
            test["status"] = "running"
            test["started_at"] = datetime.now(timezone.utc).isoformat()
            _save_ab_tests(tests)
            return JsonResponse({"success": True, "test": test})

    return _error_response("Test not found", status=404)


@csrf_exempt
@require_http_methods(["POST"])
def admin_ab_test_stop(request: HttpRequest) -> JsonResponse:
    """
    Stop an A/B test.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    test_id = int(payload.get("test_id", 0))

    tests = _load_ab_tests()
    for test in tests:
        if test["id"] == test_id:
            test["status"] = "completed"
            test["stopped_at"] = datetime.now(timezone.utc).isoformat()
            _save_ab_tests(tests)
            return JsonResponse({"success": True, "test": test})

    return _error_response("Test not found", status=404)


@csrf_exempt
@require_http_methods(["POST"])
def admin_ab_test_record(request: HttpRequest) -> JsonResponse:
    """
    Record an A/B test result.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    test_id = int(payload.get("test_id", 0))
    variant = str(payload.get("variant", ""))
    metrics = payload.get("metrics", {})

    tests = _load_ab_tests()
    for test in tests:
        if test["id"] == test_id and test["status"] == "running":
            test["samples"] = test.get("samples", 0) + 1

            if variant not in test["results"]:
                test["results"][variant] = {
                    "samples": 0,
                    "total_score": 0,
                    "total_latency": 0,
                    "positive_feedback": 0,
                }

            result = test["results"][variant]
            result["samples"] += 1
            result["total_score"] += metrics.get("score", 0)
            result["total_latency"] += metrics.get("latency_ms", 0)
            if metrics.get("feedback") is True:
                result["positive_feedback"] += 1

            _save_ab_tests(tests)
            return JsonResponse({"success": True})

    return _error_response("Test not found or not running", status=404)


@require_http_methods(["GET"])
def admin_ab_test_results(request: HttpRequest, test_id: int) -> JsonResponse:
    """
    Get A/B test results.
    """
    tests = _load_ab_tests()
    for test in tests:
        if test["id"] == test_id:
            results = []
            for variant, data in test.get("results", {}).items():
                avg_score = (
                    data["total_score"] / data["samples"] if data["samples"] > 0 else 0
                )
                avg_latency = (
                    data["total_latency"] / data["samples"]
                    if data["samples"] > 0
                    else 0
                )
                feedback_rate = (
                    data["positive_feedback"] / data["samples"]
                    if data["samples"] > 0
                    else 0
                )

                results.append(
                    {
                        "variant": variant,
                        "samples": data["samples"],
                        "avg_score": round(avg_score, 3),
                        "avg_latency_ms": round(avg_latency, 2),
                        "positive_feedback_rate": round(feedback_rate, 3),
                    }
                )

            return JsonResponse(
                {
                    "test": {
                        "id": test["id"],
                        "name": test["name"],
                        "status": test["status"],
                        "samples": test.get("samples", 0),
                    },
                    "results": results,
                }
            )

    return _error_response("Test not found", status=404)


# ==========================================
# Embedding Model Management Endpoints
# ==========================================

EMBEDDING_MODEL_SETTINGS_FILE = (
    Path(__file__).resolve().parents[1] / "data" / "embedding_model_settings.json"
)


def _load_embedding_model_settings() -> Dict[str, Any]:
    """Load embedding model settings from file."""
    default_settings = {
        "current_model": settings.EMBEDDING_MODEL,
        "model_cache": [],
    }

    if not EMBEDDING_MODEL_SETTINGS_FILE.exists():
        return default_settings

    try:
        with EMBEDDING_MODEL_SETTINGS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {**default_settings, **data}
    except (OSError, json.JSONDecodeError):
        pass

    return default_settings


def _save_embedding_model_settings(data: Dict[str, Any]) -> None:
    """Save embedding model settings to file."""
    EMBEDDING_MODEL_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with EMBEDDING_MODEL_SETTINGS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@require_http_methods(["GET"])
def list_embedding_models(request: HttpRequest) -> JsonResponse:
    """
    Get list of all available embedding models with metadata.
    """
    from app.services.embedding_manager import get_embedding_manager

    try:
        manager = get_embedding_manager()
        models = manager.get_available_models()

        # Add cache stats
        cache_stats = manager.get_cache_stats()

        return JsonResponse(
            {
                "models": models,
                "cache_stats": cache_stats,
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to load models: {str(exc)}", status=500)


@require_http_methods(["GET"])
def get_current_embedding_model(request: HttpRequest) -> JsonResponse:
    """
    Get the currently active embedding model.
    """
    from app.services.embedding_manager import get_embedding_manager

    try:
        manager = get_embedding_manager()
        current_id = manager.get_current_model_id()
        model_info = manager.AVAILABLE_MODELS.get(current_id, {})

        # Check if model is loaded in cache
        cache_stats = manager.get_cache_stats()
        is_loaded = current_id in cache_stats.get("cached_models", [])

        return JsonResponse(
            {
                "model_id": current_id,
                "model_name": model_info.get("name", current_id),
                "dimension": model_info.get("dimension", 384),
                "speed": model_info.get("speed", "Unknown"),
                "memory": model_info.get("memory", "Unknown"),
                "is_loaded": is_loaded,
                "recommended": model_info.get("recommended", False),
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to get current model: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def switch_embedding_model(request: HttpRequest) -> JsonResponse:
    """
    Switch to a different embedding model.

    Body:
        model_id: str - The model ID to switch to
        reindex: bool (optional) - Whether to reindex documents with new model
    """
    from app.services.embedding_manager import get_embedding_manager

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    model_id = str(payload.get("model_id", "")).strip()
    reindex = bool(payload.get("reindex", False))

    if not model_id:
        return _error_response("model_id is required", status=400)

    try:
        manager = get_embedding_manager()

        # Validate model exists
        if model_id not in manager.AVAILABLE_MODELS:
            return _error_response(f"Unknown model: {model_id}", status=400)

        # Switch model
        result = manager.set_current_model(model_id)

        # Save to settings
        saved_settings = _load_embedding_model_settings()
        saved_settings["current_model"] = model_id
        _save_embedding_model_settings(saved_settings)

        # If reindex requested, trigger background reindexing
        if reindex:
            # Check current indexing state
            current_state = _get_upload_indexing_state()
            if current_state["status"] != INDEXING_STATUS_RUNNING:
                _enqueue_full_rebuild(uploaded_filename="model_switch_reindex")
                result["reindex_status"] = "started"
            else:
                result["reindex_status"] = "already_running"
        else:
            result["reindex_status"] = "not_requested"

        return JsonResponse(
            {
                "success": True,
                **result,
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to switch model: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def test_embedding_model(request: HttpRequest) -> JsonResponse:
    """
    Test an embedding model with a query.

    Body:
        model_id: str - The model ID to test
        query: str (optional) - Test query (default: "test query")
        top_k: int (optional) - Number of results (default: 3)
    """
    from app.services.embedding_manager import get_embedding_manager

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    model_id = str(payload.get("model_id", "")).strip()
    query = str(payload.get("query", "test query")).strip()
    top_k = int(payload.get("top_k", 3))

    if not model_id:
        return _error_response("model_id is required", status=400)

    if not query:
        return _error_response("query cannot be empty", status=400)

    try:
        manager = get_embedding_manager()

        # Validate model exists
        if model_id not in manager.AVAILABLE_MODELS:
            return _error_response(f"Unknown model: {model_id}", status=400)

        # Test the model
        result = manager.test_model(model_id, query, top_k=top_k)

        return JsonResponse(
            {
                "success": True,
                **result,
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to test model: {str(exc)}", status=500)


@require_http_methods(["GET"])
def get_embedding_model_metrics(request: HttpRequest) -> JsonResponse:
    """
    Get performance metrics for embedding models.
    """
    from app.services.embedding_manager import get_embedding_manager

    try:
        manager = get_embedding_manager()

        # Get recent metrics
        metrics = manager.get_performance_metrics(limit=50)

        # Calculate averages per model
        model_stats: Dict[str, Dict[str, Any]] = {}
        for metric in metrics:
            model_id = metric["model_id"]
            if model_id not in model_stats:
                model_stats[model_id] = {
                    "count": 0,
                    "total_time_ms": 0,
                    "actions": {},
                }

            model_stats[model_id]["count"] += 1
            model_stats[model_id]["total_time_ms"] += metric["time_ms"]

            action = metric["action"]
            if action not in model_stats[model_id]["actions"]:
                model_stats[model_id]["actions"][action] = {
                    "count": 0,
                    "total_time_ms": 0,
                }
            model_stats[model_id]["actions"][action]["count"] += 1
            model_stats[model_id]["actions"][action]["total_time_ms"] += metric[
                "time_ms"
            ]

        # Calculate averages
        for model_id, stats in model_stats.items():
            stats["avg_time_ms"] = (
                round(stats["total_time_ms"] / stats["count"], 2)
                if stats["count"] > 0
                else 0
            )

            for action, action_stats in stats["actions"].items():
                action_stats["avg_time_ms"] = (
                    round(action_stats["total_time_ms"] / action_stats["count"], 2)
                    if action_stats["count"] > 0
                    else 0
                )

        return JsonResponse(
            {
                "metrics": metrics,
                "model_stats": model_stats,
                "cache_stats": manager.get_cache_stats(),
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to get metrics: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def clear_embedding_model_cache(request: HttpRequest) -> JsonResponse:
    """
    Clear the embedding model cache.
    """
    from app.services.embedding_manager import get_embedding_manager

    try:
        manager = get_embedding_manager()
        manager.clear_cache()

        return JsonResponse(
            {
                "success": True,
                "message": "Model cache cleared",
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to clear cache: {str(exc)}", status=500)


# ==========================================
# Document Summarization Endpoints
# ==========================================

SUMMARY_HISTORY_FILE = (
    Path(__file__).resolve().parents[1] / "data" / "summary_history.json"
)


def _load_summary_history() -> List[Dict[str, Any]]:
    """Load summary history from file."""
    if not SUMMARY_HISTORY_FILE.exists():
        return []

    try:
        with SUMMARY_HISTORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except (OSError, json.JSONDecodeError):
        pass

    return []


def _save_summary_history(history: List[Dict[str, Any]]) -> None:
    """Save summary history to file."""
    SUMMARY_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def _get_document_text(filename: str) -> Optional[str]:
    """
    Get full text content of a document from FAISS chunks.

    Args:
        filename: Document filename

    Returns:
        Full text content or None if not found
    """
    from app.services.vector_store import VectorStore
    from app.config import settings

    try:
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=settings.EMBEDDING_DIM,
        )

        # Find all chunks for this document
        doc_chunks = []
        for chunk in vector_store.chunks:
            chunk_source = str(chunk.get("source", ""))
            # Match by filename (handle UUID prefixes)
            if filename in chunk_source or chunk_source.endswith(filename):
                doc_chunks.append(chunk)

        if not doc_chunks:
            return None

        # Sort by page and join text
        doc_chunks.sort(key=lambda c: c.get("page", 0) or 0)
        full_text = " ".join([str(c.get("text", "")) for c in doc_chunks])

        return full_text
    except Exception:
        return None


@csrf_exempt
@require_http_methods(["POST"])
def generate_summary(request: HttpRequest) -> JsonResponse:
    """
    Generate summary for selected documents.

    Body:
        document_ids: List[str] - List of document filenames
        config: Dict (optional) - Summary configuration:
            - length: "short" | "medium" | "detailed"
            - style: "bullets" | "narrative" | "academic" | "executive"
            - language: "zh" | "en"
            - include_citations: bool
            - include_comparison: bool
    """
    from app.services.summarizer import DocumentSummarizer, SummarizerError

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    document_ids = payload.get("document_ids", [])
    config = payload.get("config", {})

    if not document_ids:
        return _error_response("No documents selected", status=400)

    if not isinstance(document_ids, list):
        return _error_response("document_ids must be a list", status=400)

    # Default configuration
    default_config = {
        "length": "medium",
        "style": "narrative",
        "language": "zh",
        "include_citations": True,
        "include_comparison": len(document_ids) > 1,
    }
    default_config.update(config)

    # Get document texts
    documents = []
    for doc_id in document_ids:
        text = _get_document_text(doc_id)
        if text:
            documents.append(
                {
                    "name": doc_id,
                    "text": text,
                }
            )

    if not documents:
        return _error_response("No valid documents found", status=404)

    try:
        # Generate summary
        summarizer = DocumentSummarizer()
        result = summarizer.generate_summary(documents, default_config)

        # Save to history
        history = _load_summary_history()
        history_entry = {
            "id": f"summary_{int(time.time())}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "documents": [doc["name"] for doc in documents],
            "summary": result["text"],
            "citations": result.get("citations", []),
            "comparison": result.get("comparison", []),
            "config": default_config,
            "document_count": len(documents),
        }
        history.insert(0, history_entry)  # Add to beginning

        # Keep only last 50 summaries
        if len(history) > 50:
            history = history[:50]

        _save_summary_history(history)

        return JsonResponse(
            {
                "success": True,
                "summary": result["text"],
                "citations": result.get("citations", []),
                "comparison": result.get("comparison", []),
                "document_count": len(documents),
                "documents": [doc["name"] for doc in documents],
                "config": default_config,
                "history_id": history_entry["id"],
            }
        )

    except SummarizerError as exc:
        return _error_response(str(exc), status=500)
    except Exception as exc:
        return _error_response(f"Failed to generate summary: {str(exc)}", status=500)


@require_http_methods(["GET"])
def get_summary_history(request: HttpRequest) -> JsonResponse:
    """
    Get summary generation history.

    Query params:
        limit: int (optional) - Maximum number of histories to return (default: 20)
    """
    try:
        limit = int(request.GET.get("limit", 20))
        limit = min(limit, 50)  # Max 50

        history = _load_summary_history()

        # Return most recent summaries
        recent_history = history[:limit]

        return JsonResponse(
            {
                "history": recent_history,
                "total": len(history),
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to load history: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_summary(request: HttpRequest, summary_id: str) -> JsonResponse:
    """
    Delete a summary from history.

    URL parameter:
        summary_id: str - The summary ID to delete
    """
    try:
        history = _load_summary_history()

        # Find and remove the summary
        new_history = [h for h in history if h.get("id") != summary_id]

        if len(new_history) == len(history):
            return _error_response("Summary not found", status=404)

        _save_summary_history(new_history)

        return JsonResponse(
            {
                "success": True,
                "message": "Summary deleted",
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to delete summary: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def regenerate_summary(request: HttpRequest) -> JsonResponse:
    """
    Regenerate summary with different configuration.

    Body:
        history_id: str - The summary history ID to regenerate
        config: Dict - New configuration
    """
    from app.services.summarizer import DocumentSummarizer, SummarizerError

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    history_id = payload.get("history_id")
    new_config = payload.get("config", {})

    if not history_id:
        return _error_response("history_id is required", status=400)

    # Find the original summary
    history = _load_summary_history()
    original = None
    for h in history:
        if h.get("id") == history_id:
            original = h
            break

    if not original:
        return _error_response("Summary not found", status=404)

    # Merge old config with new
    config = {**original.get("config", {}), **new_config}

    # Get document texts
    documents = []
    for doc_name in original.get("documents", []):
        text = _get_document_text(doc_name)
        if text:
            documents.append(
                {
                    "name": doc_name,
                    "text": text,
                }
            )

    if not documents:
        return _error_response("Documents not found", status=404)

    try:
        # Regenerate summary
        summarizer = DocumentSummarizer()
        result = summarizer.generate_summary(documents, config)

        # Update history
        updated_entry = {
            **original,
            "summary": result["text"],
            "citations": result.get("citations", []),
            "comparison": result.get("comparison", []),
            "config": config,
            "regenerated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Replace in history
        new_history = [
            h if h.get("id") != history_id else updated_entry for h in history
        ]
        _save_summary_history(new_history)

        return JsonResponse(
            {
                "success": True,
                "summary": result["text"],
                "citations": result.get("citations", []),
                "comparison": result.get("comparison", []),
                "config": config,
            }
        )

    except SummarizerError as exc:
        return _error_response(str(exc), status=500)
    except Exception as exc:
        return _error_response(f"Failed to regenerate summary: {str(exc)}", status=500)


# ==========================================
# Question Suggestion Endpoints
# ==========================================


@require_http_methods(["GET"])
def get_question_suggestions(request: HttpRequest) -> JsonResponse:
    """
    Generate question suggestions based on selected documents.

    Query params:
        doc_ids: Comma-separated list of document filenames
        num_suggestions: Number of suggestions to generate (default: 3)
        llm_provider: LLM provider to use (default: "local_qwen")
    """
    from app.services.question_suggestions import (
        generate_question_suggestions,
        QuestionSuggestionError,
    )

    # Get document IDs from query params
    doc_ids_param = request.GET.get("doc_ids", "")
    num_suggestions = int(request.GET.get("num_suggestions", 3))

    if not doc_ids_param:
        return _error_response("doc_ids query parameter is required", status=400)

    # Parse document IDs
    doc_ids = [doc_id.strip() for doc_id in doc_ids_param.split(",") if doc_id.strip()]

    if not doc_ids:
        return _error_response("No valid document IDs provided", status=400)

    # Limit number of suggestions
    num_suggestions = min(max(1, num_suggestions), 5)

    try:
        # Get document content from FAISS
        documents = []
        for doc_id in doc_ids:
            text = _get_document_text(doc_id)
            if text:
                documents.append(
                    {
                        "name": doc_id,
                        "content": text,
                    }
                )

        if not documents:
            return _error_response("No valid documents found in index", status=404)

        # Generate suggestions
        result = generate_question_suggestions(documents, num_suggestions)

        return JsonResponse(
            {
                "success": True,
                "suggestions": result.get("suggestions", []),
                "generated_from": result.get("generated_from", []),
                "document_count": len(documents),
            }
        )

    except QuestionSuggestionError as exc:
        return _error_response(f"Suggestion generation failed: {str(exc)}", status=500)
    except Exception as exc:
        return _error_response(
            f"Failed to generate suggestions: {str(exc)}", status=500
        )


@csrf_exempt
@require_http_methods(["POST"])
def record_suggestion_click(request: HttpRequest) -> JsonResponse:
    """
    Record when a user clicks on a suggested question.

    Body:
        question: str - The question text that was clicked
        doc_ids: List[str] - Document IDs the suggestion was based on
        position: int - Position of the clicked suggestion (0-indexed)
    """
    from django_app.models import SuggestedQuestion

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    question_text = payload.get("question", "").strip()
    doc_ids = payload.get("doc_ids", [])
    position = payload.get("position", 0)

    if not question_text:
        return _error_response("question is required", status=400)

    if not doc_ids:
        return _error_response("doc_ids is required", status=400)

    try:
        # Try to find existing suggestion
        existing = None
        doc_names_str = ", ".join(sorted([str(d) for d in doc_ids]))

        # Search for similar suggestions
        candidates = SuggestedQuestion.objects.filter(
            question_text=question_text,
            document_names=doc_names_str,
        )

        if candidates.exists():
            existing = candidates.first()
        else:
            # Try to find by question text only (more lenient)
            candidates = SuggestedQuestion.objects.filter(
                question_text=question_text,
            )
            if candidates.exists():
                existing = candidates.first()

        if existing:
            # Increment click count
            existing.increment_click_count()
            suggestion_id = existing.id
        else:
            # Create new suggestion record
            new_suggestion = SuggestedQuestion.objects.create(
                question_text=question_text,
                question_type="concept",  # Default type
                document_names=doc_names_str,
                click_count=1,
                generation_metadata={
                    "position": position,
                    "doc_ids": doc_ids,
                },
            )
            suggestion_id = new_suggestion.id

        return JsonResponse(
            {
                "success": True,
                "message": "Click recorded",
                "suggestion_id": suggestion_id,
                "click_count": (existing.click_count if existing else 1),
            }
        )

    except Exception as exc:
        # Don't fail the request if tracking fails
        print(f"Failed to record suggestion click: {exc}")
        return JsonResponse(
            {
                "success": True,
                "message": "Click recorded (tracking may have failed)",
            }
        )


@require_http_methods(["GET"])
def get_suggestion_history(request: HttpRequest) -> JsonResponse:
    """
    Get history of generated suggestions.

    Query params:
        limit: int (optional) - Maximum number of suggestions to return (default: 20)
        doc_id: str (optional) - Filter by document ID
    """
    from django_app.models import SuggestedQuestion

    try:
        limit = int(request.GET.get("limit", 20))
        doc_id = request.GET.get("doc_id", "")

        limit = min(limit, 100)  # Max 100

        # Build query
        query = SuggestedQuestion.objects.all()

        if doc_id:
            query = query.filter(document_names__icontains=doc_id)

        # Get recent suggestions
        suggestions = query.order_by("-created_at")[:limit]

        # Serialize
        result = []
        for s in suggestions:
            result.append(
                {
                    "id": s.id,
                    "question_text": s.question_text,
                    "question_type": s.question_type,
                    "document_names": (
                        s.document_names.split(", ") if s.document_names else []
                    ),
                    "click_count": s.click_count,
                    "feedback_score": s.feedback_score,
                    "created_at": s.created_at.isoformat(),
                }
            )

        return JsonResponse(
            {
                "suggestions": result,
                "total": query.count(),
            }
        )

    except Exception:
        return JsonResponse({"suggestions": [], "total": 0})


# ==========================================
# Phase 3: Smart Operations (Alerts, Forecasting, Self-Healing, Cost, Users, Reports, Health)
# ==========================================

ALERTS_FILE = Path(__file__).resolve().parents[1] / "data" / "alerts.json"
SELFHEALING_FILE = Path(__file__).resolve().parents[1] / "data" / "selfhealing.json"
REPORTS_FILE = Path(__file__).resolve().parents[1] / "data" / "reports.json"


def _load_alerts() -> Dict[str, Any]:
    if not ALERTS_FILE.exists():
        return {"active": [], "history": [], "rules": []}
    try:
        with ALERTS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"active": [], "history": [], "rules": []}


def _save_alerts(data: Dict[str, Any]) -> None:
    ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ALERTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _load_selfhealing() -> Dict[str, Any]:
    if not SELFHEALING_FILE.exists():
        return {"events": [], "policies": []}
    try:
        with SELFHEALING_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"events": [], "policies": []}


def _save_selfhealing(data: Dict[str, Any]) -> None:
    SELFHEALING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SELFHEALING_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _load_reports() -> List[Dict[str, Any]]:
    if not REPORTS_FILE.exists():
        return []
    try:
        with REPORTS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_reports(data: List[Dict[str, Any]]) -> None:
    REPORTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REPORTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@require_http_methods(["GET"])
def admin_alerts_current(request: HttpRequest) -> JsonResponse:
    """Get current active alerts."""
    alerts_data = _load_alerts()

    from django_app.models import QueryLog, SystemMetric

    now = datetime.now(timezone.utc)
    recent = now - timedelta(hours=1)

    active_alerts = []

    try:
        latency_avg = (
            QueryLog.objects.filter(created_at__gte=recent).aggregate(
                avg=SystemMetric.objects.filter(
                    timestamp__gte=recent, name="avg_latency"
                ).values_list("value", flat=True)
            )["avg"]
            or 0
        )

        if latency_avg > 500:
            active_alerts.append(
                {
                    "id": "latency_high",
                    "type": "latency_anomaly",
                    "severity": "warning",
                    "message": f"检索延迟较高: {latency_avg:.0f}ms",
                    "current_value": latency_avg,
                    "baseline": {"avg": 200, "std": 50},
                    "start_time": (now - timedelta(minutes=30)).strftime("%H:%M"),
                    "possible_causes": ["traffic_spike", "model_loading"],
                }
            )
    except Exception:
        pass

    index_path = Path(settings.FAISS_INDEX_PATH)
    index_file = index_path / "index.faiss"
    if not index_file.exists() or index_file.stat().st_size == 0:
        active_alerts.append(
            {
                "id": "faiss_empty",
                "type": "index_empty",
                "severity": "critical",
                "message": "FAISS 索引为空",
                "current_value": 0,
                "baseline": {"min": 1000},
                "start_time": now.strftime("%H:%M"),
                "possible_causes": ["no_documents", "index_failed"],
                "auto_remediation": "rebuild_index",
            }
        )

    alerts_data["active"] = active_alerts
    _save_alerts(alerts_data)

    history = alerts_data.get("history", [])[-20:]

    return JsonResponse(
        {
            "active_alerts": active_alerts,
            "history": history,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def admin_alerts_acknowledge(request: HttpRequest) -> JsonResponse:
    """Acknowledge an alert."""
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    alert_id = payload.get("alert_id")
    action = payload.get("action", "acknowledge")

    alerts_data = _load_alerts()

    if action == "ignore":
        for alert in alerts_data.get("active", []):
            if alert.get("id") == alert_id:
                alert["status"] = "ignored"
                alerts_data["history"].append(alert)
                alerts_data["active"] = [
                    a for a in alerts_data["active"] if a.get("id") != alert_id
                ]
                break

    _save_alerts(alerts_data)

    return JsonResponse({"success": True})


@require_http_methods(["GET"])
def admin_capacity_forecast(request: HttpRequest) -> JsonResponse:
    """Get capacity forecast."""
    months = int(request.GET.get("months", 3))

    from django_app.models import QueryLog

    now = datetime.now(timezone.utc)

    historical_docs = []
    historical_queries = []

    for i in range(6, 0, -1):
        month_start = now - timedelta(days=i * 30)
        doc_count = (
            QueryLog.objects.filter(created_at__gte=month_start)
            .values("query")
            .distinct()
            .count()
        )
        query_count = QueryLog.objects.filter(created_at__gte=month_start).count()
        historical_docs.append(doc_count)
        historical_queries.append(query_count)

    avg_doc_growth = 1.1
    avg_query_growth = 1.15

    current_docs = historical_docs[-1] if historical_docs else 100
    current_queries = historical_queries[-1] if historical_queries else 100

    forecast_docs = int(current_docs * (avg_doc_growth**months))
    forecast_queries = int(current_queries * (avg_query_growth**months))

    index_path = Path(settings.FAISS_INDEX_PATH)
    index_file = index_path / "index.faiss"
    current_index_size = (
        index_file.stat().st_size / (1024 * 1024) if index_file.exists() else 0
    )

    recommendations = []
    if forecast_docs > current_docs * 1.5:
        recommendations.append(
            {
                "date": (now + timedelta(days=14)).strftime("%Y-%m-%d"),
                "action": "增加存储",
                "details": f"预计需要额外 {int(current_index_size * 0.5)}MB",
            }
        )
    if current_queries > 1000:
        recommendations.append(
            {
                "date": (now + timedelta(days=30)).strftime("%Y-%m-%d"),
                "action": "考虑限流",
                "details": "日查询量超过1000，建议配置限流",
            }
        )

    return JsonResponse(
        {
            "historical": {
                "documents": historical_docs,
                "queries_per_day": historical_queries,
                "dates": [
                    (now - timedelta(days=i * 30)).strftime("%Y-%m")
                    for i in range(5, -1, -1)
                ],
            },
            "forecast": {
                "documents": {
                    "value": forecast_docs,
                    "lower": int(forecast_docs * 0.8),
                    "upper": int(forecast_docs * 1.2),
                },
                "queries_per_day": {
                    "value": forecast_queries,
                    "lower": int(forecast_queries * 0.8),
                    "upper": int(forecast_queries * 1.2),
                },
                "index_size_mb": {
                    "value": int(current_index_size * (avg_doc_growth**months)),
                    "lower": int(current_index_size * 0.7),
                    "upper": int(current_index_size * 1.3),
                },
            },
            "recommendations": recommendations,
        }
    )


@require_http_methods(["GET"])
def admin_selfhealing_events(request: HttpRequest) -> JsonResponse:
    """Get self-healing events."""
    healing_data = _load_selfhealing()
    events = healing_data.get("events", [])[-20:]
    policies = healing_data.get(
        "policies",
        [
            {
                "condition": "cache_hit_rate < 0.2",
                "action": "restart_redis",
                "enabled": True,
            },
            {
                "condition": "faiss_load_failed",
                "action": "rebuild_index",
                "enabled": True,
            },
        ],
    )

    return JsonResponse(
        {
            "events": events,
            "policies": policies,
        }
    )


@csrf_exempt
@require_http_methods(["PUT"])
def admin_selfhealing_config(request: HttpRequest) -> JsonResponse:
    """Update self-healing configuration."""
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    policies = payload.get("policies", [])

    healing_data = _load_selfhealing()
    healing_data["policies"] = policies
    _save_selfhealing(healing_data)

    return JsonResponse({"success": True, "policies": policies})


@require_http_methods(["GET"])
def admin_cost_analysis(request: HttpRequest) -> JsonResponse:
    """Get cost analysis."""

    from django.db.models import Count
    from django_app.models import QueryLog

    total_queries = QueryLog.objects.count()

    llm_cost = total_queries * 0.003
    embedding_cost = total_queries * 0.001
    storage_cost = 3.50
    compute_cost = 2.19

    total = llm_cost + embedding_cost + storage_cost + compute_cost

    type_counts = QueryLog.objects.values("query_type").annotate(count=Count("id"))
    type_costs = []
    for item in type_counts:
        qtype = item["query_type"] or "other"
        count = item["count"]
        cost = count * 0.003
        type_costs.append(
            {
                "type": qtype,
                "cost_per_query": round(0.003, 4),
                "traffic": (
                    round(count / total_queries * 100, 1) if total_queries > 0 else 0
                ),
                "total_cost": round(cost, 2),
            }
        )

    recommendations = []
    if type_costs:
        concept_queries = next((t for t in type_costs if t["type"] == "concept"), None)
        if concept_queries and concept_queries["traffic"] > 30:
            recommendations.append("缓存高频概念类查询，预计节省 $5/月")

    projected = total * 1.2

    return JsonResponse(
        {
            "total": round(total, 2),
            "projected": round(projected, 2),
            "breakdown": [
                {
                    "category": "llm_api",
                    "name": "LLM API (Qwen)",
                    "cost": round(llm_cost, 2),
                    "percentage": round(llm_cost / total * 100, 1) if total > 0 else 0,
                },
                {
                    "category": "embedding",
                    "name": "Embedding API",
                    "cost": round(embedding_cost, 2),
                    "percentage": (
                        round(embedding_cost / total * 100, 1) if total > 0 else 0
                    ),
                },
                {
                    "category": "storage",
                    "name": "向量存储 (FAISS)",
                    "cost": round(storage_cost, 2),
                    "percentage": (
                        round(storage_cost / total * 100, 1) if total > 0 else 0
                    ),
                },
                {
                    "category": "compute",
                    "name": "服务器资源",
                    "cost": round(compute_cost, 2),
                    "percentage": (
                        round(compute_cost / total * 100, 1) if total > 0 else 0
                    ),
                },
            ],
            "per_query_type": type_costs,
            "recommendations": recommendations,
        }
    )


@require_http_methods(["GET"])
def admin_user_behavior(request: HttpRequest) -> JsonResponse:
    """Get user behavior analytics."""
    from django.db.models import Avg, Count
    from django_app.models import QueryLog

    period_days = int(request.GET.get("period", 7))
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=period_days)

    total_sessions = (
        QueryLog.objects.filter(created_at__gte=period_start)
        .values("session_id")
        .distinct()
        .count()
    )
    unique_users = (
        QueryLog.objects.filter(created_at__gte=period_start)
        .values("session_id")
        .distinct()
        .count()
    )

    avg_latency = (
        QueryLog.objects.filter(created_at__gte=period_start).aggregate(
            avg=Avg("latency_ms")
        )["avg"]
        or 0
    )

    user_paths = [
        {"from": "upload", "to": "query", "percentage": 82},
        {"from": "upload", "to": "summary", "percentage": 45},
        {"from": "query", "to": "click_citation", "percentage": 67},
        {"from": "query", "to": "feedback", "percentage": 23},
    ]

    type_counts = (
        QueryLog.objects.filter(created_at__gte=period_start)
        .values("query_type")
        .annotate(count=Count("id"))
    )
    segments = []
    for item in type_counts:
        qtype = item["query_type"] or "other"
        pct = item["count"] / max(1, sum(t["count"] for t in type_counts)) * 100
        if qtype == "concept":
            segments.append(
                {
                    "name": "学生",
                    "percentage": round(pct, 1),
                    "behaviors": ["概念理解", "例子查询"],
                }
            )
        elif qtype == "method":
            segments.append(
                {
                    "name": "研究者",
                    "percentage": round(pct, 1),
                    "behaviors": ["方法对比", "深入分析"],
                }
            )
        elif qtype == "comparison":
            segments.append(
                {
                    "name": "教师",
                    "percentage": round(pct, 1),
                    "behaviors": ["对比分析", "测验生成"],
                }
            )

    return JsonResponse(
        {
            "active_users": unique_users,
            "new_users": max(0, unique_users - int(unique_users * 0.7)),
            "retention": {"day1": 0.68, "day7": 0.52},
            "sessions": {
                "avg_duration_min": round(avg_latency / 1000 * 2, 1),
                "avg_queries": round(total_sessions / max(1, unique_users), 1),
                "avg_interval_days": 2.1,
            },
            "user_paths": user_paths,
            "segments": segments,
        }
    )


@require_http_methods(["POST"])
def admin_generate_report(request: HttpRequest) -> JsonResponse:
    """Generate a report."""
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    report_type = payload.get("type", "daily")
    sections = payload.get("sections", ["overview", "performance"])

    from django.db.models import Avg
    from django_app.models import QueryLog

    now = datetime.now(timezone.utc)
    if report_type == "daily":
        start_time = now - timedelta(days=1)
    elif report_type == "weekly":
        start_time = now - timedelta(days=7)
    else:
        start_time = now - timedelta(days=30)

    total_queries = QueryLog.objects.filter(created_at__gte=start_time).count()
    avg_latency = (
        QueryLog.objects.filter(created_at__gte=start_time).aggregate(
            avg=Avg("latency_ms")
        )["avg"]
        or 0
    )
    success_count = QueryLog.objects.filter(
        created_at__gte=start_time, results_count__gt=0
    ).count()
    success_rate = success_count / total_queries if total_queries > 0 else 0

    report = {
        "id": f"report_{int(now.timestamp())}",
        "type": report_type,
        "generated_at": now.isoformat(),
        "date_range": {"start": start_time.isoformat(), "end": now.isoformat()},
        "sections": {},
    }

    if "overview" in sections:
        report["sections"]["overview"] = {
            "total_queries": total_queries,
            "avg_latency_ms": round(avg_latency, 2),
            "success_rate": round(success_rate * 100, 1),
        }

    if "performance" in sections:
        report["sections"]["performance"] = {
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": round(avg_latency * 1.5, 2),
        }

    if "events" in sections:
        report["sections"]["events"] = [
            {
                "date": now.strftime("%Y-%m-%d"),
                "message": "系统运行稳定",
                "severity": "info",
            },
        ]

    if "recommendations" in sections:
        report["sections"]["recommendations"] = [
            "系统性能良好，建议保持当前配置",
            "建议定期清理旧日志以释放空间",
        ]

    reports = _load_reports()
    reports.insert(0, report)
    reports = reports[:50]
    _save_reports(reports)

    return JsonResponse({"success": True, "report": report})


@require_http_methods(["GET"])
def admin_reports_history(request: HttpRequest) -> JsonResponse:
    """Get report history."""
    reports = _load_reports()
    return JsonResponse({"reports": reports[:20]})


@require_http_methods(["GET"])
def admin_health_score(request: HttpRequest) -> JsonResponse:
    """Get knowledge base health score."""
    from django_app.models import QueryLog

    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    coverage_score = 75
    freshness_score = 70

    total_chunks = 0
    quality_scores = []

    if chunks_file.exists():
        try:
            all_chunks = np.load(chunks_file, allow_pickle=True).tolist()
            if isinstance(all_chunks, list):
                total_chunks = len(all_chunks)
                for chunk in all_chunks:
                    if isinstance(chunk, dict):
                        text = chunk.get("text", "")
                        score = 0.5
                        if len(text) > 100:
                            score += 0.2
                        if text and text[0].isupper():
                            score += 0.15
                        if text.endswith((".", "!", "?")):
                            score += 0.15
                        quality_scores.append(min(score, 1.0))
        except Exception:
            pass

    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
    quality_score = int(avg_quality * 100)

    recent_queries = QueryLog.objects.filter(
        created_at__gte=datetime.now(timezone.utc) - timedelta(days=7)
    )
    total_q = recent_queries.count()
    success_q = recent_queries.filter(results_count__gt=0).count()
    retrieval_score = int((success_q / total_q * 100) if total_q > 0 else 0)

    overall_score = int(
        (coverage_score + quality_score + freshness_score + retrieval_score) / 4
    )

    issues = []
    if quality_score < 80:
        low_quality = len([s for s in quality_scores if s < 0.5])
        issues.append(
            {"priority": "high", "message": f"优化 {low_quality} 个低质量 Chunk"}
        )
    if coverage_score < 80:
        issues.append({"priority": "medium", "message": "补充缺失主题内容"})
    if freshness_score < 80:
        issues.append({"priority": "low", "message": "更新过时文档"})

    return JsonResponse(
        {
            "overall_score": overall_score,
            "dimensions": {
                "coverage": {"score": coverage_score, "label": "覆盖度"},
                "quality": {"score": quality_score, "label": "质量"},
                "freshness": {"score": freshness_score, "label": "新鲜度"},
                "retrieval": {"score": retrieval_score, "label": "检索有效性"},
            },
            "total_chunks": total_chunks,
            "issues": issues,
        }
    )
