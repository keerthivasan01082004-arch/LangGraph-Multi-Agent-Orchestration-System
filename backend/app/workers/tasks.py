"""Celery tasks: the async ingestion pipeline.

process_document (queue=ingestion):
    validate → extract → chunk → enqueue embed_chunk_batch
embed_chunk_batch (queue=embedding):
    embed → upsert into Qdrant → update Document status

Retries use exponential backoff; failures are recorded on the Document row.
"""

import logging
import uuid

from app.ingestion.chunkers import chunk_text
from app.ingestion.parsers import extract_text_bytes
from app.services import embeddings, vectorstore
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.process_document", bind=True, max_retries=3)
def process_document(self, document_id: str) -> dict[str, object]:
    from sqlalchemy.orm import Session

    from app.db.models import Document, DocumentStatus
    from app.db.session import SessionLocal
    from app.services.storage import get_object

    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if doc is None:
            return {"document_id": document_id, "status": "missing"}

        doc.status = DocumentStatus.PROCESSING
        db.commit()

        try:
            raw = get_object(doc.s3_key)
            text = extract_text_bytes(raw, doc.content_type, doc.filename)
            chunks = chunk_text(text)
            vectorstore.ensure_collection()
            for i, chunk in enumerate(chunks):
                embed_chunk_batch.delay(document_id, doc.workspace_id, i, chunk)
            doc.chunk_count = len(chunks)
            doc.status = DocumentStatus.READY
            db.commit()
        except Exception as exc:
            doc.status = DocumentStatus.FAILED
            doc.error_message = str(exc)
            db.commit()
            raise self.retry(exc=exc, countdown=2**self.request.retries)
    return {"document_id": document_id, "chunks": doc.chunk_count}


@celery_app.task(bind=True, max_retries=3, queue="embedding")
def embed_chunk_batch(self, document_id: str, workspace_id: str, chunk_index: int, chunk: str) -> dict[str, object]:
    try:
        vector = embeddings.embed_texts([chunk])[0]
        vectorstore.upsert_chunk(uuid.UUID(workspace_id), uuid.UUID(document_id), chunk_index, vector, chunk)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries)
    return {"document_id": document_id, "chunk_index": chunk_index}