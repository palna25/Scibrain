"""Validated configuration for the isolated SciBrain graph engine."""
from __future__ import annotations
import os
from dataclasses import dataclass
import math


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _float_env(name: str, default: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be finite and between {minimum} and {maximum}")
    return value


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


@dataclass(frozen=True)
class GraphEngineSettings:
    gemini_model: str = "gemini-3.5-flash-lite"
    qdrant_collection: str = "scibrain_papers"
    retrieval_limit: int = 8
    max_chunks_per_paper: int = 30
    max_total_chunks: int = 100
    max_chunks_per_category: int = 4
    extraction_batch_size: int = 5
    max_chunk_chars: int = 5000
    max_concurrent_extractions: int = 3
    minimum_relationship_confidence: float = 0.70
    enable_cross_paper_discovery: bool = False

    @classmethod
    def from_env(cls) -> "GraphEngineSettings":
        return cls(
            gemini_model=(os.getenv("GRAPH_GEMINI_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip(),
            qdrant_collection=(os.getenv("GRAPH_QDRANT_COLLECTION") or os.getenv("QDRANT_COLLECTION") or "scibrain_papers").strip(),
            retrieval_limit=_int_env("GRAPH_RETRIEVAL_LIMIT", 8),
            max_chunks_per_paper=_int_env("GRAPH_MAX_CHUNKS_PER_PAPER", 30),
            max_total_chunks=_int_env("GRAPH_MAX_TOTAL_CHUNKS", 100),
            max_chunks_per_category=_int_env("GRAPH_MAX_CHUNKS_PER_CATEGORY", 4),
            extraction_batch_size=_int_env("GRAPH_EXTRACTION_BATCH_SIZE", 5),
            max_chunk_chars=_int_env("GRAPH_MAX_CHUNK_CHARS", 5000),
            max_concurrent_extractions=_int_env("GRAPH_MAX_CONCURRENT_EXTRACTIONS", 3),
            minimum_relationship_confidence=_float_env("GRAPH_MIN_RELATIONSHIP_CONFIDENCE", 0.70),
            enable_cross_paper_discovery=_bool_env("GRAPH_ENABLE_CROSS_PAPER_DISCOVERY", False),
        )
