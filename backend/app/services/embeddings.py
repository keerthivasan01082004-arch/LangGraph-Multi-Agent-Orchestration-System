"""Embedding service.

Abstraction over the embedding backend so dev (local sentence-transformers with
ONNX) and prod (HuggingFace TEI or an embedding endpoint) are interchangeable.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings


@lru_cache
def _model():
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    # Batch encode; normalize for cosine via Qdrant's dot product option.
    vectors = _model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [list(v) for v in vectors]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]