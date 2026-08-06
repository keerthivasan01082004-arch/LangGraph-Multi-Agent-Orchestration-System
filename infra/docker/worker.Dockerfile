FROM python:3.11-slim AS worker

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --no-cache-dir "fastapi" "uvicorn[standard]" "pydantic>=2.8" "pydantic-settings" "sqlalchemy>=2.0" "psycopg[binary]" "alembic" "redis" "celery" "langgraph>=0.2" "langgraph-checkpoint-postgres" "qdrant-client" "openai" "litellm" "pyjwt" "bcrypt" "structlog" "httpx" "tenacity" "tiktoken" "python-multipart" "boto3" "prometheus-client" "email-validator" "sentence-transformers" "onnxruntime"

CMD ["celery", "-A", "app.workers.celery_app:celery_app", "worker", "-Q", "ingestion,embedding", "--concurrency=4", "--loglevel=info"]