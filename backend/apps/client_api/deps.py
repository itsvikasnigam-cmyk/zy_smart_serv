from __future__ import annotations

"""FastAPI dependencies for client_api.

A request-bound ``CurrentUser`` is loaded from the JWT *and verified against the
DB* (so disabling a user invalidates outstanding tokens). Scoping rules:
- ``super_admin`` may target any client; client_id must be supplied as a query
  param where relevant.
- ``owner`` / ``agent`` are pinned to ``cid`` (their own client_id).
"""

from dataclasses import dataclass
from typing import Iterable

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text

from backend.shared.db import engine

from .auth import ROLE_SUPER_ADMIN, decode_jwt


@dataclass(frozen=True)
class CurrentUser:
    id: str
    client_id: str | None
    role: str
    email: str | None
    name: str | None


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing authorization")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authorization header")
    return parts[1].strip()


def _load_user_or_401(user_id: str) -> CurrentUser:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT id::text, client_id::text, role, email, name
                FROM api_users
                WHERE id = CAST(:uid AS uuid)
                LIMIT 1
                """
            ),
            {"uid": user_id},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return CurrentUser(id=row[0], client_id=row[1], role=row[2], email=row[3], name=row[4])


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    token = _extract_bearer(authorization)
    try:
        claims = decode_jwt(token)
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token expired") from e
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid token: {e}") from e

    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token missing sub")
    user = _load_user_or_401(sub)
    # Reject tokens whose claim no longer matches DB role (role change → re-login).
    claim_role = claims.get("role")
    if claim_role and claim_role != user.role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="role changed; please re-login")
    return user


def require_roles(*roles: str):
    def _inner(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if roles and user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return user

    return _inner


def resolve_client_scope(
    user: CurrentUser,
    *,
    explicit_client_id: str | None = None,
) -> str:
    """Resolve the client_id this request operates on.

    - ``super_admin`` may pass ``client_id`` to act on any client.
    - non-super_admin: ``client_id`` query param (if provided) must match own.
    """
    if user.role == ROLE_SUPER_ADMIN:
        if not explicit_client_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="super_admin requests must include client_id",
            )
        return explicit_client_id
    if not user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user has no client_id",
        )
    if explicit_client_id and explicit_client_id != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="client_id mismatch",
        )
    return user.client_id


def assert_role_in(user: CurrentUser, roles: Iterable[str]) -> None:
    if user.role not in tuple(roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
