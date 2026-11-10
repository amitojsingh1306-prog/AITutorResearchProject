"""Semantic embedding provider with a deterministic fallback.

The production path uses sentence-transformers to create dense semantic
embeddings. The fallback keeps the app usable when the model is not installed
or cannot be loaded on the current machine.
"""

from __future__ import annotations

import hashlib
import math
import os
from functools import lru_cache


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def embed_text(text: str) -> list[float]:
    """Return a dense semantic embedding when possible."""

    try:
        model = _load_model()
        return [float(value) for value in model.encode(text, normalize_embeddings=True).tolist()]
    except Exception:
      return fallback_hash_embedding(text)


def embedding_backend() -> str:
    """Return the active backend name for debug output."""

    try:
        _load_model()
    except Exception:
        return "fallback-hash-64"
    return os.getenv("CHATBOT_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def _load_model():
    from sentence_transformers import SentenceTransformer

    model_name = os.getenv("CHATBOT_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    try:
        return SentenceTransformer(model_name, local_files_only=True)
    except Exception:
        return SentenceTransformer(model_name)


def fallback_hash_embedding(text: str, dimensions: int = 64) -> list[float]:
    """Create deterministic sparse vectors when semantic embeddings are unavailable."""

    vector = [0.0] * dimensions
    tokens = [token.lower() for token in text.split() if token.strip()]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % dimensions
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return [0.0] * dimensions
    return [value / magnitude for value in vector]
