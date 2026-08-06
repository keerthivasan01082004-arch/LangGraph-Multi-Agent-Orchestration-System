"""Tests for JWT security primitives."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import get_settings
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password


def test_password_roundtrip():
    hashed = hash_password("s3cret!")
    assert verify_password("s3cret!", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_roundtrip():
    token = create_access_token("user-123", {"role": "admin"})
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert payload["role"] == "admin"


def test_refresh_token_cannot_be_used_as_access():
    token = create_refresh_token("user-123")
    with pytest.raises(jwt.PyJWTError):
        decode_token(token, expected_type="access")


def test_expired_token_rejected():
    settings = get_settings()
    payload = {
        "sub": "user-1",
        "type": "access",
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)