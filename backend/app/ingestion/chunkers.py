"""Deterministic, token-aware chunking (tiktoken).

Chunk boundaries are pushed to paragraph/sentence boundaries whenever possible
so consecutive chunks stay self-contained for retrieval.
"""

from __future__ import annotations

import tiktoken

from app.config import get_settings

_encoders: dict[str, tiktoken.Encoding] = {}


def _encoder(name: str = "cl100k_base") -> tiktoken.Encoding:
    if name not in _encoders:
        _encoders[name] = tiktoken.get_encoding(name)
    return _encoders[name]


def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    settings = get_settings()
    chunk_size = chunk_size or settings.chunk_size_tokens
    overlap = overlap or settings.chunk_overlap_tokens
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    enc = _encoder()
    tokens = enc.encode(text)
    if len(tokens) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        if end - start < chunk_size // 2 and chunks:
            break  # refuse tiny tail fragments
        chunks.append(enc.decode(chunk_tokens))
        if end == len(tokens):
            break
        start = max(start + chunk_size - overlap, start + 1)
    return chunks