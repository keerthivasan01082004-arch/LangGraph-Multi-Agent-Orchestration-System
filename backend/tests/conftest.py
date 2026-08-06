"""Test bootstrap: set required env before `app.config` is imported."""

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")