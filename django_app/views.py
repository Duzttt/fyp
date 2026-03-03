import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import requests
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

SETTINGS_FILE = Path(__file__).resolve().parents[1] / "data" / "settings.json"
CHAT_DEMO_FILE = Path(__file__).resolve().parent / "chat_demo.html"
VALID_PROVIDERS = {"gemini", "openrouter"}
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


@require_http_methods(["GET"])
def index_page(request: HttpRequest) -> HttpResponse:
    return render(request, "index.html")


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
        unique_filename = f"{uuid.uuid4()}_{original_filename}"
        saved_file_path = pdf_loader.save_pdf(contents, unique_filename)
    except OSError as exc:
        return _error_response(f"Failed to save PDF: {str(exc)}", status=500)

    indexing_strategy = _resolve_upload_indexing_strategy()
    if (
        indexing_strategy == INDEXING_STRATEGY_FULL_REBUILD
        and settings.UPLOAD_INDEXING_ASYNC
    ):
        state = _enqueue_full_rebuild(uploaded_filename=unique_filename)
        return JsonResponse(
            {
                "success": True,
                "message": "File uploaded. Full reindex is running in background.",
                "filename": unique_filename,
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
            "filename": unique_filename,
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

    try:
        retrieved_sources = retrieve_with_faiss(
            query=query, top_k=3, source_filter=source_filter
        )
        context = build_context_from_sources(retrieved_sources)
        if not context.strip():
            return _error_response("No indexed context found in FAISS", status=400)

        system_prompt = (
            "You are a rigorous academic teaching assistant. Please answer the questions based on the following reference materials."
            "If the evidence is insufficient, please explain clearly."
        )
        user_prompt = f"参考资料：\n{context}\n\n用户提问：{query}"

        ollama_client = OllamaClient(
            host=settings.LOCAL_QWEN_BASE_URL,
            timeout=settings.LOCAL_QWEN_TIMEOUT_SECONDS,
        )
        model_response = ollama_client.chat(
            model=settings.LOCAL_QWEN_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
            keep_alive=settings.LOCAL_QWEN_KEEP_ALIVE,
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

    query = f"请总结文档 {filename} 的核心内容，并列出 3 个最重要的知识点。"

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
