import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cross_encoder_reranker")

_DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"


def _resolve_device(device: Optional[str]) -> str:
    """
    Resolve the torch device for the cross-encoder.

    - Explicit "cuda" / "cpu" / "mps" values are used as-is.
    - None or "auto" picks CUDA when available, then Apple MPS, else CPU.
    """
    if device is not None and device != "auto":
        return device
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        mps_backend = getattr(torch.backends, "mps", None)
        if mps_backend is not None and mps_backend.is_available():
            return "mps"
    except Exception:  # noqa: BLE001 - torch import failure falls back to CPU
        pass
    return "cpu"


class CrossEncoderReranker:
    _instance: Optional["CrossEncoderReranker"] = None
    _model_name: str = ""
    _model: Any = None
    _lock: threading.Lock = threading.Lock()

    def __init__(
        self, model_name: str = _DEFAULT_MODEL, device: Optional[str] = None
    ) -> None:
        self._model_name = model_name
        self._device = _resolve_device(device)

    @property
    def device(self) -> str:
        """The device the cross-encoder runs on (e.g. 'cuda', 'cpu', 'mps')."""
        return self._device

    @classmethod
    def get_instance(
        cls,
        model_name: str = _DEFAULT_MODEL,
        device: Optional[str] = None,
    ) -> "CrossEncoderReranker":
        resolved_device = _resolve_device(device)
        if (
            cls._instance is not None
            and cls._instance._model_name == model_name
            and cls._instance._device == resolved_device
        ):
            return cls._instance
        with cls._lock:
            if (
                cls._instance is not None
                and cls._instance._model_name == model_name
                and cls._instance._device == resolved_device
            ):
                return cls._instance
            cls._instance = cls(model_name, resolved_device)
            return cls._instance

    def _load_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name, device=self._device)
            logger.info(
                "Loaded cross-encoder model: %s on device %s",
                self._model_name,
                self._device,
            )
        return self._model

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if not results:
            return []
        model = self._load_model()
        pairs = [(query, r.get("text", "")) for r in results]
        scores = model.predict(pairs)
        for r, s in zip(results, scores):
            r["rerank_score"] = float(s)
        results.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        if top_k is not None:
            results = results[:top_k]
        return results

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None
