"""Authentication endpoints: register, login, refresh, logout.

JWT (access + refresh) with bcrypt password hashing. Full security design in
docs/12-security.md.
"""

import uuid

import jwt
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import AuthorizationError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.db.session import get_db
from app.schemas.user import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise ConflictError("Email already registered")
    user = User(email=body.email.lower(), full_name=body.full_name, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_pair_for(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise AuthorizationError("Invalid credentials")
    if not user.is_active:
        raise AuthorizationError("Account disabled")
    return _token_pair_for(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest) -> TokenResponse:
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
        user_id = str(payload["sub"])
    except jwt.PyJWTError as exc:
        raise AuthorizationError("Invalid refresh token") from exc
    return _token_pair_for(User(id=user_id))


@router.post("/logout", status_code=204)
def logout(_: User = Depends(get_current_user)) -> None:
    # Token is stateless (JWT). Client drops it; server may revoke via jti blocklist.
    return None


def _token_pair_for(user: User, user_id: str | None = None) -> TokenResponse:
    sub = user_id or str(user.id)
    return TokenResponse(
        access_token=create_access_token(sub),
        refresh_token=create_refresh_token(sub),
        token_type="bearer",
        expires_in=30 * 60,
        user=UserOut.model_validate({"id": sub, "email": getattr(user, "email", ""), "full_name": getattr(user, "full_name", "")}),
    )