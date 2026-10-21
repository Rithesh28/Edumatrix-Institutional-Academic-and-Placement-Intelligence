"""
Shared GLiNER Service for Placement Intelligence & Entity Recognition

Provides thread-safe, lazy-loaded, offline-only Named Entity Recognition (NER)
using the urchade/gliner_base model cached locally in the environment.
"""

import logging
import threading
import time
from typing import List, Dict, Any, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)


class GLiNERService:
    """
    Singleton service managing the local GLiNER base model for zero-shot
    open-vocabulary entity extraction.
    """

    def __init__(self):
        self.model = None
        self.is_loaded = False
        self._load_attempted = False
        self.model_name = getattr(settings, "GLINER_MODEL_NAME", "urchade/gliner_base")
        self.use_gliner = getattr(settings, "USE_GLINER", True)
        self.default_threshold = getattr(settings, "GLINER_THRESHOLD", 0.50)
        self._init_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._last_error: Optional[str] = None
        self._load_time_seconds: float = 0.0

    def _ensure_model(self) -> bool:
        """
        Lazily load the GLiNER model once in a thread-safe manner.
        Only uses local cached files. Never attempts remote downloads.
        """
        if not self.use_gliner:
            return False

        if self.is_loaded:
            return True

        if self._load_attempted:
            return self.is_loaded

        with self._init_lock:
            if self.is_loaded:
                return True

            self._load_attempted = True
            start_t = time.perf_counter()

            try:
                from gliner import GLiNER
            except ImportError as ie:
                self._last_error = f"gliner package not installed: {ie}"
                logger.warning(f"⚠️ GLiNER initialization skipped: {self._last_error}")
                self.is_loaded = False
                return False

            try:
                logger.info(f"Loading local GLiNER model '{self.model_name}' (offline mode)...")
                # Enforce local_files_only=True to prevent remote network calls
                self.model = GLiNER.from_pretrained(
                    self.model_name,
                    local_files_only=True
                )
                self.is_loaded = True
                self._load_time_seconds = time.perf_counter() - start_t
                self._last_error = None
                logger.info(
                    f"✅ GLiNER model '{self.model_name}' loaded successfully offline in "
                    f"{self._load_time_seconds:.2f}s"
                )
                return True
            except Exception as exc:
                self._last_error = str(exc)
                self.is_loaded = False
                logger.warning(
                    f"⚠️ Failed to load local GLiNER model '{self.model_name}': {exc}. "
                    f"Extraction will proceed with deterministic regex fallback."
                )
                return False

    def is_available(self) -> bool:
        """Check if the GLiNER model is loaded or can be loaded."""
        if not self.use_gliner:
            return False
        return self._ensure_model()

    def get_model(self) -> Optional[Any]:
        """Access the underlying GLiNER model instance."""
        if self._ensure_model():
            return self.model
        return None

    def get_status(self) -> Dict[str, Any]:
        """Return diagnostic health and status information."""
        return {
            "model_name": self.model_name,
            "use_gliner": self.use_gliner,
            "is_loaded": self.is_loaded,
            "load_attempted": self._load_attempted,
            "load_time_seconds": round(self._load_time_seconds, 3),
            "last_error": self._last_error,
            "device": "cpu"
        }

    def predict_entities(
        self,
        text: str,
        labels: List[str],
        threshold: Optional[float] = None,
        flat_ner: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Extract named entities from a single text block.
        
        Args:
            text: Input text snippet
            labels: List of target entity classes (e.g., ['technical skill', 'job title'])
            threshold: Confidence threshold (defaults to settings.GLINER_THRESHOLD)
            flat_ner: Whether to enforce non-overlapping spans
            
        Returns:
            List of dicts: [{'text': str, 'label': str, 'score': float, 'start': int, 'end': int}]
        """
        if not text or not text.strip() or not labels:
            return []

        if not self._ensure_model():
            return []

        th = threshold if threshold is not None else self.default_threshold

        with self._inference_lock:
            try:
                preds = self.model.predict_entities(
                    text,
                    labels,
                    threshold=th,
                    flat_ner=flat_ner
                )
                formatted: List[Dict[str, Any]] = []
                for p in preds:
                    t = str(p.get("text", "")).strip()
                    if t:
                        formatted.append({
                            "text": t,
                            "label": str(p.get("label", "")),
                            "score": float(p.get("score", 0.0)),
                            "start": int(p.get("start", 0)),
                            "end": int(p.get("end", 0))
                        })
                return formatted
            except Exception as err:
                logger.warning(f"GLiNER predict_entities inference failed: {err}")
                return []

    def chunked_predict_entities(
        self,
        text: str,
        labels: List[str],
        threshold: Optional[float] = None,
        max_chars: int = 1200,
        overlap: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Extract entities from longer documents using a sliding window approach
        to respect transformer sequence limits without cutting off entities.
        """
        if not text or not text.strip():
            return []

        if len(text) <= max_chars:
            return self.predict_entities(text, labels, threshold=threshold)

        # Split into overlapping chunks
        chunks: List[Tuple[int, str]] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + max_chars, text_len)
            # Try to break at a newline if not at end
            if end < text_len:
                last_newline = text.rfind("\n", start + max_chars // 2, end)
                if last_newline != -1:
                    end = last_newline + 1

            chunk_str = text[start:end]
            chunks.append((start, chunk_str))
            if end >= text_len:
                break
            start = end - overlap if (end - overlap) > start else end

        all_entities: List[Dict[str, Any]] = []
        for offset, chunk_text in chunks:
            chunk_preds = self.predict_entities(chunk_text, labels, threshold=threshold)
            for cp in chunk_preds:
                cp["start"] += offset
                cp["end"] += offset
                all_entities.append(cp)

        # Deduplicate overlapping entities: keep highest confidence score
        unique_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for ent in all_entities:
            key = (ent["label"].lower(), ent["text"].lower().strip())
            if key not in unique_map or ent["score"] > unique_map[key]["score"]:
                unique_map[key] = ent

        return list(unique_map.values())


# Global singleton instance
gliner_service = GLiNERService()
