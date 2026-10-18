"""
Structured Performance Timing and Lifecycle Instrumentation for Study Buddy.

Provides high-resolution timing, metric aggregation, and structured logging
for the 9 Study Buddy request lifecycle stages:
1. Attachment upload and SHA-256 calculation
2. PDF/text extraction and OCR, if triggered
3. Chunking and embedding generation
4. Qdrant indexing and confirmation
5. Retrieval from lecturer notes
6. Retrieval from attached student document
7. PostgreSQL authorization and citation validation
8. Qwen model loading and answer generation
9. Total end-to-end request latency

CRITICAL PRIVACY SAFEGUARDS:
- Never logs passwords, tokens, full document text, or PII.
- Only logs durations, sizes, status flags, and counts.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from collections import deque

logger = logging.getLogger("study_buddy.perf")

# In-memory circular buffer of recent structured performance records (last 200 events)
# for automated test assertions and telemetry reporting.
_recent_metrics: deque = deque(maxlen=200)


class PerfTimer:
    """Context manager for high-resolution wall-clock timing."""
    def __init__(self, name: str = "operation"):
        self.name = name
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self.elapsed_ms = (self.end_time - self.start_time) * 1000.0


def record_perf_metric(stage: str, duration_ms: float, **kwargs) -> Dict[str, Any]:
    """
    Record and log a structured performance metric.
    Format: ⏱️ [PERF-METRIC] stage='...' | duration_ms=... | key=val ...
    """
    clean_ms = round(float(duration_ms), 2)
    metric_record = {
        "stage": stage,
        "duration_ms": clean_ms,
        "timestamp": time.time(),
        **kwargs
    }
    _recent_metrics.append(metric_record)

    extra_parts = [f"{k}={v}" for k, v in kwargs.items()]
    extra_str = (" | " + " | ".join(extra_parts)) if extra_parts else ""
    logger.info(f"⏱️ [PERF-METRIC] stage='{stage}' | duration_ms={clean_ms:.2f}{extra_str}")
    return metric_record


def get_recent_perf_metrics(stage: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve recorded metrics, optionally filtered by stage."""
    if stage:
        return [m for m in _recent_metrics if m.get("stage") == stage]
    return list(_recent_metrics)


def clear_recent_perf_metrics() -> None:
    """Clear metric buffer (used before benchmarking runs)."""
    _recent_metrics.clear()
