"""
Flashcard generation API views.

Endpoints:
- POST /api/flashcards/generate    -> generate flashcards from selected documents
- GET  /api/flashcards/history     -> list recent flashcard decks
- POST /api/flashcards/<id>/delete -> delete a deck from history
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings

from django_app.views.helpers import _error_response, _get_json_body

FLASHCARDS_HISTORY_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "flashcards_history.json"
)
MAX_HISTORY_ENTRIES = 50
DEFAULT_CARD_COUNT = 10


def _load_history() -> List[Dict[str, Any]]:
    if not FLASHCARDS_HISTORY_FILE.exists():
        return []

    try:
        with FLASHCARDS_HISTORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except (OSError, json.JSONDecodeError):
        pass

    return []


def _save_history(history: List[Dict[str, Any]]) -> None:
    FLASHCARDS_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with FLASHCARDS_HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def _get_document_text(filename: str) -> Optional[str]:
    from app.services.runtime_embedding import load_runtime_embedding_settings
    from app.services.vector_store import VectorStore

    try:
        rt = load_runtime_embedding_settings()
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=rt["embedding_dim"],
        )

        doc_chunks = []
        for chunk in vector_store.chunks:
            chunk_source = str(chunk.get("source", ""))
            if filename in chunk_source or chunk_source.endswith(filename):
                doc_chunks.append(chunk)

        if not doc_chunks:
            return None

        doc_chunks.sort(key=lambda c: c.get("page", 0) or 0)
        return " ".join([str(c.get("text", "")) for c in doc_chunks])
    except Exception:
        return None


def _normalize_config(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("config must be an object")

    num_cards = raw.get("num_cards", DEFAULT_CARD_COUNT)
    try:
        num_cards = int(num_cards)
    except (TypeError, ValueError):
        raise ValueError("num_cards must be an integer")
    if not 1 <= num_cards <= 50:
        raise ValueError("num_cards must be between 1 and 50")

    topic = str(raw.get("topic") or "").strip()
    if len(topic) > 200:
        raise ValueError("topic must be 200 characters or fewer")

    return {"num_cards": num_cards, "topic": topic}


@csrf_exempt
@require_http_methods(["POST"])
def generate_flashcards(request: HttpRequest) -> JsonResponse:
    from app.services.flashcard_generator import (
        FlashcardGenerationError,
        FlashcardGenerator,
    )

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    document_ids = payload.get("document_ids", [])
    if not isinstance(document_ids, list) or not document_ids:
        return _error_response("document_ids must be a non-empty list", status=400)

    try:
        config = _normalize_config(payload.get("config") or {})
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    documents = []
    for doc_id in document_ids:
        text = _get_document_text(str(doc_id))
        if text:
            documents.append({"name": str(doc_id), "text": text})

    if not documents:
        return _error_response("No valid documents found", status=404)

    try:
        generator = FlashcardGenerator()
        result = generator.generate(documents, config)
    except FlashcardGenerationError as exc:
        return _error_response(str(exc), status=500)
    except Exception as exc:
        return _error_response(f"Failed to generate flashcards: {str(exc)}", status=500)

    cards = result.get("cards") if isinstance(result, dict) else None
    if not isinstance(cards, list):
        return _error_response("Flashcard generation returned invalid data", status=500)

    deck_id = f"deck_{int(time.time() * 1000)}"
    entry = {
        "id": deck_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "documents": [doc["name"] for doc in documents],
        "config": config,
        "cards": cards,
    }

    history = _load_history()
    history.insert(0, entry)
    if len(history) > MAX_HISTORY_ENTRIES:
        history = history[:MAX_HISTORY_ENTRIES]
    _save_history(history)

    return JsonResponse(
        {
            "success": True,
            "deck_id": deck_id,
            "cards": cards,
            "config": config,
            "document_count": len(documents),
            "documents": [doc["name"] for doc in documents],
        }
    )


@require_http_methods(["GET"])
def get_flashcards_history(request: HttpRequest) -> JsonResponse:
    try:
        try:
            limit = int(request.GET.get("limit", 20))
        except (TypeError, ValueError):
            limit = 20
        limit = max(0, min(limit, 50))

        history = _load_history()
        result = []
        for entry in history[:limit]:
            item = {key: value for key, value in entry.items() if key != "cards"}
            item["cards"] = entry.get("cards", [])
            item["card_count"] = len(entry.get("cards", []))
            result.append(item)

        return JsonResponse({"history": result, "total": len(history)})
    except Exception as exc:
        return _error_response(
            f"Failed to load flashcard history: {str(exc)}", status=500
        )


@csrf_exempt
@require_http_methods(["POST"])
def delete_flashcards(request: HttpRequest, deck_id: str) -> JsonResponse:
    try:
        history = _load_history()
        new_history = [entry for entry in history if entry.get("id") != deck_id]

        if len(new_history) == len(history):
            return _error_response("Flashcard deck not found", status=404)

        _save_history(new_history)
        return JsonResponse({"success": True, "message": "Flashcard deck deleted"})
    except Exception as exc:
        return _error_response(f"Failed to delete flashcards: {str(exc)}", status=500)
