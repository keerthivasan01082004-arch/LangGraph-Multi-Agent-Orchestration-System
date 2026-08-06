"""Celery application shared by all workers.

Broker/backend: Redis. See docs/03-tech-stack.md for the queue rationale.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "conductor",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.tasks.process_document": {"queue": "ingestion"},
        "app.workers.tasks.embed_chunk_batch": {"queue": "embedding"},
    },
    task_time_limit=600,
    task_soft_time_limit=540,
    broker_connection_retry_on_startup=True,
)