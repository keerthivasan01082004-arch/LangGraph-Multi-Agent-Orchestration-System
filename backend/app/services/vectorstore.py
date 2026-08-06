"""Qdrant client helpers: collection lifecycle, upsert, hybrid-ish search.

Vectors are stored per-workspace using a payload filter for strict tenant
isolation; one collection is shared and filtered at query time.
"""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import get_settings


def _client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection() -> None:
    settings = get_settings()
    client = _client()
    if not client.collection_exists(settings.qdrant_collection):
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=qm.VectorParams(size=settings.embedding_dim, distance=qm.Distance.COSINE),
            # Keep the index in memory for fast filtering; large corpora move
            # the payload index to disk (see docs/11-database.md).
            on_disk_payload=False,
        )


def upsert_chunk(workspace_id: uuid.UUID, document_id: uuid.UUID, chunk_index: int, vector: list[float], text: str) -> None:
    settings = get_settings()
    client = _client()
    point_id = f"{document_id}:{chunk_index}"
    client.upsert(
        collection_name=settings.qdrant_collection,
        points=[
            qm.PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "workspace_id": str(workspace_id),
                    "document_id": str(document_id),
                    "chunk_index": chunk_index,
                    "text": text,
                },
            )
        ],
    )


def search(workspace_id: uuid.UUID, vector: list[float], limit: int = 6, document_ids: list[uuid.UUID] | None = None) -> list[dict[str, object]]:
    settings = get_settings()
    client = _client()
    must: list[qm.FieldCondition] = [qm.FieldCondition(key="workspace_id", match=qm.MatchValue(value=str(workspace_id)))]
    if document_ids:
        must.append(qm.FieldCondition(key="document_id", match=qm.MatchAny(any=[str(d) for d in document_ids])))
    hits = client.search(
        collection_name=settings.qdrant_collection,
        query_vector=vector,
        query_filter=qm.Filter(must=must),
        limit=limit,
        with_payload=True,
    )
    return [
        {
            "text": h.payload.get("text", ""),
            "score": h.score,
            "document_id": h.payload.get("document_id"),
            "chunk_index": h.payload.get("chunk_index"),
        }
        for h in hits
    ]


def delete_document_vectors(workspace_id: uuid.UUID, document_id: uuid.UUID) -> None:
    settings = get_settings()
    client = _client()
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=qm.FilterSelector(
            filter=qm.Filter(
                must=[
                    qm.FieldCondition(key="workspace_id", match=qm.MatchValue(value=str(workspace_id))),
                    qm.FieldCondition(key="document_id", match=qm.MatchValue(value=str(document_id))),
                ]
            )
        ),
    )