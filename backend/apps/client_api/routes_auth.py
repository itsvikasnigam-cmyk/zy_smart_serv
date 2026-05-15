from __future__ import annotations

"""Authentication + identity routes for client_api.

Endpoints:
    POST /auth/login   — email + password → JWT
    GET  /auth/me      — current user
    GET  /users        — list users in current client (handy for assignment UI)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text

from backend.shared.db import engine

from .auth import ROLE_SUPER_ADMIN, make_jwt, verify_password
from .deps import CurrentUser, get_current_user, resolve_client_scope
from .models import LoginRequest, LoginResponse, UserOut

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest) -> LoginResponse:
    email = (req.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email required")
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT id::text, client_id::text, role, name, email, password_hash
                FROM api_users
                WHERE lower(email) = :email
                LIMIT 1
                """
            ),
            {"email": email},
        ).fetchone()
    if not row or not verify_password(req.password, row[5]):
        # Single error to avoid email enumeration.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    user_id, client_id, role, name, email_db, _hash = row
    token, exp = make_jwt(user_id=user_id, client_id=client_id, role=role)
    return LoginResponse(
        access_token=token,
        expires_at=exp,
        user=UserOut(id=user_id, client_id=client_id, name=name, email=email_db, role=role),
    )


@router.get("/auth/me", response_model=UserOut)
def auth_me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> UserOut:
    return UserOut(
        id=user.id,
        client_id=user.client_id,
        name=user.name,
        email=user.email,
        role=user.role,  # type: ignore[arg-type]
    )


@router.get("/me", response_model=UserOut, include_in_schema=True)
def me_blueprint_alias(user: Annotated[CurrentUser, Depends(get_current_user)]) -> UserOut:
    """Blueprint ``GET /me`` — alias of ``GET /auth/me``."""
    return UserOut(
        id=user.id,
        client_id=user.client_id,
        name=user.name,
        email=user.email,
        role=user.role,  # type: ignore[arg-type]
    )


@router.get("/users", response_model=list[UserOut])
def list_users(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    client_id: Annotated[str | None, Query(description="Required for super_admin; ignored otherwise")] = None,
    role: Annotated[str | None, Query(description="Filter by role (owner|agent|super_admin)")] = None,
) -> list[UserOut]:
    scope = resolve_client_scope(user, explicit_client_id=client_id)
    params: dict[str, object] = {"cid": scope}
    sql = """
        SELECT id::text, client_id::text, name, email, role
        FROM api_users
        WHERE client_id = CAST(:cid AS uuid)
    """
    if role:
        sql += " AND role = :role"
        params["role"] = role
    sql += " ORDER BY role, lower(coalesce(name, email, ''))"

    with engine.begin() as conn:
        rows = conn.execute(text(sql), params).all()
    return [UserOut(id=r[0], client_id=r[1], name=r[2], email=r[3], role=r[4]) for r in rows]
