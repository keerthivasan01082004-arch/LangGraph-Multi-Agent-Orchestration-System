"""Shared FastAPI dependencies: auth, RBAC, tenant scoping."""

import uuid

import jwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AuthorizationError, PermissionDeniedError
from app.core.security import decode_token
from app.db.models import Role, User, Workspace, WorkspaceMember
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthorizationError("Missing bearer token")
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = str(payload["sub"])
    except (jwt.PyJWTError, KeyError) as exc:
        raise AuthorizationError("Invalid or expired token") from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthorizationError("User not found or inactive")
    return user


def get_workspace(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or not workspace.is_active:
        raise PermissionDeniedError("Workspace not accessible")
    membership = (
        db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == workspace.id, WorkspaceMember.user_id == user.id).first()
    )
    if membership is None:
        raise PermissionDeniedError("Not a member of this workspace")
    return workspace


def require_role(*roles: Role) -> object:
    def checker(
        workspace_id: str,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> WorkspaceMember:
        membership = (
            db.query(WorkspaceMember)
            .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user.id)
            .first()
        )
        if membership is None or membership.role not in roles:
            raise PermissionDeniedError(f"Requires one of roles: {[r.value for r in roles]}")
        return membership

    return checker