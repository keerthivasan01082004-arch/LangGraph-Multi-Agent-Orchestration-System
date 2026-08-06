FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --no-cache-dir "fastapi" "uvicorn[standard]" "pydantic>=2.8" "pydantic-settings" "sqlalchemy>=2.0" "psycopg[binary]" "alembic" "redis" "celery" "langgraph>=0.2" "langgraph-checkpoint-postgres" "qdrant-client" "openai" "litellm" "pyjwt" "bcrypt" "structlog" "httpx" "tenacity" "tiktoken" "python-multipart" "boto3" "prometheus-client" "email-validator"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]