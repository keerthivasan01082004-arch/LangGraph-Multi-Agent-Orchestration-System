"""Pydantic v2 schemas for auth and common API shapes."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, SecretStr


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    thread_id: str
    created_at: datetime
    messages: list[MessageOut] = []


class Paginated(BaseModel):
    items: list[object]
    total: int
    page: int
    page_size: int
    next_cursor: str | None = None