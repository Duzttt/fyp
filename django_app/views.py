import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
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
