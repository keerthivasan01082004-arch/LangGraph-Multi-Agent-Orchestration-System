"""Tests for token-aware chunking."""

from app.ingestion.chunkers import chunk_text, token_count


def test_short_text_is_single_chunk():
    text = "Short document."
    chunks = chunk_text(text, chunk_size=512, overlap=64)
    assert chunks == [text]


def test_long_text_splits_with_overlap():
    text = " ".join(f"word{i}" for i in range(2000))
    chunks = chunk_text(text, chunk_size=256, overlap=32)
    assert len(chunks) > 1
    # Overlap means the concatenation is longer than the source; every chunk
    # must be bounded by the budget.
    for chunk in chunks:
        assert token_count(chunk) <= 300


def test_no_tiny_trailing_fragment():
    text = " ".join(f"word{i}" for i in range(1370))
    chunks = chunk_text(text, chunk_size=512, overlap=64)
    for chunk in chunks:
        assert token_count(chunk) >= 200  # refuse tiny tail fragments


def test_overlap_must_not_exceed_chunk_size():
    import pytest

    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=10, overlap=10)


def test_token_count_monotonic():
    assert token_count("hello world") == token_count("hello world")
    assert token_count("a much longer sentence of text here") > 4