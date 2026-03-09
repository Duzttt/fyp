import json
import os
import threading
import time
from datetime import datetime, timezone
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
    frontend_index = Path(django_settings.BASE_DIR) / "django_app" / "static" / "frontend" / "index.html"
    
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
    from app.services.vector_store import VectorStore
    
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
    
    return JsonResponse({
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
    })


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
        vector_store = VectorStore.get_cached(settings.FAISS_INDEX_PATH, settings.EMBEDDING_DIM)
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
    
    return JsonResponse({
        "performance": {
            "avg_retrieval_time_ms": round(retrieval_time_ms, 2),
            "avg_embedding_time_ms": round(embedding_time_ms, 2),
        },
        "quality": quality_metrics,
    })


@require_http_methods(["GET"])
def dashboard_chunks_distribution(request: HttpRequest) -> JsonResponse:
    """
    Get chunk length distribution data for histogram.
    """
    from app.services.vector_store import VectorStore
    
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
            bins.append({
                "range": f"{int(bin_start)}-{int(bin_end)}",
                "count": count,
            })
        
        stats = {
            "min": min_len,
            "max": max_len,
            "mean": round(sum(chunk_lengths) / len(chunk_lengths), 2),
            "median": sorted(chunk_lengths)[len(chunk_lengths) // 2],
        }
    else:
        bins = []
        stats = {"min": 0, "max": 0, "mean": 0, "median": 0}
    
    return JsonResponse({
        "histogram": bins,
        "statistics": stats,
        "total_chunks": len(chunk_lengths),
    })


@require_http_methods(["GET"])
def dashboard_similarity_distribution(request: HttpRequest) -> JsonResponse:
    """
    Get similarity score distribution data.
    """
    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStore
    
    similarity_scores = []
    
    try:
        vector_store = VectorStore.get_cached(settings.FAISS_INDEX_PATH, settings.EMBEDDING_DIM)
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
            count = sum(1 for score in similarity_scores if bin_start <= score < bin_end)
            bins.append({
                "range": f"{bin_start:.1f}-{bin_end:.1f}",
                "count": count,
            })
        
        stats = {
            "min": round(min(similarity_scores), 3),
            "max": round(max(similarity_scores), 3),
            "mean": round(sum(similarity_scores) / len(similarity_scores), 3),
        }
    else:
        bins = []
        stats = {"min": 0, "max": 0, "mean": 0}
    
    return JsonResponse({
        "histogram": bins,
        "statistics": stats,
        "sample_size": len(similarity_scores),
    })


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
                documents.append({
                    "name": pdf.name,
                    "display_name": "_".join(pdf.name.split("_")[1:]) if "_" in pdf.name else pdf.name,
                    "size_kb": round(stats.st_size / 1024, 2),
                    "created_at": datetime.fromtimestamp(stats.st_ctime, tz=timezone.utc).isoformat(),
                    "modified_at": datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc).isoformat(),
                })
            except Exception:
                pass
    
    # Sort by creation date
    documents.sort(key=lambda x: x["created_at"], reverse=True)
    
    return JsonResponse({
        "documents": documents,
        "total": len(documents),
    })


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
    
    return JsonResponse({
        "status": "success",
        "config": config,
        "message": "Configuration updated. Reindex required for chunking changes to take effect.",
    })


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
    
    return JsonResponse({
        "status": "success",
        "message": "Reindexing started",
        "indexing_state": state,
    })


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
# Embedding Model Management Endpoints
# ==========================================

EMBEDDING_MODEL_SETTINGS_FILE = Path(__file__).resolve().parents[1] / "data" / "embedding_model_settings.json"


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
        
        return JsonResponse({
            "models": models,
            "cache_stats": cache_stats,
        })
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
        
        return JsonResponse({
            "model_id": current_id,
            "model_name": model_info.get("name", current_id),
            "dimension": model_info.get("dimension", 384),
            "speed": model_info.get("speed", "Unknown"),
            "memory": model_info.get("memory", "Unknown"),
            "is_loaded": is_loaded,
            "recommended": model_info.get("recommended", False),
        })
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
        
        return JsonResponse({
            "success": True,
            **result,
        })
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
        
        return JsonResponse({
            "success": True,
            **result,
        })
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
            model_stats[model_id]["actions"][action]["total_time_ms"] += metric["time_ms"]
        
        # Calculate averages
        for model_id, stats in model_stats.items():
            stats["avg_time_ms"] = round(stats["total_time_ms"] / stats["count"], 2) if stats["count"] > 0 else 0
            
            for action, action_stats in stats["actions"].items():
                action_stats["avg_time_ms"] = round(
                    action_stats["total_time_ms"] / action_stats["count"], 2
                ) if action_stats["count"] > 0 else 0
        
        return JsonResponse({
            "metrics": metrics,
            "model_stats": model_stats,
            "cache_stats": manager.get_cache_stats(),
        })
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

        return JsonResponse({
            "success": True,
            "message": "Model cache cleared",
        })
    except Exception as exc:
        return _error_response(f"Failed to clear cache: {str(exc)}", status=500)


# ==========================================
# Document Summarization Endpoints
# ==========================================

SUMMARY_HISTORY_FILE = Path(__file__).resolve().parents[1] / "data" / "summary_history.json"


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
            documents.append({
                "name": doc_id,
                "text": text,
            })
    
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
        
        return JsonResponse({
            "success": True,
            "summary": result["text"],
            "citations": result.get("citations", []),
            "comparison": result.get("comparison", []),
            "document_count": len(documents),
            "documents": [doc["name"] for doc in documents],
            "config": default_config,
            "history_id": history_entry["id"],
        })
        
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
        
        return JsonResponse({
            "history": recent_history,
            "total": len(history),
        })
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
        
        return JsonResponse({
            "success": True,
            "message": "Summary deleted",
        })
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
            documents.append({
                "name": doc_name,
                "text": text,
            })
    
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
        new_history = [h if h.get("id") != history_id else updated_entry for h in history]
        _save_summary_history(new_history)
        
        return JsonResponse({
            "success": True,
            "summary": result["text"],
            "citations": result.get("citations", []),
            "comparison": result.get("comparison", []),
            "config": config,
        })
        
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
                documents.append({
                    "name": doc_id,
                    "content": text,
                })
        
        if not documents:
            return _error_response("No valid documents found in index", status=404)
        
        # Generate suggestions
        result = generate_question_suggestions(documents, num_suggestions)
        
        return JsonResponse({
            "success": True,
            "suggestions": result.get("suggestions", []),
            "generated_from": result.get("generated_from", []),
            "document_count": len(documents),
        })
        
    except QuestionSuggestionError as exc:
        return _error_response(f"Suggestion generation failed: {str(exc)}", status=500)
    except Exception as exc:
        return _error_response(f"Failed to generate suggestions: {str(exc)}", status=500)


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
        
        return JsonResponse({
            "success": True,
            "message": "Click recorded",
            "suggestion_id": suggestion_id,
            "click_count": (existing.click_count if existing else 1),
        })
        
    except Exception as exc:
        # Don't fail the request if tracking fails
        print(f"Failed to record suggestion click: {exc}")
        return JsonResponse({
            "success": True,
            "message": "Click recorded (tracking may have failed)",
        })


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
            result.append({
                "id": s.id,
                "question_text": s.question_text,
                "question_type": s.question_type,
                "document_names": s.document_names.split(", ") if s.document_names else [],
                "click_count": s.click_count,
                "feedback_score": s.feedback_score,
                "created_at": s.created_at.isoformat(),
            })
        
        return JsonResponse({
            "suggestions": result,
            "total": query.count(),
        })
        
    except Exception as exc:
        return _error_response(f"Failed to load suggestions: {str(exc)}", status=500)
