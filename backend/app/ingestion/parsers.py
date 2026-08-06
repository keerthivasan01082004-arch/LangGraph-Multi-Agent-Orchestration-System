"""Format-specific text extractors (pdf, docx, txt/md, csv)."""

from __future__ import annotations

import csv
import io
import re

from app.core.errors import APIError


class UnsupportedFormatError(APIError):
    def __init__(self, fmt: str) -> None:
        super().__init__(
            code="unsupported_format",
            message=f"Unsupported document format: {fmt}",
            http_status=415,
        )


def extract_text_bytes(data: bytes, content_type: str, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("txt", "md", "csv", "json"):
        return data.decode("utf-8", errors="replace")
    if ext == "pdf":
        return _extract_pdf(data)
    if ext == "docx":
        return _extract_docx(data)
    raise UnsupportedFormatError(ext or content_type)


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "(pdf extraction requires pypdf; see README)"
    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    try:
        import docx  # python-docx
    except ImportError:
        return "(docx extraction requires python-docx; see README)"
    document = docx.Document(io.BytesIO(data))
    return "\n\n".join(p.text for p in document.paragraphs)


def normalize_spaces(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text)